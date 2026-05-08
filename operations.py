from datetime import date, datetime
import logger
import params
import pyexasol
import time
import os
import smtplib
from email.message import EmailMessage
import requests
import uuid
from typing import Dict, List
import pandas as pd

def open_exa_saas_edw_prod_connection():
    # Connect to EDW Exasol DB:
    logger.log_info('Connecting to EDW Exasol Prod (SaaS)')

    connection_attempts = 1
    max_attempts = 3
    while connection_attempts <= max_attempts:
        try:
            conn_exa_edw = pyexasol.connect(dsn=params.exasol_saas_dsn,
                                            user=params.exasol_saas_user,
                                            password=params.exasol_saas_password,
                                            compression=params.exasol_saas_compression,
                                            schema=params.exasol_saas_schema)
            logger.log_info(f'Successful connection to EDW Exasol Prod (SaaS) on attempt {connection_attempts}')
            break

        except Exception as e:
            logger.log_info("Connection timeout. Retrying in 5 minutes...")
            time.sleep(300)  # Wait for 5 minutes before retrying
            connection_attempts += 1

            if connection_attempts > max_attempts:
                logger.log_error(str(e))

    return conn_exa_edw


def create_email_txt():
    filename = 'email_' + str(date.today()) + '.txt'

    if os.path.exists('EmailTxts/'+filename):
        # If file exists for today, rename it so we can create a new one:
        os.rename('EmailTxts/'+filename, 'EmailTxts/'+filename+'_ARCH_'+str(datetime.now().strftime("%Y%m%d%H%M%S"))+'.txt')

    with open('EmailTxts/'+filename, 'w') as f:
        txt = 'EDW to Ometria Payloads'
        f.write(txt)


def update_email_txt(txt):
    filename = 'email_' + str(date.today()) + '.txt'
    file = open('EmailTxts/'+filename, 'a')
    file.write('\n ' + str(datetime.now().strftime("%d/%m/%Y %H:%M:%S")) + ': ' + txt)


def send_email(subject, content):
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = subject
    msg['From'] = params.gmail_user
    msg['To'] = params.gmail_dl

    try:
        # Send the message via our own SMTP server.
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(params.gmail_user, params.gmail_app_password)
        server.send_message(msg)
        server.quit()
        logger.log_info('Email sent')
    except Exception as e:
        logger.log_warning(e)


def update_db_control(conn, updated_by, process, sub_process, descr):
    # This function takes a set of parameters and updates the DB_LOGS table in Exasol.
    sql = "INSERT INTO LAYER0_CONTROL.DB_LOGS VALUES(SYSDATE, SYSTIMESTAMP, '" + updated_by + "', '" + process + "', '" + sub_process + "', '" + descr + "')"
    conn.execute(sql)


def check_dependencies(edw_conn):
    logger.log_info('Checking dependent processes (IP, SCV, OneStock, Ometria S3 load, SQL Executer)...')
    count = 0
    while True:
        # Check if dependent processes have updated...
        stmt = edw_conn.execute("""SELECT COUNT(*) CNT
                                    FROM (
                                        -- Island Pacific:
                                        SELECT MIN(EVENT_TIMESTAMP) COMPLETE_TIMESTAMP 
                                        FROM LAYER0_CONTROL.DB_LOGS 
                                        WHERE EVENT_DATE = CURRENT_DATE 
                                        AND PROCESS = 'EDW Overnight Process' 
                                        AND SUB_PROCESS = 'MicroStrategy Events Triggered' -- IP
                                        AND DESCR = 'Triggered' 
                                        UNION ALL 
                                        -- Single Customer View
                                        SELECT MIN(EVENT_TIMESTAMP) COMPLETE_TIMESTAMP
                                        FROM LAYER0_CONTROL.DB_LOGS 
                                        WHERE EVENT_DATE = CURRENT_DATE
                                        AND PROCESS = 'Single Customer View'
                                        AND SUB_PROCESS IS NULL  
                                        AND DESCR = 'Process complete'
                                        UNION ALL 
                                        -- OneStock process
                                        SELECT MIN(EVENT_TIMESTAMP) COMPLETE_TIMESTAMP
                                        FROM LAYER0_CONTROL.DB_LOGS 
                                        WHERE EVENT_DATE = CURRENT_DATE
                                        AND PROCESS = 'EDW to OneStock Process'
                                        AND SUB_PROCESS IS NULL  
                                        AND DESCR = 'Process complete'
                                        UNION ALL 
                                        -- Ometria S3 > EDW process
                                        SELECT MIN(EVENT_TIMESTAMP) COMPLETE_TIMESTAMP
                                        FROM LAYER0_CONTROL.DB_LOGS 
                                        WHERE EVENT_DATE = CURRENT_DATE
                                        AND PROCESS = 'Ometria S3 to EDW Processing'
                                        AND SUB_PROCESS IS NULL  
                                        AND DESCR = 'Process complete'
                                        UNION ALL 
                                        -- SQL Executer (updates the PROD_OPTION tables)
                                        SELECT MIN(EVENT_TIMESTAMP) COMPLETE_TIMESTAMP
                                        FROM LAYER0_CONTROL.DB_LOGS 
                                        WHERE EVENT_DATE = CURRENT_DATE
                                        AND PROCESS = 'EDW SQL Script Executer'
                                        AND SUB_PROCESS IS NULL  
                                        AND DESCR = 'Process complete')
                                    WHERE COMPLETE_TIMESTAMP IS NOT NULL
                                    HAVING COUNT(*) = 5""")

        record = stmt.fetchall()

        # If no trigger has happened after 8 hours kill the program.
        if count == 480:
            logger.log_error('Process waited for 8 hours. Killing program')
            exit()

        if record:
            logger.log_info("Dependent jobs completed. Moving to next stage.")
            break
        else:
            logger.log_info("Dependent jobs not yet completed. Wait another minute...")

        count += 1
        # Wait for one minute before checking again
        time.sleep(60)


def fetch_customer_locations(edw, brand) -> List[Dict]:
    # Fetch customer locations from Exasol. This retrieves the full history.

    if brand == 'Monsoon':
        query = """
                SELECT EMAIL, LATEST_EXPRESS_CC_LOCATION_ID, LATEST_EXPRESS_CC_LOCATION_DESCR, 
                       LATEST_RETAIL_LOCATION_ID, LATEST_RETAIL_LOCATION_DESCR
                FROM REVERSE_ETL_PROD.OMETRIA_LAST_CUSTOMER_MONSOON_LOCATIONS_VW
                ORDER BY 1
                """
    else:
        query = """
                SELECT EMAIL, LATEST_EXPRESS_CC_LOCATION_ID, LATEST_EXPRESS_CC_LOCATION_DESCR, 
                       LATEST_RETAIL_LOCATION_ID, LATEST_RETAIL_LOCATION_DESCR
                FROM REVERSE_ETL_PROD.OMETRIA_LAST_CUSTOMER_ACCESSORIZE_LOCATIONS_VW
                ORDER BY 1
                """

    try:
        # Execute query and fetch results
        logger.log_info(f'Retrieving last shopped data for {brand}...')
        result = edw.export_to_list(query)
        logger.log_info(f'Retrieved {len(result)} records')

        return [
            {
                'email': row[0],
                'latest_express_cc_location_id': row[1],
                'latest_express_cc_location_descr': row[2],
                'latest_retail_location_id': row[3],
                'latest_retail_location_descr': row[4]
            } for row in result
        ]
    except Exception as e:
        logger.log_error(f"Error fetching data from Exasol: {str(e)}")
        raise


def fetch_customer_locations_r7d(edw, brand) -> List[Dict]:
    # Fetch customer locations from Exasol. This retrieves the last 7 days only.

    if brand == 'Monsoon':
        query = """
                SELECT EMAIL, LATEST_EXPRESS_CC_LOCATION_ID, LATEST_EXPRESS_CC_LOCATION_DESCR, 
                       LATEST_RETAIL_LOCATION_ID, LATEST_RETAIL_LOCATION_DESCR
                FROM REVERSE_ETL_PROD.OMETRIA_LAST_CUSTOMER_MONSOON_LOCATIONS_R7D_VW
                ORDER BY 1
                """
    else:
        query = """
                SELECT EMAIL, LATEST_EXPRESS_CC_LOCATION_ID, LATEST_EXPRESS_CC_LOCATION_DESCR, 
                       LATEST_RETAIL_LOCATION_ID, LATEST_RETAIL_LOCATION_DESCR
                FROM REVERSE_ETL_PROD.OMETRIA_LAST_CUSTOMER_ACCESSORIZE_LOCATIONS_R7D_VW
                ORDER BY 1
                """

    try:
        # Execute query and fetch results
        logger.log_info(f'Retrieving last shopped data for {brand} for the last 7 days...')
        result = edw.export_to_list(query)
        logger.log_info(f'Retrieved {len(result)} records')

        return [
            {
                'email': row[0],
                'latest_express_cc_location_id': row[1],
                'latest_express_cc_location_descr': row[2],
                'latest_retail_location_id': row[3],
                'latest_retail_location_descr': row[4]
            } for row in result
        ]
    except Exception as e:
        logger.log_error(f"Error fetching data from Exasol: {str(e)}")
        raise


def transform_to_ometria_payload(data: List[Dict]) -> List[Dict]:
    payload = []
    #logger.log_info('Transforming last shopped data to Ometria Payload...')

    for record in data:
        unique_id = str(uuid.uuid4())

        payload_item = {
            '@type': 'contact',
            '@collection': 'dwh_customer',
            'id': unique_id,
            'email': record['email'],
            '@merge': True,
            'last_click_collect_store_id': str(record.get('latest_express_cc_location_id', '')),
            'last_click_collect_store_descr': record.get('latest_express_cc_location_descr', ''),
            'last_shopped_store_id': str(record.get('latest_retail_location_id', '')),
            'last_shopped_store_descr': record.get('latest_retail_location_descr', '')
        }

        payload.append(payload_item)

    #logger.log_info('Ometria Payload created')
    return payload


def send_to_ometria(payload: List[Dict], brand: str, max_retries: int = 3, initial_backoff: float = 2.0) -> None:
    """
    Send payload to Ometria API with retry logic on 502 (and other 5xx) errors.

    Args:
        payload: List of dictionaries to send
        brand: 'Monsoon' or other brand to select API key
        max_retries: Maximum number of retry attempts (default: 3)
        initial_backoff: Starting wait time in seconds (doubles each retry)
    """
    if brand == 'Monsoon':
        key = params.mon_production_API_key
    else:
        key = params.acc_production_API_key

    headers = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'X-Ometria-Auth': f'{key}'
    }

    url = 'https://api.ometria.com/v2/push'
    attempt = 0
    backoff = initial_backoff

    while attempt <= max_retries:
        attempt += 1

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            # logger.log_info(f"Successfully sent {brand} data to Ometria. Status: {response.status_code}")
            return  # Success → exit function

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None

            # Only retry on 502 (Bad Gateway) and some other transient server errors
            if status_code in (502, 503, 504):
                if attempt <= max_retries:
                    wait_time = backoff * (2 ** (attempt - 1))  # exponential backoff: 2s → 4s → 8s ...
                    # logger.log_warning(f"Ometria returned {status_code} - retrying in {wait_time}s "
                    #                  f"(attempt {attempt}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.log_error(f"Failed to send to Ometria after {max_retries} retries - "
                                     f"final error: {str(e)}")
                    raise
            else:
                # Non-retryable status (4xx, other 5xx, etc.)
                logger.log_error(f"Non-retryable Ometria error: {str(e)} - Status: {status_code}")
                raise

        except requests.exceptions.RequestException as e:
            # Timeout, connection error, etc.
            if attempt <= max_retries:
                wait_time = backoff * (2 ** (attempt - 1))
                # logger.log_warning(f"Request failed ({str(e)}) - retrying in {wait_time}s "
                #                  f"(attempt {attempt}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                logger.log_error(f"Failed to send to Ometria after {max_retries} retries - {str(e)}")
                raise

    # This line should never be reached if logic is correct
    raise RuntimeError("Unexpected exit from retry loop")


def send_to_ometria_staging(payload: List[Dict], brand) -> None:
    """Send payload to Ometria API."""
    logger.log_info(f'Attempting to send {brand} payload to Ometria...')
    if brand == 'Monsoon':
        key = params.mon_staging_API_key
    else:
        key = params.acc_staging_API_key


    headers = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'X-Ometria-Auth': f'{key}'
    }

    try:
        response = requests.post('https://api.ometria.com/v2/push', headers=headers, json=payload)
        response.raise_for_status()
        logger.log_info(f"Successfully sent data to Ometria. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.log_error(f"Error sending data to Ometria: {str(e)}")
        raise


def send_customer_locations_to_ometria(edw_conn):
    brands = ['Monsoon', 'Accessorize']

    try:
        for brand in brands:
            logger.log_info(f'Running for {brand}')
            # Fetch data from Exasol
            customer_data = fetch_customer_locations_r7d(edw_conn, brand)

            # Find the length of the customer data
            data_length = len(customer_data)
            batch_size = 100
            log_interval = 10000

            start_time = time.time()
            last_log_time = start_time

            # Call the payload for every 100 customers followed by a small delay
            for i in range(0, data_length, batch_size):
                batch = customer_data[i:i + batch_size]

                # Transform to Ometria payload format
                ometria_payload = transform_to_ometria_payload(batch)

                # Send to Ometria API
                send_to_ometria(ometria_payload, brand)

                # Add small delay between API calls
                time.sleep(0.2)

                processed = i + len(batch)  # more accurate than just i

                if processed >= log_interval and processed % log_interval == 0:
                    current_time = time.time()
                    elapsed = current_time - start_time
                    since_last = current_time - last_log_time

                    rate = processed / elapsed if elapsed > 0 else 0

                    logger.log_info(
                        f"[{brand}] Processed {processed:,} / {data_length:,} "
                        f"customers | {rate:,.0f} rec/s | "
                        f"total: {elapsed:.1f}s | last 10k: {since_last:.1f}s"
                    )

                    last_log_time = current_time

                    time.sleep(5)  # Wait another 5 seconds after each 10k records

        logger.log_info('All data has been sent.')

    except Exception as e:
        print(f"Error in main process: {str(e)}")
        raise


def retrieve_low_stock_monsoon_data(edw_conn):
    logger.log_info('Retrieving low stock data from EDW...')
    monsoon_sql = 'SELECT * FROM REVERSE_ETL_PROD.OMETRIA_LOW_STOCK_EMAIL_TRIGGER_MONSOON_VW'
    monsoon_df = edw_conn.export_to_pandas(monsoon_sql)
    logger.log_info('Low stock data retrieved successfully.')

    return monsoon_df


def create_low_stock_monsoon_payload(df: pd.DataFrame, event_type: str = "low_stock", timestamp: str = None) -> list:
    logger.log_info('Creating low stock payload...')

    if timestamp is None:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Group and aggregate
    grouped = (df.groupby('EMAIL')
               .agg({
        'ID': 'first',  # take the first id for the email
        'PROD_OPTION': list  # collect all prod_options into a list
    })
               .reset_index())

    payloads = []
    for _, row in grouped.iterrows():
        # Convert PROD_OPTION values to strings (this is the key fix)
        prod_options = [str(option) for option in row['PROD_OPTION']]

        payload = {
            "properties": {
                "product_id": prod_options
            },
            "@type": "custom_event",
            "id": str(row['ID']),
            "event_type": event_type,
            "timestamp": timestamp,
            "identity_email": row['EMAIL']
        }
        payloads.append(payload)

    logger.log_info(f'Low stock payload created with {len(payloads)} events.')
    return payloads


def update_audit_log(edw_conn, df: pd.DataFrame,event_type,timestamp: str = None) -> pd.DataFrame:
    if timestamp is None:
        timestamp = datetime.utcnow()

        # Create audit log with one row per original record
    audit_df = pd.DataFrame({
        "event_type": event_type,
        "identity_email": df['EMAIL'],
        "prod_option": df['PROD_OPTION'],
        "timestamp": timestamp
    })

    edw_conn.import_from_pandas(audit_df, ('REVERSE_ETL_PROD','OMETRIA_STOCK_EMAIL_AUDIT'))


def retrieve_back_in_stock_monsoon_data(edw_conn):
    logger.log_info('Retrieving browsers back in stock data from EDW...')
    monsoon_sql = 'SELECT * FROM REVERSE_ETL_PROD.OMETRIA_BACK_IN_STOCK_EMAIL_TRIGGER_MONSOON_VW'
    monsoon_df = edw_conn.export_to_pandas(monsoon_sql)
    logger.log_info('Browsers back in stock data successfully retrieved')
    return monsoon_df


def create_back_in_stock_monsoon_payload(df: pd.DataFrame,event_type: str = "browsers_back_in_stock",timestamp: str = None) -> list:
    if timestamp is None:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Group by email
    grouped = (df.groupby('EMAIL')
               .agg({
        'ID': 'first',  # one ID per email
        'PROD_OPTION': list  # list of all products for that email
    })
               .reset_index())

    payloads = []
    for _, row in grouped.iterrows():
        # Convert all product IDs to strings (very important!)
        product_ids = [str(option) for option in row['PROD_OPTION']]

        payload = {
            "properties": {
                "product_id": product_ids  # ← now list of strings
            },
            "@type": "custom_event",
            "id": str(row['ID']),
            "event_type": event_type,
            "timestamp": timestamp,
            "identity_email": row['EMAIL']
        }
        payloads.append(payload)

    return payloads


def send_low_stock_payloads_to_ometria(low_stock_monsoon_df, edw_conn):
    low_stock_monsoon_df = low_stock_monsoon_df.reset_index(drop=True)

    chunk_size = 100

    for i in range(0, len(low_stock_monsoon_df), chunk_size):
        chunk_df = low_stock_monsoon_df.iloc[i:i + chunk_size]

        try:
            # Create payload for this chunk
            chunk_payload = create_low_stock_monsoon_payload(chunk_df)

            # Send to Ometria
            send_to_ometria(chunk_payload, 'Monsoon')

            # Update audit log immediately for this chunk (only successful ones)
            update_audit_log(edw_conn, chunk_df, 'low_stock')

            print(f"✅ Sent and audited chunk {i // chunk_size + 1} "
                  f"({len(chunk_df)} records)")

        except Exception as e:
            print(f"❌ Failed on chunk starting at index {i}: {e}")
            # Optionally break or continue depending on your preference
            # break   # uncomment if you want to stop on first error

        # Small delay between requests (skip after last chunk)
        if i + chunk_size < len(low_stock_monsoon_df):
            time.sleep(0.1)


def send_browsers_back_in_stock_payloads_to_ometria(back_in_stock_monsoon_df, edw_conn):
    back_in_stock_monsoon_df = back_in_stock_monsoon_df.reset_index(drop=True)

    chunk_size = 100

    for i in range(0, len(back_in_stock_monsoon_df), chunk_size):
        chunk_df = back_in_stock_monsoon_df.iloc[i:i + chunk_size]

        try:
            # Create payload for this chunk
            chunk_payload = create_back_in_stock_monsoon_payload(chunk_df)

            # Send to Ometria
            send_to_ometria(chunk_payload, 'Monsoon')

            # Update audit log immediately for this chunk (only successful ones)
            update_audit_log(edw_conn, chunk_df, 'browsers_back_in_stock')

            print(f"✅ Sent and audited chunk {i // chunk_size + 1} "
                  f"({len(chunk_df)} records)")

        except Exception as e:
            print(f"❌ Failed on chunk starting at index {i}: {e}")
            # Optionally break or continue depending on your preference
            # break   # uncomment if you want to stop on first error

        # Small delay between requests (skip after last chunk)
        if i + chunk_size < len(back_in_stock_monsoon_df):
            time.sleep(0.1)
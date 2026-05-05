import pandas as pd
from datetime import datetime
import operations


def retrieve_low_stock_monsoon_data(edw_conn):
    monsoon_sql = 'SELECT * FROM REVERSE_ETL_TEST.OMETRIA_LOW_STOCK_EMAIL_TRIGGER_MONSOON_VW limit 10'
    monsoon_df = edw_conn.export_to_pandas(monsoon_sql)

    return monsoon_df


def create_low_stock_monsoon_payload(df: pd.DataFrame, event_type: str = "low_stock", timestamp: str = None) -> list:
    if timestamp is None:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    grouped = (df.groupby('EMAIL')
               .agg({
        'ID': 'first',  # take the first id for the email
        'PROD_OPTION': list  # collect all prod_options into a list
    })
               .reset_index())

    payloads = []

    for _, row in grouped.iterrows():
        payload = {
            "properties": {
                "products_list_custom_field": row['PROD_OPTION']
            },
            "@type": "custom_event",
            "id": str(row['ID']),
            "event_type": event_type,
            "timestamp": timestamp,
            "identity_email": row['EMAIL']
        }
        payloads.append(payload)

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

    edw_conn.import_from_pandas(audit_df, ('REVERSE_ETL_TEST','OMETRIA_STOCK_EMAIL_AUDIT'))


def retrieve_back_in_stock_monsoon_data(edw_conn):
    monsoon_sql = 'SELECT * FROM REVERSE_ETL_TEST.OMETRIA_BACK_IN_STOCK_EMAIL_TRIGGER_MONSOON_VW limit 10'
    monsoon_df = edw_conn.export_to_pandas(monsoon_sql)

    return monsoon_df


def create_back_in_stock_monsoon_payload(df: pd.DataFrame,event_type: str = "back_in_stock",timestamp: str = None) -> list:
    if timestamp is None:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Group by email: take first ID and collect all product options into a list
    grouped = (df.groupby('EMAIL')
               .agg({
        'ID': 'first',  # one ID per email
        'PROD_OPTION': list  # list of all products for that email
    })
               .reset_index())

    payloads = []
    for _, row in grouped.iterrows():
        payload = {
            "properties": {
                "products_list_custom_field": row['PROD_OPTION']
            },
            "@type": "custom_event",
            "id": str(row['ID']),  # ensure string as in example
            "event_type": event_type,
            "timestamp": timestamp,
            "identity_email": row['EMAIL']
        }
        payloads.append(payload)

    return payloads


# Testing low stock
edw_conn = operations.open_exa_saas_edw_prod_connection()
low_stock_monsoon_df = retrieve_low_stock_monsoon_data(edw_conn)
low_stock_monsoon_payload = create_low_stock_monsoon_payload(low_stock_monsoon_df)
operations.send_to_ometria_staging(low_stock_monsoon_payload, 'Monsoon')
update_audit_log(edw_conn,low_stock_monsoon_df,'low_stock')

back_in_stock_monsoon_df = retrieve_back_in_stock_monsoon_data(edw_conn)
back_in_stock_monsoon_payload = create_back_in_stock_monsoon_payload(back_in_stock_monsoon_df)
operations.send_to_ometria_staging(back_in_stock_monsoon_payload, 'Monsoon')
update_audit_log(edw_conn,back_in_stock_monsoon_df,'back_in_stock')

print('The end')
edw_conn.close()
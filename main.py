import logger
import operations
import os
import time
from datetime import date

def main():
    edw_conn = operations.open_exa_saas_edw_prod_connection()

    logger.log_info(f'################## {os.path.basename(os.path.dirname(os.path.abspath(__file__)))} Process Started ##################')
    operations.update_db_control(edw_conn, 'Python', f'{os.path.basename(os.path.dirname(os.path.abspath(__file__)))}',
                                 '', 'Process started')

    #### Main processing starts here
    # 1. Send customer locations (last shopped / last C&C) to Ometria
    operations.send_customer_locations_to_ometria(edw_conn)

    # 2. Send Low Stock email trigger:
    low_stock_monsoon_df = operations.retrieve_low_stock_monsoon_data(edw_conn)
    low_stock_monsoon_payload = operations.create_low_stock_monsoon_payload(low_stock_monsoon_df)
    operations.send_to_ometria_staging(low_stock_monsoon_payload, 'Monsoon')
    operations.update_audit_log(edw_conn, low_stock_monsoon_df, 'low_stock')

    # 3. Send Back in Stock email trigger:
    back_in_stock_monsoon_df = operations.retrieve_back_in_stock_monsoon_data(edw_conn)
    back_in_stock_monsoon_payload = operations.create_back_in_stock_monsoon_payload(back_in_stock_monsoon_df)
    operations.send_to_ometria_staging(back_in_stock_monsoon_payload, 'Monsoon')
    operations.update_audit_log(edw_conn, back_in_stock_monsoon_df, 'back_in_stock')

    #### Main processing ends here
    logger.log_info('Documentation can be found in the EDW to Ometria Payloads section of this document:')
    logger.log_info('https://monsoonaccessorize.sharepoint.com/:w:/s/BI/EUOOrNtUsD9PgaCbzouTvtUBbjw5BrihYZh-cq89LGA8tw?e=mWLDkS')

    # Send confirmation email
    emailsubject = 'SUCCESS: Ometria Last Shopped Store & Last C&C Store Updated'
    filename = 'email_' + str(date.today()) + '.txt'
    with open('EmailTxts/' + filename, 'r') as f:
        emailcontent = f.read()
    operations.send_email(emailsubject, emailcontent)

    logger.log_info(f'################## {os.path.basename(os.path.dirname(os.path.abspath(__file__)))} Process Complete ##################')
    operations.update_db_control(edw_conn, 'Python', f'{os.path.basename(os.path.dirname(os.path.abspath(__file__)))}',
                                 '', 'Process started')

if __name__ == "__main__":
    operations.create_email_txt()
    main()
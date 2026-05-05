import configparser

#  Load the configuration file
config = configparser.RawConfigParser()
config.read(r'C:\Python Projects\0. CONFIG\config.ini', encoding='utf-8')

#  Gmail parameters
gmail_user = config['gmail']['gmail_user']
gmail_app_password = config['gmail']['gmail_app_password']
gmail_dl = ['jtbrown@monsoon.co.uk','clee@monsoon.co.uk']

#  Exasol parameters
exasol_saas_dsn = config['exasol']['exasol_saas_dsn']
exasol_saas_user = config['exasol']['exasol_saas_user']
exasol_saas_password = config['exasol']['exasol_saas_password']
exasol_saas_compression_string = config['exasol']['exasol_saas_compression']
exasol_saas_compression = exasol_saas_compression_string.strip().lower() == 'true'
exasol_saas_schema = 'LAYER1_STAGING'

#  Ometria parameters
acc_staging_API_key = config['ometria_payload_keys']['acc_staging_API_key']
acc_production_API_key = config['ometria_payload_keys']['acc_production_API_key']
mon_staging_API_key = config['ometria_payload_keys']['mon_staging_API_key']
mon_production_API_key = config['ometria_payload_keys']['mon_production_API_key']
ometria_api_url = 'https://api.ometria.com/v2/push'

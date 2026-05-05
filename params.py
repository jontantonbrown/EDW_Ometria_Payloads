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

#  Ometria parameters - to be entered into the params file
acc_staging_API_key = '6df9cf5a33eb70ac35cbed015f3604d7'
acc_production_API_key = '5176469c9bcf8add59239591150eae53'

mon_staging_API_key = 'd1e9887546f591e64e5b50fc5265b718'
mon_production_API_key = '607ca451e16f8ca5bec47f1fdf149116'
ometria_api_url = 'https://api.ometria.com/v2/push'
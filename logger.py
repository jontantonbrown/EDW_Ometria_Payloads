import logging
from logging.handlers import RotatingFileHandler
import operations
import sys
from datetime import date

# Set up rotating file handler: 50MB max size, 3 backup files
log_handler = RotatingFileHandler(
    filename='EDW_to_Ometria_Payloads.log',
    maxBytes=20 * 1024 * 1024,  # 20 MB in bytes
    backupCount=3  # Keep 3 previous versions
)

# Configure logging
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

def log_info(str):
    print(str)
    logging.info(str)
    operations.update_email_txt(str)

def log_warning(str):
    logging.warning(str)
    operations.update_email_txt(str)

def log_error(message):
    print(message)
    logging.error(message)
    operations.update_email_txt(message)
    filename = 'email_' + str(date.today()) + '.txt'
    subject = 'ERROR: EDW to Ometria Payloads'
    with open('EmailTxts/' + filename, 'r') as f:
        emailcontent = f.read()
    operations.send_email(subject, emailcontent)
    sys.exit()
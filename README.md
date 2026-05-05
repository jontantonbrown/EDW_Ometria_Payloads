# EDW to Ometria Payloads

This Python project extracts data from the Enterprise Data Warehouse (Exasol) and sends it to **Ometria** to support Monsoon & Accessorize email marketing campaigns.

## Overview

The solution runs daily at **04:00 AM** via Windows Task Scheduler on server **AZR-ETL-PROD**.

It performs three main functions:
1. Sends the latest shopped and Click & Collect store information for customers.
2. Triggers **Low Stock** emails.
3. Triggers **Back In Stock** emails.

## Project Structure
EDW_Ometria_Payloads/
├── main.py                 # Main orchestration script
├── operations.py           # Core functions (DB, API, payloads, etc.)
├── logger.py               # Logging and email alert handling
├── params.py               # Configuration loader (reads config.ini)
├── EDW_to_Ometria_Payloads.log   # Main log file (rotating)
├── EmailTxts/              # Daily email notification files
├── C:\Python Projects\0. CONFIG\config.ini   # Secrets & connection strings
text## Features & Process Flow

### 1. Customer Location Updates (Last Shopped & Click & Collect)
- Uses views:
  - `REVERSE_ETL_PROD.OMETRIA_LAST_CUSTOMER_MONSOON_LOCATIONS_R7D_VW`
  - `REVERSE_ETL_PROD.OMETRIA_LAST_CUSTOMER_ACCESSORIZE_LOCATIONS_R7D_VW`
- Data is sent in batches of **100** records with delays.
- Updates custom attributes in Ometria contacts.

### 2. Low Stock Email Triggers (Monsoon only)
- Source view: `REVERSE_ETL_PROD.OMETRIA_LOW_STOCK_EMAIL_TRIGGER_MONSOON_VW`
- Creates custom events in Ometria.
- Logs sent items in `REVERSE_ETL_PROD.OMETRIA_STOCK_EMAIL_AUDIT`

### 3. Back In Stock Email Triggers (Monsoon only)
- Source view: `REVERSE_ETL_PROD.OMETRIA_BACK_IN_STOCK_EMAIL_TRIGGER_MONSOON_VW`
- Creates custom events in Ometria.
- Logs sent items in audit table.

## Technical Details

- **Language**: Python 3
- **Database**: Exasol (via `pyexasol`)
- **API**: Ometria v2 Push API
- **Logging**: Rotating log file (20MB × 3 backups)
- **Notifications**: Gmail alerts on success and error
- **Error Handling**: Retry logic on transient Ometria errors (502, 503, etc.)

## Setup & Configuration

1. Place the project in:  
   `C:\Python Projects\EDW_Ometria_Payloads`
2. Ensure `config.ini` exists in `C:\Python Projects\0. CONFIG\`
3. Required Python packages: `pyexasol`, `pandas`, `requests`
4. Windows Task Scheduler runs `main.py` daily at 04:00.

## Running the Script

```bash
cd "C:\Python Projects\EDW_Ometria_Payloads"
python main.py
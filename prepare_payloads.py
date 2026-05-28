# ABOUTME: Fetches item data by barcode and builds PUT payloads for updating serial numbers.
# ABOUTME: Outputs a CSV of prepared payloads that can be reviewed before running mass_update.py.

import os
import requests
import csv
import sys
import json
from dotenv import load_dotenv

load_dotenv()

# ------------------------------ Configuration ------------------------------ #

CLIENT_ID = os.environ['DESTINY_CLIENT_ID']
CLIENT_SECRET = os.environ['DESTINY_CLIENT_SECRET']

# API Base URL
BASE_URL = os.environ['DESTINY_BASE_URL']

# CSV file paths
INPUT_CSV_FILE_PATH = './input/laptops.csv'          # Path to your input CSV
OUTPUT_CSV_FILE_PATH = './output/update_payloads.csv' # Path to save the prepared payloads

# ------------------------------ Field IDs ------------------------------ #

# These field IDs are district-specific. Use inspect_item_fields() or the
# /materials/resourcetypes/{id} endpoint to find yours.
SERIAL_NUMBER_FIELD_ID = 18
BARCODE_FIELD_ID = 2
CONDITION_FIELD_ID = 4

# ------------------------------ Functions ------------------------------ #

def get_access_token(client_id, client_secret):
    """
    Obtain an access token using client credentials.
    """
    token_url = f"{BASE_URL}/auth/accessToken"
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        print(f"Requesting access token from {token_url}...")
        response = requests.post(token_url, data=data, headers=headers)
        response.raise_for_status()
        token_info = response.json()
        access_token = token_info.get('access_token')
        if not access_token:
            print("Error: Access token not found in the response.")
            sys.exit(1)
        print("Access token obtained successfully.\n")
        return access_token
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while obtaining access token: {http_err}")
        print(f"Response Body: {response.text}")
        sys.exit(1)
    except Exception as err:
        print(f"An error occurred while obtaining access token: {err}")
        sys.exit(1)

def get_specific_item_details(access_token, item_barcode):
    """
    Fetch details of a specific item using its Barcode.
    """
    url = f"{BASE_URL}/materials/resources/items"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    params = {
        'itemBarcode': item_barcode
    }

    try:
        print(f"Fetching details for Item Barcode: {item_barcode}...")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get('value', [])
        if not items:
            print(f"No items found with Barcode: {item_barcode}\n")
            return None
        item_details = items[0]  # Assuming barcode is unique
        print("Item details fetched successfully.\n")
        return item_details
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while fetching item details: {http_err}")
        print(f"Response Body: {response.text}\n")
        return None
    except Exception as err:
        print(f"An error occurred while fetching item details: {err}\n")
        return None

def prepare_update_payload(item_details, new_serial_number, condition):
    """
    Create the payload for updating the serial number, including Barcode and Condition.
    """
    resource_id = item_details.get('resource', {}).get('guid', '')
    site_id = item_details.get('site', {}).get('guid', '')
    item_guid = item_details.get('guid', '')

    # Extract existing Barcode
    barcode = item_details.get('barcode', '')

    # Construct the payload with Barcode, Condition, and Serial Number
    payload = {
        "resourceId": resource_id,
        "siteId": site_id,
        "itemFields": [
            {
                "id": BARCODE_FIELD_ID,
                "value": barcode
            },
            {
                "id": CONDITION_FIELD_ID,
                "value": condition
            },
            {
                "id": SERIAL_NUMBER_FIELD_ID,
                "value": new_serial_number
            }
        ]
    }

    return {
        'GUID': item_guid,
        'Site ID': site_id,
        'Serial Number': new_serial_number,
        'Barcode': barcode,
        'Condition': condition,
        'Payload': json.dumps(payload)
    }

def read_input_csv(csv_file_path):
    """
    Read the input CSV and return a list of dictionaries.
    """
    items = []
    try:
        with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                items.append(row)
        print(f"Successfully read {len(items)} rows from '{csv_file_path}'.\n")
        return items
    except FileNotFoundError:
        print(f"Error: File '{csv_file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)

def write_output_csv(payloads, csv_file_path):
    """
    Write the prepared payloads to an output CSV file.
    """
    # Define the CSV columns
    csv_columns = ['GUID', 'Site ID', 'Serial Number', 'Barcode', 'Condition', 'Payload']

    try:
        print(f"Writing update payloads to CSV file '{csv_file_path}'...")
        with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for payload in payloads:
                writer.writerow(payload)
        print(f"Update payloads successfully written to '{csv_file_path}'.\n")
    except IOError as e:
        print(f"Error writing to CSV file: {e}")
        sys.exit(1)

def main():
    print("=== Destiny Laptop Serial Number Update - Preparation Phase ===\n")

    # Step 1: Authenticate and get access token
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)

    # Step 2: Read the input CSV
    input_items = read_input_csv(INPUT_CSV_FILE_PATH)

    # Step 3: Prepare update payloads
    prepared_payloads = []
    for item in input_items:
        barcode = item.get('Barcode', '').strip()
        new_serial_number = item.get('Serial Number', '').strip()
        guid = item.get('GUID', '').strip()
        site_id = item.get('Site ID', '').strip()
        condition = item.get('Condition', '').strip()

        if not barcode:
            print(f"Skipping item with GUID: {guid} due to missing Barcode.\n")
            continue
        if not new_serial_number:
            print(f"Skipping item with GUID: {guid} due to missing Serial Number.\n")
            continue
        if not condition:
            print(f"Skipping item with GUID: {guid} due to missing Condition.\n")
            continue

        item_details = get_specific_item_details(access_token, barcode)
        if not item_details:
            print(f"Skipping item with Barcode: {barcode} as details could not be fetched.\n")
            continue

        # Prepare the update payload (Serial Number, Barcode, Condition)
        prepared_payload = prepare_update_payload(item_details, new_serial_number, condition)
        prepared_payloads.append(prepared_payload)

    if not prepared_payloads:
        print("No payloads prepared. Exiting.\n")
        sys.exit(0)

    # Step 4: Write the prepared payloads to the output CSV
    write_output_csv(prepared_payloads, OUTPUT_CSV_FILE_PATH)

    print("Preparation phase completed successfully. Review the 'update_payloads.csv' before proceeding with updates.\n")

if __name__ == "__main__":
    main()

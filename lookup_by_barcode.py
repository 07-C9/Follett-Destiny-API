# ABOUTME: Looks up item details in Follett Destiny by barcode and exports results to CSV.
# ABOUTME: Takes a CSV of barcodes as input, queries the API for each, outputs GUID/Site/Serial/Barcode.

import requests
import csv
import sys
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

# ------------------------------ Configuration ------------------------------ #

CLIENT_ID = os.environ['DESTINY_CLIENT_ID']
CLIENT_SECRET = os.environ['DESTINY_CLIENT_SECRET']
BASE_URL = os.environ['DESTINY_BASE_URL']
INPUT_CSV_FILE_PATH = './input/barcodes.csv'
OUTPUT_CSV_FILE_PATH = './output/item_details.csv'

# ------------------------------ Functions ------------------------------ #

def get_access_token(client_id, client_secret):
    """Obtain an access token using client credentials."""
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
        print(f"Response Body: {response.text}\n")
        sys.exit(1)
    except Exception as err:
        print(f"An error occurred while obtaining access token: {err}")
        sys.exit(1)

def read_barcodes(csv_file_path):
    """Read the input CSV and return a list of barcodes."""
    barcodes = []
    try:
        with open(csv_file_path, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)

            # Debug: Print detected fieldnames
            print(f"Detected CSV fieldnames: {reader.fieldnames}")

            # Normalize fieldnames: strip spaces and convert to lowercase
            normalized_fields = [field.strip().lower() for field in reader.fieldnames]
            print(f"Normalized fieldnames: {normalized_fields}")

            if 'barcode' not in normalized_fields:
                print("Error: Input CSV must contain a 'Barcode' column.")
                sys.exit(1)

            # Identify the actual field name for 'Barcode' (case-insensitive)
            barcode_field = None
            for field in reader.fieldnames:
                if field.strip().lower() == 'barcode':
                    barcode_field = field
                    break

            if not barcode_field:
                print("Error: 'Barcode' column not found after normalization.")
                sys.exit(1)

            for row in reader:
                barcode = row[barcode_field].strip()
                if barcode:
                    barcodes.append(barcode)

        print(f"Successfully read {len(barcodes)} barcodes from '{csv_file_path}'.\n")
        return barcodes
    except FileNotFoundError:
        print(f"Error: File '{csv_file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input CSV file: {e}")
        sys.exit(1)

def fetch_item_details(access_token, barcode):
    """Fetch item details for a specific barcode."""
    url = f"{BASE_URL}/materials/resources/items"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    params = {
        'itemBarcode': barcode,
        'includeCurrentCheckout': 'false',  # Adjust based on need
        '$top': 1  # Assuming barcode is unique; retrieve only one item
    }

    try:
        print(f"Searching for item with Barcode: {barcode}...")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get('value', [])

        if not items:
            print(f"No item found with Barcode: {barcode}.\n")
            return {
                'GUID': barcode,  # Retain barcode if GUID not found
                'Site GUID': 'Not Found',
                'Serial Number': 'Not Found',
                'Barcode': barcode
            }

        # Assuming the first match is the correct item
        item = items[0]
        item_guid = item.get('guid', '')
        site_guid = item.get('site', {}).get('guid', '')  # Changed from internalId to guid
        serial_number = item.get('serialNumber', '')
        barcode_returned = item.get('barcode', '')

        # Ensure all fields are strings before calling strip()
        item_guid = str(item_guid).strip() if item_guid else ''
        site_guid = str(site_guid).strip() if site_guid else ''
        serial_number = str(serial_number).strip() if serial_number else ''
        barcode_returned = str(barcode_returned).strip() if barcode_returned else ''

        print(f"Found Item - GUID: {item_guid}, Site GUID: {site_guid}, Serial Number: {serial_number}, Barcode: {barcode_returned}\n")

        return {
            'GUID': item_guid,
            'Site GUID': site_guid,
            'Serial Number': serial_number,
            'Barcode': barcode_returned
        }

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while fetching Barcode {barcode}: {http_err}")
        print(f"Response Body: {response.text}\n")
        return {
            'GUID': barcode,
            'Site GUID': 'Error',
            'Serial Number': 'Error',
            'Barcode': barcode
        }
    except Exception as err:
        print(f"An error occurred while fetching Barcode {barcode}: {err}")
        return {
            'GUID': barcode,
            'Site GUID': 'Error',
            'Serial Number': 'Error',
            'Barcode': barcode
        }

def write_output_csv(items, output_file_path):
    """Write the list of item details to the output CSV."""
    headers = ['GUID', 'Site GUID', 'Serial Number', 'Barcode']
    try:
        with open(output_file_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            for item in items:
                writer.writerow(item)
        print(f"Successfully wrote {len(items)} items to '{output_file_path}'.\n")
    except Exception as e:
        print(f"Error writing to output CSV file: {e}")
        sys.exit(1)

def main():
    print("=== Destiny Item Details Generator ===\n")

    # Step 1: Authenticate and get access token
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)

    # Step 2: Read barcodes from input CSV
    barcodes = read_barcodes(INPUT_CSV_FILE_PATH)

    # Step 3: Fetch item details for each barcode
    item_details = []
    total_barcodes = len(barcodes)
    for index, barcode in enumerate(barcodes, start=1):
        print(f"Processing {index}/{total_barcodes}")
        item = fetch_item_details(access_token, barcode)
        item_details.append(item)
        # Optional: Sleep to respect API rate limits
        time.sleep(0.2)  # Adjust based on API rate limits

    # Step 4: Write the collected item details to the output CSV
    write_output_csv(item_details, OUTPUT_CSV_FILE_PATH)

    print("=== Process Completed ===")

if __name__ == "__main__":
    main()

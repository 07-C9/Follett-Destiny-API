# ABOUTME: Exports all items of a given resource type from Follett Destiny to CSV.
# ABOUTME: Outputs GUID, Site ID, Serial Number, Barcode, and Condition for each item.

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

RESOURCE_TYPE_ID = 119  # Find your resource type ID using the /materials/resourcetypes endpoint

# CSV file paths
OUTPUT_CSV_FILE_PATH = './output/items_export.csv'

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

def fetch_all_items(access_token, resource_type_id):
    """
    Fetch all items for a specific resource type.
    Attempts to retrieve all items in a single request by setting a large $top value.
    """
    url = f"{BASE_URL}/materials/resourcetypes/{resource_type_id}/items"
    headers = {
        'Authorization': f"Bearer {access_token}",
        'Accept': 'application/json'
    }
    params = {
        '$top': 1000000  # Set a large number to attempt to get all items in one call
    }
    try:
        print("Fetching all items...")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get('value', [])
        total_items = len(items)
        print(f"Total items fetched: {total_items}\n")
        return items
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while fetching items: {http_err}")
        print(f"Response Body: {response.text}")
        sys.exit(1)
    except Exception as err:
        print(f"An error occurred while fetching items: {err}")
        sys.exit(1)

def get_field_value(item_fields, field_name):
    """
    Retrieve the value of a field by its name from the item_fields list.
    """
    for field in item_fields:
        if field.get('name') == field_name:
            return field.get('value', '')
    return ''

def save_items_to_csv(items, csv_file_path):
    """
    Save the GUID, Site ID, Serial Number, Barcode, and Condition of items to a CSV file.
    """
    # Define the CSV columns
    csv_columns = ['GUID', 'Site ID', 'Serial Number', 'Barcode', 'Condition']

    # Prepare data for CSV
    csv_data = []
    for item in items:
        # Extract Barcode using existing keys
        barcode = item.get('itemBarcode', '') or item.get('barcode', '') or item.get('barcodeNumber', '')

        # Extract itemFields
        item_fields = item.get('itemFields', [])

        # Use the helper function to get Condition
        condition = get_field_value(item_fields, 'Condition')

        csv_data.append({
            'GUID': item.get('guid', ''),
            'Site ID': item.get('site', {}).get('internalId', ''),
            'Serial Number': item.get('serialNumber', ''),
            'Barcode': barcode,
            'Condition': condition
        })

    # Write to CSV
    try:
        print(f"Writing items to CSV file '{csv_file_path}'...")
        with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for data in csv_data:
                writer.writerow(data)
        print(f"Items successfully written to '{csv_file_path}'.\n")
    except IOError as e:
        print(f"Error writing to CSV file: {e}")
        sys.exit(1)

# ------------------------------ Main Execution ------------------------------ #

def main():
    print("=== Destiny Laptop Data Exporter ===\n")

    # Step 1: Authenticate and get access token
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)

    # Step 2: Fetch all items
    all_items = fetch_all_items(access_token, RESOURCE_TYPE_ID)

    # Step 3: Save required data to CSV
    save_items_to_csv(all_items, OUTPUT_CSV_FILE_PATH)

    print("Data export completed successfully.")

if __name__ == "__main__":
    main()

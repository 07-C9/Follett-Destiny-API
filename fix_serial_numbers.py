# ABOUTME: Fixes serial numbers in Follett Destiny that had a leading zero incorrectly prepended.
# ABOUTME: Reads correct serials from CSV, finds items with the wrong serial, and updates them via PUT.

import csv
import requests
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
log_file = './output/destiny_fix.log'
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
base_url = os.environ['DESTINY_BASE_URL']
client_id = os.environ['DESTINY_CLIENT_ID']
client_secret = os.environ['DESTINY_CLIENT_SECRET']
csv_file = './input/serials.csv'

def get_access_token():
    token_url = f"{base_url}/auth/accessToken"
    logging.info(f"Requesting access token from URL: {token_url}")
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        response = requests.post(token_url, data=data, headers=headers)
        logging.info(f"Response Status Code: {response.status_code}")
        logging.info(f"Response Body: {response.text}")
        response.raise_for_status()
        access_token = response.json().get('access_token')
        if not access_token:
            logging.error("Access token not found in the response.")
            return None
        logging.info("Access token obtained successfully.")
        return access_token
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred while obtaining access token: {http_err}")
    except Exception as err:
        logging.error(f"An error occurred while obtaining access token: {err}")
    return None


def get_item_by_serial_number(serial_number, headers):
    api_url = f"{base_url}/materials/resources/items"
    params = {
        '$filter': f"serialNumber eq '{serial_number}'"
    }
    logging.info(f"GET {api_url} with params {params}")
    try:
        response = requests.get(api_url, headers=headers, params=params)
        logging.info(f"Response Status Code: {response.status_code}")
        logging.info(f"Response Body: {response.text}")
        response.raise_for_status()
        items = response.json().get('value', [])
        if items:
            return items[0]  # Return the first matching item
        else:
            return None
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred while searching for item: {http_err}")
        logging.error(f"Response Body: {response.text}")
    except Exception as err:
        logging.error(f"An error occurred while searching for item: {err}")
    return None


def get_item_by_id(item_id, headers):
    api_url = f"{base_url}/materials/resources/items/{item_id}"
    logging.info(f"GET {api_url}")
    try:
        response = requests.get(api_url, headers=headers)
        logging.info(f"Response Status Code: {response.status_code}")
        logging.info(f"Response Body: {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred while retrieving item ID {item_id}: {http_err}")
        logging.error(f"Response Body: {response.text}")
    except Exception as err:
        logging.error(f"An error occurred while retrieving item ID {item_id}: {err}")
    return None


def get_site_by_id(site_id, headers):
    api_url = f"{base_url}/sites/{site_id}"
    logging.info(f"GET {api_url}")
    try:
        response = requests.get(api_url, headers=headers)
        logging.info(f"Response Status Code: {response.status_code}")
        logging.info(f"Response Body: {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred while retrieving site ID {site_id}: {http_err}")
        logging.error(f"Response Body: {response.text}")
    except Exception as err:
        logging.error(f"An error occurred while retrieving site ID {site_id}: {err}")
    return None


def update_item(item_data, correct_serial, headers):
    item_id = item_data['id']
    api_url = f"{base_url}/materials/resources/items/{item_id}"

    # Retrieve full site information
    site_id = item_data.get('site', {}).get('internalId')
    site_data = get_site_by_id(site_id, headers)
    if not site_data:
        logging.error(f"Could not retrieve site data for site ID {site_id}. Skipping update.")
        print(f"Could not retrieve site data for site ID {site_id}. Skipping update.")
        return False

    # Use 'internalId' or 'guid' based on API requirements. Here, we'll use 'internalId'.
    site_identifier = site_data.get('internalId')
    if not site_identifier:
        logging.error(f"Site data for site ID {site_id} does not contain 'internalId'. Skipping update.")
        print(f"Site data for site ID {site_id} does not contain 'internalId'. Skipping update.")
        return False

    # Prepare the update payload
    update_payload = {
        'serialNumber': correct_serial,
        'site': {'id': site_identifier},
        'resourceType': {'id': item_data['resourceType']['id']},
        'resource': {'id': item_data['resource']['id']},
        'condition': item_data.get('condition', 'Good'),
        'status': item_data.get('status', 'Available')
    }

    logging.info(f"PUT {api_url} with payload {update_payload}")

    try:
        response = requests.put(api_url, headers=headers, json=update_payload)
        logging.info(f"Response Status Code: {response.status_code}")
        logging.info(f"Response Body: {response.text}")
        response.raise_for_status()
        return True  # Update was successful
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred while updating item ID {item_id}: {http_err}")
        logging.error(f"Response Body: {response.text}")
        return False
    except Exception as err:
        logging.error(f"An error occurred while updating item ID {item_id}: {err}")
        return False


def main():
    access_token = get_access_token()
    if not access_token:
        print("Failed to obtain access token.")
        return

    headers = {
        'Authorization': f"Bearer {access_token}",
        'Content-Type': 'application/json'
    }

    # Read the CSV file
    try:
        with open(csv_file, newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        logging.info(f"CSV file '{csv_file}' read successfully.")
        print(f"CSV file '{csv_file}' read successfully.")
    except Exception as err:
        logging.error(f"Failed to read CSV file '{csv_file}': {err}")
        print(f"Failed to read CSV file '{csv_file}': {err}")
        return

    serials_to_update = []

    for row in rows:
        correct_serial = str(row['serial_number']).strip()
        incorrect_serial = '0' + correct_serial  # Construct the incorrect serial

        # Find the item in Destiny by incorrect serial number
        item = get_item_by_serial_number(incorrect_serial, headers)
        if item:
            item_id = item['id']
            full_item_data = get_item_by_id(item_id, headers)
            if not full_item_data:
                logging.error(f"Could not retrieve full data for item ID {item_id}. Skipping.")
                print(f"Could not retrieve full data for item ID {item_id}. Skipping.")
                continue

            # Check if the serial number already matches the correct one
            existing_serial = str(full_item_data.get('serialNumber')).strip()
            logging.info(f"Existing serial number for item {item_id}: '{existing_serial}'")
            logging.info(f"Correct serial number for item {item_id}: '{correct_serial}'")

            if existing_serial == correct_serial:
                print(f"Serial number for item {item_id} is already correct. No update needed.")
                logging.info(f"Serial number for item {item_id} is already correct. No update needed.")
                continue

            serials_to_update.append((incorrect_serial, correct_serial, full_item_data))
        else:
            logging.warning(f"Item with serial number {incorrect_serial} not found. Skipping.")
            print(f"Item with serial number {incorrect_serial} not found. Skipping.")

    if not serials_to_update:
        print("No serial numbers need to be updated.")
        return

    print(f"\n{len(serials_to_update)} serial number(s) will be updated. Proceed? (yes/no)")
    proceed = input().strip().lower()
    if proceed != 'yes':
        print("Operation cancelled by user.")
        return

    for incorrect_serial, correct_serial, full_item_data in serials_to_update:
        item_id = full_item_data['id']
        print(f"\nProcessing item ID {item_id}: {incorrect_serial} -> {correct_serial}")
        logging.info(f"Processing item ID {item_id}: {incorrect_serial} -> {correct_serial}")

        # Proceed with the update
        if update_item(full_item_data, correct_serial, headers):
            print(f"Successfully updated item {item_id}: {incorrect_serial} -> {correct_serial}")
            logging.info(f"Successfully updated item {item_id}: {incorrect_serial} -> {correct_serial}")
        else:
            print(f"Failed to update item {item_id}: {incorrect_serial} -> {correct_serial}")
            logging.error(f"Failed to update item {item_id}: {incorrect_serial} -> {correct_serial}")


if __name__ == '__main__':
    main()

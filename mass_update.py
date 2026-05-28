# ABOUTME: Mass-updates item fields (serial numbers, custodians) in Follett Destiny via the API.
# ABOUTME: Reads items from CSV, fetches current data, updates only what changed, and logs results.
import os
import requests
import csv
import sys
import json
import time
from dotenv import load_dotenv

load_dotenv()

# ------------------------------ Configuration ------------------------------ #

CLIENT_ID = os.environ['DESTINY_CLIENT_ID']
CLIENT_SECRET = os.environ['DESTINY_CLIENT_SECRET']
BASE_URL = os.environ['DESTINY_BASE_URL']
INPUT_CSV_FILE_PATH = './input/items.csv'  # Path to your input CSV
STAFF_CSV_FILE_PATH = './input/staff_patrons.csv'  # Path to staff patrons CSV

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

def read_staff_csv(csv_file_path):
    """Read the staff patrons CSV and return a dictionary mapping full names to GUIDs."""
    staff_mapping = {}
    try:
        with open(csv_file_path, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                full_name = f"{row['lastName'].upper()}, {row['firstName'].upper()} {row['middleName'].upper()}".strip()
                guid = row['GUID'].strip()
                staff_mapping[full_name] = guid
        print(f"Successfully read {len(staff_mapping)} staff patrons from '{csv_file_path}'.\n")
        return staff_mapping
    except FileNotFoundError:
        print(f"Error: File '{csv_file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading staff CSV file: {e}")
        sys.exit(1)

def read_input_csv(csv_file_path):
    """Read the input CSV and return a list of dictionaries."""
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
        print(f"Error reading input CSV file: {e}")
        sys.exit(1)

def fetch_full_item_data(access_token, item_guid):
    """Fetch the full item data for a specific item using its GUID."""
    url = f"{BASE_URL}/materials/resources/items/{item_guid}"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }

    try:
        print(f"Fetching full data for Item GUID: {item_guid}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        item_data = response.json()
        print("Item data fetched successfully.\n")
        return item_data
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while fetching item data: {http_err}")
        print(f"Response Body: {response.text}\n")
        return None
    except Exception as err:
        print(f"An error occurred while fetching item data: {err}\n")
        return None

def update_serial_number(access_token, item_data, new_serial_number, site_guid, custodian_guid):
    """
    Update the serial number and custodian GUID in the item data and send a PUT request to update the item.
    """
    item_guid = item_data.get('guid', '')
    url = f"{BASE_URL}/materials/resources/items/{item_guid}"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # Prepare the payload, copying existing item fields
    item_fields = item_data.get('itemFields', [])
    serial_number_updated = False

    # Update the serial number in itemFields only if it is different from the current one
    for field in item_fields:
        if field.get('name') == 'Serial Number':
            old_serial = field.get('value', '')
            if old_serial == new_serial_number:
                print(f"Serial number for Item GUID {item_guid} is already '{new_serial_number}'. Skipping update.\n")
                return "No Update Needed"  # Mark as no update needed
            field['value'] = new_serial_number  # Update the serial number
            serial_number_updated = True
            print(f"Serial Number for Item GUID {item_guid} updated from '{old_serial}' to '{new_serial_number}'.")
            break  # Assuming only one Serial Number field

    if not serial_number_updated:
        print(f"Serial Number field not found for Item GUID: {item_guid}. Skipping update.\n")
        return False

    # Update the Custodian field to patronGUID if custodian_guid is provided
    custodian_updated = False
    if custodian_guid:
        for field in item_fields:
            if field.get('name') == 'Custodian':
                old_custodian = field.get('value', '')
                field['value'] = custodian_guid  # Update to patron GUID
                custodian_updated = True
                print(f"Custodian for Item GUID {item_guid} set to Patron GUID '{custodian_guid}' (was '{old_custodian}').")
                break  # Assuming only one Custodian field

    if not custodian_updated and custodian_guid:
        print(f"No Custodian field found for Item GUID: {item_guid}. Skipping Custodian update.\n")

    # Prepare the payload without the Status field
    payload = {
        'resourceId': item_data['resource']['guid'],  # Use the resource GUID from the item data
        'siteId': site_guid,  # Use the provided site GUID
        'itemFields': [field for field in item_fields if field.get('name') != 'Status']  # Exclude Status field
    }

    # Optional: Print the payload for debugging
    print(f"Payload being sent for Item GUID {item_guid}:")
    print(json.dumps(payload, indent=2))
    print("\n")

    # Send the PUT request to update the item
    try:
        print(f"Updating Item GUID: {item_guid}...")
        response = requests.put(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print(f"Item {item_guid} updated successfully.\n")
        return "Updated"
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while updating item: {http_err}")
        print(f"Response Body: {response.text}\n")
        return False
    except Exception as err:
        print(f"An error occurred while updating item: {err}\n")
        return False

def confirm_update(total_items, sample_items):
    """Display a summary of the updates and prompt the user for confirmation."""
    print("=== Update Summary ===")
    print(f"Total items to be updated: {total_items}")
    print("\nSample of items to be updated:")
    print("{:<38} {:<38} {:<15} {:<15}".format("GUID", "Site GUID", "Serial Number", "Barcode"))
    print("-" * 110)
    for item in sample_items[:5]:  # Show first 5 items as a sample
        print("{:<38} {:<38} {:<15} {:<15}".format(
            item.get('GUID', ''),
            item.get('Site GUID', ''),
            item.get('Serial Number', ''),
            item.get('Barcode', '')
        ))
    print("-" * 110)
    print("...")

    # Prompt for confirmation
    while True:
        user_input = input(f"\nDo you want to proceed with updating {total_items} items? (yes/no): ").strip().lower()
        if user_input in ['yes', 'y']:
            print("Proceeding with updates...\n")
            return True
        elif user_input in ['no', 'n']:
            print("Update operation cancelled by the user.")
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

def main():
    print("=== Destiny Laptop Serial Number Update ===\n")

    # Step 1: Authenticate and get access token
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)

    # Step 2: Read the staff patrons CSV to build the mapping dictionary
    staff_mapping = read_staff_csv(STAFF_CSV_FILE_PATH)

    # Step 3: Read the input CSV
    input_items = read_input_csv(INPUT_CSV_FILE_PATH)

    # Step 4: Prepare list of items to update
    items_to_update = []
    for index, item in enumerate(input_items, start=1):
        guid = item.get('GUID', '').strip()
        new_serial_number = str(item.get('Serial Number', '').strip())
        barcode = item.get('Barcode', '').strip()
        site_guid = item.get('Site GUID', '').strip()  # Use 'Site GUID' directly from CSV

        # Validate required fields
        if not guid:
            print(f"Skipping item at row {index} due to missing GUID.\n")
            continue
        if not new_serial_number:
            print(f"Skipping item with GUID: {guid} due to missing Serial Number.\n")
            continue
        if not barcode:
            print(f"Skipping item with GUID: {guid} due to missing Barcode.\n")
            continue
        if not site_guid:
            print(f"Skipping item with GUID: {guid} due to missing Site GUID.\n")
            continue

        items_to_update.append({
            'GUID': guid,
            'Site GUID': site_guid,
            'Serial Number': new_serial_number,
            'Barcode': barcode
        })

    total_items = len(items_to_update)

    if total_items == 0:
        print("No items to update. Exiting.\n")
        sys.exit(0)

    # Step 5: Display summary and confirm
    confirm = confirm_update(total_items, items_to_update)
    if not confirm:
        sys.exit(0)

    # Step 6: Update serial numbers and prepare result logging
    success_count = 0
    no_update_needed_count = 0
    failure_count = 0
    results = []

    for index, item in enumerate(items_to_update, start=1):
        guid = item['GUID']
        new_serial_number = item['Serial Number']
        barcode = item['Barcode']
        site_guid = item['Site GUID']

        # Fetch full item data
        item_data = fetch_full_item_data(access_token, guid)
        if not item_data:
            print(f"Skipping item with GUID: {guid} due to failed data fetch.\n")
            failure_count += 1
            results.append({'Barcode': barcode, 'Status': 'Failed (Data Fetch Error)'})
            continue

        # Extract custodian name from item data, if present
        custodian_name = None
        for field in item_data.get('itemFields', []):
            if field.get('name') == 'Custodian':
                custodian_name = field.get('value', '').strip().upper()
                break

        # Only attempt to set custodian if custodian_name exists
        patron_guid = staff_mapping.get(custodian_name) if custodian_name else None

        # If there's a custodian but no matching patron GUID, skip update for that item
        if custodian_name and not patron_guid:
            print(f"Skipping update for Item GUID: {guid} due to missing patron GUID for Custodian '{custodian_name}'.\n")
            failure_count += 1
            results.append({'Barcode': barcode, 'Status': 'Failed (Missing Patron GUID)'})
            continue

        # Update serial number and custodian GUID if needed
        update_result = update_serial_number(access_token, item_data, new_serial_number, site_guid, patron_guid)
        if update_result == "Updated":
            success_count += 1
            results.append({'Barcode': barcode, 'Status': 'Successfully Updated'})
        elif update_result == "No Update Needed":
            no_update_needed_count += 1
            results.append({'Barcode': barcode, 'Status': 'No Update Needed'})
        else:
            failure_count += 1
            results.append({'Barcode': barcode, 'Status': 'Failed (Update Error)'})

        # Optional: Sleep to avoid hitting API rate limits
        time.sleep(0.5)  # Adjust as necessary based on API rate limits

    # Step 7: Final summary
    print("=== Update Process Completed ===")
    print(f"Total items attempted: {total_items}")
    print(f"Successfully updated: {success_count}")
    print(f"Didn't need updating: {no_update_needed_count}")
    print(f"Failed to update: {failure_count}\n")

    # Write results to a CSV file
    output_csv_file = './output/update_results.csv'
    with open(output_csv_file, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Barcode', 'Status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Results have been saved to '{output_csv_file}'.")

if __name__ == "__main__":
    main()

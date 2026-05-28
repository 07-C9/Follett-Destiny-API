# ABOUTME: Brute-forces patron discovery by scanning a range of internal IDs via the Destiny API.
# ABOUTME: The API has no "list all patrons" endpoint, so this hits /patrons/{id} for each ID in a range.

import os
import aiohttp
import asyncio
import csv
import sys
import json
import time
import logging
from dotenv import load_dotenv
from aiohttp import ClientSession, ClientResponseError
from tqdm.asyncio import tqdm_asyncio

load_dotenv()

# ------------------------------ Configuration ------------------------------ #

CLIENT_ID = os.environ['DESTINY_CLIENT_ID']
CLIENT_SECRET = os.environ['DESTINY_CLIENT_SECRET']
BASE_URL = os.environ['DESTINY_BASE_URL']

# Internal ID Range Configuration
START_ID = 100000  # Starting internalId (inclusive) - Adjust this range for your district
END_ID = 200000    # Ending internalId (inclusive) - Adjust this range for your district

# Output CSV File Path
OUTPUT_CSV = './output/staff_patrons.csv'

# Maximum number of concurrent requests
MAX_CONCURRENT_REQUESTS = 10  # Adjust based on API's concurrency support

# Delay between requests in seconds to respect rate limits
REQUEST_DELAY = 0.1  # Seconds

# Retry Configuration
MAX_RETRIES = 10
BACKOFF_FACTOR = 0.5

# ------------------------------ Logging Configuration ------------------------------ #

logging.basicConfig(
    filename='fetch_staff_patrons_async.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# ------------------------------ Functions ------------------------------ #

async def get_access_token(session: ClientSession) -> str:
    """
    Obtain an access token using client credentials.
    """
    token_url = f"{BASE_URL}/auth/accessToken"
    data = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        logging.info(f"Requesting access token from {token_url}...")
        async with session.post(token_url, data=data, headers=headers) as response:
            response.raise_for_status()
            token_info = await response.json()
            access_token = token_info.get('access_token')
            if not access_token:
                logging.error("Error: Access token not found in the response.")
                sys.exit(1)
            logging.info("Access token obtained successfully.\n")
            return access_token
    except ClientResponseError as e:
        logging.error(f"HTTP error occurred while obtaining access token: {e.status} {e.message}")
        response_text = await e.response.text()
        logging.error(f"Response Body: {response_text}\n")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An error occurred while obtaining access token: {e}")
        sys.exit(1)

async def fetch_patron_info(session: ClientSession, access_token: str, patron_id: int, retries: int = 3, backoff_factor: float = 0.5) -> dict:
    """
    Fetch patron information using the provided patron ID (guid or internalId).
    Implements retry logic with exponential backoff.
    Returns the patron data if found and is staff, else None.
    """
    url = f"{BASE_URL}/patrons/{patron_id}"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    patron_data = await response.json()
                    return patron_data
                elif response.status == 401:
                    logging.error(f"401 Unauthorized: Access token is invalid, expired, or missing for ID {patron_id}.")
                    return None
                elif response.status == 404:
                    # Patron not found; no need to log as error, just skip
                    return None
                elif response.status == 429:
                    # Rate limit exceeded
                    logging.warning(f"429 Too Many Requests: Rate limit exceeded for ID {patron_id}. Retrying after backoff.")
                    await asyncio.sleep(backoff_factor * (2 ** (attempt - 1)))
                else:
                    logging.error(f"Unexpected status {response.status} for patron ID {patron_id}.")
                    response_text = await response.text()
                    logging.error(f"Response Body: {response_text}\n")
                    return None
        except ClientResponseError as e:
            logging.error(f"HTTP error occurred while fetching patron info for ID {patron_id}: {e.status} {e.message}")
            response_text = await e.response.text()
            logging.error(f"Response Body: {response_text}\n")
            await asyncio.sleep(backoff_factor * (2 ** (attempt - 1)))
        except Exception as e:
            logging.error(f"An error occurred while fetching patron info for ID {patron_id}: {e}")
            await asyncio.sleep(backoff_factor * (2 ** (attempt - 1)))

    logging.error(f"Failed to fetch patron info for ID {patron_id} after {retries} attempts.")
    return None

def is_staff(patron_data: dict) -> bool:
    """
    Determine if the patron is a staff member based on siteAssociations.
    """
    site_associations = patron_data.get('siteAssociations', [])
    for association in site_associations:
        if association.get('type', '').lower() == 'staff' and association.get('status', '').lower() == 'active':
            return True
    return False

def extract_required_fields(patron_data: dict) -> dict:
    """
    Extract the required fields from patron data.
    """
    guid = patron_data.get('guid', '')
    internalId = patron_data.get('internalId', '')
    lastName = patron_data.get('lastName', '')
    firstName = patron_data.get('firstName', '')
    middleName = patron_data.get('middleName', '')

    # Determine type based on siteAssociations
    site_associations = patron_data.get('siteAssociations', [])
    patron_type = 'Unknown'  # Default

    for association in site_associations:
        if association.get('type', '').lower() == 'staff':
            patron_type = 'Staff'
            break
        elif association.get('type', '').lower() == 'student':
            patron_type = 'Student'
            break
        # Add more types if necessary

    return {
        'GUID': guid,
        'internalId': internalId,
        'lastName': lastName,
        'firstName': firstName,
        'middleName': middleName,
        'type': patron_type
    }

def initialize_csv(file_path: str):
    """
    Initialize the CSV file with headers.
    """
    headers = ['GUID', 'internalId', 'lastName', 'firstName', 'middleName', 'type']
    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
        logging.info(f"Initialized CSV file with headers: {headers}\n")
    except Exception as e:
        logging.error(f"Failed to initialize CSV file: {e}")
        sys.exit(1)

def append_to_csv(file_path: str, data: dict):
    """
    Append a row of data to the CSV file.
    """
    try:
        with open(file_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=data.keys())
            writer.writerow(data)
    except Exception as e:
        logging.error(f"Failed to append data to CSV: {e}")

async def process_patron(session: ClientSession, semaphore: asyncio.Semaphore, access_token: str, patron_id: int, csv_lock: asyncio.Lock):
    """
    Process a single patron: fetch, check if staff, and extract fields.
    """
    async with semaphore:
        patron_data = await fetch_patron_info(session, access_token, patron_id, retries=MAX_RETRIES, backoff_factor=BACKOFF_FACTOR)
        if patron_data and is_staff(patron_data):
            extracted_data = extract_required_fields(patron_data)
            async with csv_lock:
                append_to_csv(OUTPUT_CSV, extracted_data)
        # Respect API rate limits by delaying
        await asyncio.sleep(REQUEST_DELAY)

async def main_async():
    # Initialize CSV
    initialize_csv(OUTPUT_CSV)

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS)
    timeout = aiohttp.ClientTimeout(total=None)  # No total timeout
    async with ClientSession(connector=connector, timeout=timeout) as session:
        # Obtain access token
        access_token = await get_access_token(session)

        # Set up semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        # Lock for writing to CSV
        csv_lock = asyncio.Lock()

        # Prepare list of internal IDs
        patron_ids = list(range(START_ID, END_ID + 1))

        # Create tasks
        tasks = [
            asyncio.create_task(process_patron(session, semaphore, access_token, patron_id, csv_lock))
            for patron_id in patron_ids
        ]

        # Set up progress bar
        for f in tqdm_asyncio.as_completed(tasks, desc="Processing Patrons", total=len(tasks)):
            try:
                await f
            except Exception as e:
                logging.error(f"Exception occurred during patron processing: {e}")

    logging.info("=== Patron Fetching Process Completed ===")
    logging.info(f"CSV File Created: {OUTPUT_CSV}\n")

def main():
    start_time = time.time()
    asyncio.run(main_async())
    end_time = time.time()
    total_time = end_time - start_time
    logging.info(f"Total time taken: {total_time/60:.2f} minutes.")

if __name__ == "__main__":
    main()

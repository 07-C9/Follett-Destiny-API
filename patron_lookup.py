# ABOUTME: CLI tool to look up a single patron by GUID or internal ID in Follett Destiny.
# ABOUTME: Usage: python patron_lookup.py <patron_id>

import os
import requests
import argparse
import json
import sys
from dotenv import load_dotenv

load_dotenv()

# ------------------------------ Configuration ------------------------------ #

CLIENT_ID = os.environ['DESTINY_CLIENT_ID']
CLIENT_SECRET = os.environ['DESTINY_CLIENT_SECRET']
BASE_URL = os.environ['DESTINY_BASE_URL']

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
        print(f"Response Body: {response.text}\n")
        sys.exit(1)
    except Exception as err:
        print(f"An error occurred while obtaining access token: {err}")
        sys.exit(1)

def fetch_patron_info(access_token, patron_id):
    """
    Fetch patron information using the provided patron ID (guid or internalId).
    """
    url = f"{BASE_URL}/patrons/{patron_id}"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }

    try:
        print(f"Fetching patron details for ID: {patron_id}...")
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            patron_data = response.json()
            print("Patron details fetched successfully:\n")
            print(json.dumps(patron_data, indent=4))
            return patron_data
        elif response.status_code == 401:
            print("Error: Access token is invalid, expired, or missing.")
            print(f"Response Body: {response.text}\n")
            sys.exit(1)
        elif response.status_code == 404:
            print("Error: Patron not found using the given identifier.")
            print(f"Response Body: {response.text}\n")
            sys.exit(1)
        else:
            print(f"Unexpected error occurred. Status Code: {response.status_code}")
            print(f"Response Body: {response.text}\n")
            sys.exit(1)
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred while fetching patron info: {http_err}")
        print(f"Response Body: {response.text}\n")
        sys.exit(1)
    except Exception as err:
        print(f"An error occurred while fetching patron info: {err}")
        sys.exit(1)

# ------------------------------ Main Execution ------------------------------ #

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Fetch Patron Information from Destiny API")
    parser.add_argument('id', help='Patron Identifier (guid or internalId)')
    args = parser.parse_args()

    patron_id = args.id.strip()

    # Obtain access token
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET)

    # Fetch patron information
    fetch_patron_info(access_token, patron_id)

if __name__ == "__main__":
    main()

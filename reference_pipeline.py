# ABOUTME: Reference implementation showing how to extract all data from the Destiny API.
# ABOUTME: Covers sites, resource types, items (with pagination), and patron lookups.

'''
Reference implementation for extracting data from the Follett Destiny API.
Demonstrates the full pattern for pulling sites, resource types, items (with
pagination), and patron data. Not directly runnable as-is - adapt the credential
loading and output handling to fit your environment.

To view the API documentation, open Destiny and navigate to:
- "Setup" button in the top right
- API tab
- "Developer Help" button
- There will be several different categories, doesn't matter which one.
    3 buttons on the right, click the leftmost button (View ___ Documentation)
'''

import os
import sys
import requests
import json
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

base_url = os.environ['DESTINY_BASE_URL']
client_id = os.environ['DESTINY_CLIENT_ID']
client_secret = os.environ['DESTINY_CLIENT_SECRET']


def get_destiny_access_header():
    token_url = base_url + '/auth/accessToken'
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
    }
    response = requests.post(token_url, data=data)
    token = response.json().get('access_token')
    return {
        'Authorization': f'Bearer {token}'
    }



def task_query_destiny_api(**kwargs):
    templates_dict = kwargs.get("templates_dict")
    output = templates_dict.get("output_dir")
    staffid_df = helper_get_query_df(templates_dict.get("staff_sql"))
    staffids = staffid_df['staffid'].tolist()

    # get site info
    destiny_site_cols = ['id', 'state_id', 'name', 'short_name', 'library_site', 'media_site', 'textbook_site',
                        'resource_site', 'district_warehouse', 'district_advanced_booking', 'site_type_id', 'site_type_name']
    destiny_sites = []
    api_url = base_url + f'/sites'
    headers = get_destiny_access_header()
    response = requests.get(api_url, headers=headers)
    result = json.loads(response.text)
    for s in result.get('value', []):
        print(s)
        site_guid = s.get('guid')
        api_url = base_url + f'/sites/{site_guid}'
        headers = get_destiny_access_header()
        response = requests.get(api_url, headers=headers)
        site = json.loads(response.text)
        destiny_sites.append([
            site.get('internalId'),
            site.get('stateIdentifier'),
            site.get('name'),
            site.get('shortName'),
            s.get('librarySite'),
            s.get('mediaSite'),
            s.get('textbookSite'),
            s.get('resourceSite'),
            s.get('districtWarehouse'),
            s.get('districtAdvancedBooking'),
            s.get('siteType', {}).get('id'),
            s.get('siteType', {}).get('name'),
        ])
    site_df = pd.DataFrame(destiny_sites, columns=destiny_site_cols)
    site_df.to_csv(output+'/sites.csv', index=False)
    print("\n\nSites complete.\n\n")

    # get resource_type info
    destiny_resource_type_cols = ['id', 'name', 'parent_id']
    destiny_resource_types = []
    api_url = base_url + f'/materials/resourcetypes'
    headers = get_destiny_access_header()
    response = requests.get(api_url, headers=headers)
    result = json.loads(response.text)
    def get_resource_types(data, parent_id):
        print(data)
        for rt in data.get('children', []):
            destiny_resource_types.append([
                rt.get('id'),
                rt.get('name'),
                parent_id,
            ])
            if 'children' in rt.keys():
                get_resource_types(rt, rt.get('id'))
    get_resource_types(result, None)
    resource_types_df = pd.DataFrame(destiny_resource_types, columns=destiny_resource_type_cols)
    resource_types_df.to_csv(output+'/resource_types.csv', index=False)
    print("\n\nResource Types complete.\n\n")

    # get item info
    destiny_item_cols = ['item_id', 'barcode', 'serial_number', 'status', 'resource_type_id', 'resource_id',
                        'resource_name', 'site_id', 'patron_district_id', 'patron_id', 'date_out', 'date_due']
    destiny_items = []
    destiny_item_field_cols = ['item_id', 'field_id', 'field_name', 'value']
    destiny_item_fields = []
    destiny_item_note_cols = ['item_id', 'note_text', 'urgent']
    destiny_item_notes = []
    destiny_item_historical_note_cols = ['item_id', 'note_text']
    destiny_item_historical_notes = []
    api_url = base_url + f'/materials/resources/items?$top=100&$orderby=id&includeCurrentCheckout=True'
    params = {
        'includeCurrentCheckout': True,
    }
    failcount = 0
    while api_url != None:
        headers = get_destiny_access_header()
        response = requests.get(api_url, headers=headers)
        result = json.loads(response.text)
        try:
            for item in result.get('value', []):
                destiny_items.append([
                    item.get('id'),
                    item.get('barcode'),
                    item.get('serialNumber'),
                    item.get('status'),
                    item.get('resourceType', {}).get('id'),
                    item.get('resource', {}).get('id'),
                    item.get('resource', {}).get('name'),
                    item.get('site', {}).get('internalId'),
                    item.get('checkout', {}).get('districtId'),
                    item.get('checkout', {}).get('patronId'),
                    item.get('checkout', {}).get('dateOut'),
                    item.get('checkout', {}).get('dateDue'),
                ])
                for field in item.get('itemFields', []):
                    destiny_item_fields.append([
                        item.get('id'),
                        field.get('id'),
                        field.get('name'),
                        field.get('value'),
                    ])
                for note in item.get('itemNotes', []):
                    destiny_item_notes.append([
                        item.get('id'),
                        note.get('text'),
                        note.get('urgent'),
                    ])
                for histnote in item.get('historicalNotes', []):
                    destiny_item_historical_notes.append([
                        item.get('id'),
                        histnote.get('text'),
                    ])
            if result.get('@nextLink'):
                failcount = 0
                api_url = base_url + '/materials' + result['@nextLink'] + '&includeCurrentCheckout=True'
                print(api_url)
            else:
                api_url = None
        except Exception as e:
            failcount += 1
            print(f"Failed {failcount} time(s)! [api_url={api_url}] Error: {e}")
            if failcount >= 5:
                print("TOO MANY FAILS. EXITING.")
                sys.exit(1)
    items_df = pd.DataFrame(destiny_items, columns=destiny_item_cols)
    items_df.to_csv(output+'/items.csv', index=False)
    item_fields_df = pd.DataFrame(destiny_item_fields, columns=destiny_item_field_cols)
    item_fields_df.to_csv(output+'/item_fields.csv', index=False)
    item_notes_df = pd.DataFrame(destiny_item_notes, columns=destiny_item_note_cols)
    item_notes_df.to_csv(output+'/item_notes.csv', index=False)
    item_historical_notes_df = pd.DataFrame(destiny_item_historical_notes, columns=destiny_item_historical_note_cols)
    item_historical_notes_df.to_csv(output+'/item_historical_notes.csv', index=False)
    print("\n\nItems complete.\n\n")

    # get patron info
    destiny_patron_cols = ['district_id', 'id', 'first_name', 'last_name', 'site_id', 'primary_site', 'site_status', 'patron_type_id', 'patron_type_name']
    destiny_patrons = []
    for pat in staffids:
        print(pat)
        try:
            api_url = base_url + f'/circulation/patrons/{pat}/status'
            headers = get_destiny_access_header()
            response = requests.get(api_url, headers=headers)
            result = json.loads(response.text)
            for site in result.get('sites', []):
                destiny_patrons.append([
                    result.get('districtId'),
                    result.get('internalId'),
                    result.get('firstName'),
                    result.get('lastName'),
                    site.get('internalId'),
                    site.get('primarySite'),
                    site.get('status'),
                    site.get('patronType', {}).get('id'),
                    site.get('patronType', {}).get('name'),
                ])
        except Exception as e:
            print(f"Error retrieving data for '{pat}': {e}")
    patron_df = pd.DataFrame(destiny_patrons, columns=destiny_patron_cols)
    patron_df.to_csv(output+'/patrons.csv', index=False)
    print("\n\nPatrons complete.\n\n")

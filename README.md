# Follett Destiny API tools

Python scripts for working with the Follett Destiny API. Follett's own API docs are pretty thin and mostly locked behind their community portal login now, so hopefully this is useful if you're trying to figure it out.

I originally built these to fix a serial number problem. We had a few hundred devices in Destiny where the serials got a leading zero prepended during data entry (probably an Excel thing). Serials in Destiny didn't match our device management system, and Destiny's UI doesn't support bulk editing item fields, so the API was the only option. I spent a few weeks figuring it out through trial and error, including brute-forcing patron data out of the API since there's no endpoint to just list them all.

## Scripts

**fix_serial_numbers.py** - The original script that started all of this. Reads correct serial numbers from a CSV, finds the corresponding item in Destiny by searching for the incorrect serial (with the leading zero), and PUTs the corrected value. Prompts for confirmation before making changes.

**export_items.py** - Exports all items of a given resource type to CSV. Pulls GUID, Site ID, Serial Number, Barcode, and Condition. You'll probably want to run this first to see what you're working with.

**fetch_patrons_async.py** - The Destiny API doesn't have a "list all patrons" endpoint, so this brute-forces it by hitting `/patrons/{id}` for every ID in a numeric range (e.g., 100000 to 200000) using async requests. Filters for staff patrons and dumps the results to CSV. Takes a while but there's no other way to get a full patron list out.

**mass_update.py** - The final version of the bulk updater. Reads items from a CSV, fetches current data for each from the API, updates the Serial Number and Custodian fields if they differ, and logs results. Has a confirmation step and skip-if-already-correct logic so you can safely re-run it.

**lookup_by_barcode.py** - Takes a CSV of barcodes, hits the API for each one, and outputs the item's GUID, Site GUID, Serial Number, and Barcode. I used this to build the input files that mass_update needs.

**prepare_payloads.py** - Fetches item data by barcode and constructs the PUT request payloads. This is where I figured out the field ID mapping (Serial Number = 18, Barcode = 2, Condition = 4 in our instance). Your field IDs will probably be different. Outputs a CSV you can review before actually pushing updates.

**patron_lookup.py** - Simple CLI tool. Pass a patron GUID or internal ID, get the full JSON back. Useful for debugging.

**reference_pipeline.py** - Shows how to pull everything out of the API: sites, resource types, items (with pagination), and patrons. Not directly runnable as-is, but if you want to understand the full data model this is the place to look.

## Setup

```bash
# Clone the repo
git clone https://github.com/07-C9/Follett-Destiny-API.git
cd Follett-Destiny-API

# Set up a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy the example env file and fill in your credentials
cp .env.example .env
```

Edit `.env` with your Destiny API credentials. You can find/create these in Destiny under Setup > API tab. You need a client ID and secret with the "client credentials" grant type.

Your base URL will look something like:
```
https://yourdistrict.follettdestiny.com/api/v1/rest/context/destiny-XXXX-XXXX
```

The context name is specific to your Destiny instance. If your server doesn't host multiple districts, you can try just `destiny` as the context name.

The `.env` / dotenv approach is fine for running these locally. If you're putting any of this into a scheduled pipeline or automation, use a proper secrets manager instead of leaving credentials in a file on disk.

## CSV column names

The scripts expect specific column headers in their input CSVs. Here's what each one needs:

| Script | Input columns |
|--------|--------------|
| fix_serial_numbers.py | `serial_number` |
| mass_update.py | `GUID`, `Site GUID`, `Serial Number`, `Barcode` |
| lookup_by_barcode.py | `Barcode` |
| prepare_payloads.py | `GUID`, `Site ID`, `Serial Number`, `Barcode`, `Condition` |

Put input CSVs in `./input/` and the scripts will write output to `./output/`. Both directories are included in the repo.

## Things I learned the hard way

**Field IDs are not universal.** The numeric IDs for item fields (Serial Number, Barcode, Condition, etc.) vary by district/instance. You need to hit the `/materials/resourcetypes/{id}` endpoint to discover yours. The `prepare_payloads.py` script has the ones from our setup as defaults but yours will almost certainly be different.

**PUT requests need the full payload.** The API docs sort of mention this but it's easy to miss. If you PUT an update to an item and only include the field you're changing, it can blank out everything else. Always GET the full item first, modify what you need, then PUT the whole thing back. The `mass_update.py` script handles this.

**There's no "list all patrons" endpoint.** Seriously. You can look up a patron by ID, barcode, or districtId, but you can't just get a list. The `fetch_patrons_async.py` script works around this by scanning a range of internal IDs. It's slow but it works.

**Pagination uses OData.** The API uses `$top`, `$skip`, and `$orderby` parameters. The `@nextLink` field in the response gives you the next page URL, but you need to prepend your base URL to it. Check `reference_pipeline.py` for how the pagination loop works.

**The auth token expires.** Tokens last about an hour (3600 seconds). If you're doing a long-running operation, you might need to refresh it mid-run. The scripts in this repo don't handle token refresh, so keep that in mind for really large batches.

**Rate limiting exists but isn't documented.** I put short delays between requests (0.1 to 0.5 seconds) and didn't have problems. The async patron fetcher caps concurrent requests at 10. Your mileage may vary.

## API quick reference

These are the endpoints I actually used. Destiny has more (Circulations, Fines, CDL, etc.) but I didn't need them.

### Authentication
```
POST /auth/accessToken
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=YOUR_ID&client_secret=YOUR_SECRET
```
Returns a bearer token in `access_token`. Include it as `Authorization: Bearer <token>` on all subsequent requests.

### Items
```
GET /materials/resources/items                     # List all items (paginated)
GET /materials/resources/items/{id}                 # Get item by ID or GUID
GET /materials/resourcetypes/{type_id}/items        # List items by resource type
PUT /materials/resources/items/{guid}                # Update an item
```

Query parameters for listing items:
- `$top` - page size (default 25)
- `$skip` - offset
- `$orderby` - sort field (id, barcode)
- `itemBarcode` - filter by barcode
- `includeCurrentCheckout` - include checkout info (true/false)
- `modifiedSince` - ISO 8601 date filter

### Resource types
```
GET /materials/resourcetypes                        # Full hierarchy
GET /materials/resourcetypes/{id}                   # Specific type (includes field definitions)
```

The response from the specific type endpoint includes `itemFields` with field IDs, names, and data types. This is how you find your Serial Number field ID.

### Sites
```
GET /sites                                          # List all sites
GET /sites/{id}                                     # Specific site by GUID or internal ID
```

### Patrons
```
GET /patrons/{id}                                   # Lookup by GUID or internal ID
GET /circulation/patrons/{districtId}/status         # Patron status by district ID
```

## Contributing

PRs welcome if you've figured out other parts of the API.

## License

MIT

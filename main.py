from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

app = FastAPI()

class AirbnbResponse(BaseModel):
    highest_price: str
    lowest_price: str
    average_nightly_price: str
    availability_rate: str

def generate_curl_link(listing_id, checkin_date, checkout_date):
    # Base64 encode the listing ID in the format "StayListing:<listing_id>"
    encoded_id = base64.b64encode(f"StayListing:{listing_id}".encode('utf-8')).decode('utf-8')
    
    # Insert the encoded ID and dates into the cURL link
    curl_link = f'''https://www.airbnb.co.in/api/v3/StaysPdpSections/38218432c2d53194baa9c592ddd8e664cffcbcac58f0e118e8c1680eb9d58da7?operationName=StaysPdpSections&locale=en-IN&currency=INR&variables=%7B%22id%22%3A%22{encoded_id}%22%2C%22pdpSectionsRequest%22%3A%7B%22adults%22%3A%221%22%2C%22amenityFilters%22%3Anull%2C%22bypassTargetings%22%3Afalse%2C%22categoryTag%22%3Anull%2C%22causeId%22%3Anull%2C%22children%22%3Anull%2C%22disasterId%22%3Anull%2C%22discountedGuestFeeVersion%22%3Anull%2C%22displayExtensions%22%3Anull%2C%22federatedSearchId%22%3Anull%2C%22forceBoostPriorityMessageType%22%3Anull%2C%22hostPreview%22%3Afalse%2C%22infants%22%3Anull%2C%22interactionType%22%3Anull%2C%22layouts%22%3A%5B%22SIDEBAR%22%2C%22SINGLE_COLUMN%22%5D%2C%22pets%22%3A0%2C%22pdpTypeOverride%22%3Anull%2C%22photoId%22%3Anull%2C%22preview%22%3Afalse%2C%22previousStateCheckIn%22%3Anull%2C%22previousStateCheckOut%22%3Anull%2C%22priceDropSource%22%3Anull%2C%22privateBooking%22%3Afalse%2C%22promotionUuid%22%3Anull%2C%22relaxedAmenityIds%22%3Anull%2C%22searchId%22%3Anull%2C%22selectedCancellationPolicyId%22%3Anull%2C%22selectedRatePlanId%22%3Anull%2C%22splitStays%22%3Anull%2C%22staysBookingMigrationEnabled%22%3Afalse%2C%22translateUgc%22%3Anull%2C%22useNewSectionWrapperApi%22%3Afalse%2C%22sectionIds%22%3A%5B%22BOOK_IT_CALENDAR_SHEET%22%2C%22CANCELLATION_POLICY_PICKER_MODAL%22%2C%22POLICIES_DEFAULT%22%2C%22BOOK_IT_SIDEBAR%22%2C%22URGENCY_COMMITMENT_SIDEBAR%22%2C%22BOOK_IT_NAV%22%2C%22MESSAGE_BANNER%22%2C%22HIGHLIGHTS_DEFAULT%22%2C%22BOOK_IT_FLOATING_FOOTER%22%2C%22EDUCATION_FOOTER_BANNER%22%2C%22URGENCY_COMMITMENT%22%2C%22EDUCATION_FOOTER_BANNER_MODAL%22%5D%2C%22checkIn%22%3A%22{checkin_date}%22%2C%22checkOut%22%3A%22{checkout_date}%22%2C%22p3ImpressionId%22%3A%22p3_1725842290_P3p_2uEA0lDTYxPx%22%7D%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%2238218432c2d53194baa9c592ddd8e664cffcbcac58f0e118e8c1680eb9d58da7%22%7D%7D'''
    
    return curl_link

def fetch_json_from_airbnb(curl_url):
    headers = {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "content-type": "application/json",
        "device-memory": "8",
        "dpr": "1.3",
        "ect": "4g",
        "priority": "u=1, i",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "viewport-width": "1478",
        "x-airbnb-api-key": "d306zoyjsyarp7ifhu67rjxn52tv0t20",
        "x-airbnb-graphql-platform": "web",
        "x-airbnb-graphql-platform-client": "minimalist-niobe",
        "x-airbnb-supports-airlock-v2": "true",
    }

    response = requests.get(curl_url, headers=headers)
    return response.json()

def extract_price(data):
    try:
        stay_product = data.get('data', {}).get('presentation', {}).get('stayProductDetailPage', {})
        sections = stay_product.get('sections', {}).get('sections', [])
        
        if sections and sections[0].get('section') and sections[0]['section'].get('structuredDisplayPrice'):
            primary_line = sections[0]['section']['structuredDisplayPrice'].get('primaryLine', {})
            # Check for discountedPrice or fallback to price
            discounted_price = primary_line.get('discountedPrice') or primary_line.get('price', "not available")
            return discounted_price
        else:
            return "not available"
    except (KeyError, IndexError, TypeError):
        return "not available"

def get_price_for_date(listing_id, checkin_date, checkout_date):
    curl_url = generate_curl_link(listing_id, checkin_date, checkout_date)
    json_data = fetch_json_from_airbnb(curl_url)
    return extract_price(json_data)

def get_prices_concurrently(listing_id, start_date, num_days=30):
    prices = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_date = {}
        for day in range(num_days):
            checkin_date = start_date + timedelta(days=day)
            checkout_date = checkin_date + timedelta(days=2)
            future = executor.submit(get_price_for_date, listing_id, checkin_date.strftime("%Y-%m-%d"), checkout_date.strftime("%Y-%m-%d"))
            future_to_date[future] = checkin_date

        for future in as_completed(future_to_date):
            date = future_to_date[future]
            try:
                price = future.result()
                prices.append(price)
            except Exception as exc:
                print(f"Error fetching price for {date.strftime('%Y-%m-%d')}: {exc}")

    return prices

def calculate_average_price(valid_prices):
    if len(valid_prices) == 0:
        return 0
    return sum(valid_prices) / len(valid_prices)

def fetch_airbnb_occupancy_data(listing_id):
    # Base URL with a placeholder for listing ID
    base_url = "https://www.airbnb.co.in/api/v3/PdpAvailabilityCalendar/8f08e03c7bd16fcad3c92a3592c19a8b559a0d0855a84028d1163d4733ed9ade"
    query_params = (
        "?operationName=PdpAvailabilityCalendar&locale=en-IN&currency=INR&variables="
        "%7B%22request%22%3A%7B%22count%22%3A12%2C%22listingId%22%3A%22"
        f"{listing_id}"
        "%22%2C%22month%22%3A9%2C%22year%22%3A2024%7D%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%228f08e03c7bd16fcad3c92a3592c19a8b559a0d0855a84028d1163d4733ed9ade%22%7D%7D"
    )

    # Complete URL with listing ID
    url = base_url + query_params

    # Headers extracted from the cURL command
    headers = {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "content-type": "application/json",
        "device-memory": "8",
        "dpr": "1.3",
        "ect": "4g",
        "priority": "u=1, i",
        "referer": "https://www.airbnb.co.in/rooms/22021884...",
        "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-platform-version": '"15.0.0"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
        "viewport-width": "1478",
        "x-airbnb-api-key": "d306zoyjsyarp7ifhu67rjxn52tv0t20",
        "x-airbnb-graphql-platform": "web",
        "x-airbnb-graphql-platform-client": "minimalist-niobe",
        "x-airbnb-supports-airlock-v2": "true",
        "x-client-request-id": "0fywif91tmt3f11vdc4m203c4euo",
        "x-client-version": "c57d413b447fe3c7f2051773628446fe3b65c436",
        "x-csrf-token": "",
        "x-csrf-without-token": "1",
        "x-niobe-short-circuited": "true"
    }

    try:
        # Sending a GET request to the URL with the headers
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()  # Parse response to JSON
        return data
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

def calculate_occupancy_rate(data):
    today = datetime.now()
    five_months_later = today + timedelta(days=5*30)  # Approximation of 5 months

    available_days_count = 0
    total_days_count = 0

    # Traverse through the calendar months and days
    for month in data['data']['merlin']['pdpAvailabilityCalendar']['calendarMonths']:
        for day in month['days']:
            # Extract calendar date and convert it to datetime
            calendar_date_str = day['calendarDate']
            calendar_date = datetime.strptime(calendar_date_str, '%Y-%m-%d')

            # Check if the date is within the next 5 months
            if today <= calendar_date < five_months_later:
                total_days_count += 1  # Count the total number of days in range
                
                # Check the availability of the day
                available = day.get('available', False)
                if available:
                    available_days_count += 1

    # Calculate the availability rate as the percentage of available days
    if total_days_count > 0:
        availability_rate = (available_days_count / total_days_count) * 100
    else:
        availability_rate = 0
    return availability_rate

@app.get("/airbnb/{listing_id}", response_model=AirbnbResponse)
async def get_airbnb_data(listing_id: str):
    # Fetch and calculate occupancy rate
    occupancy_data = fetch_airbnb_occupancy_data(listing_id)
    if occupancy_data:
        availability_rate = calculate_occupancy_rate(occupancy_data)
    else:
        availability_rate = "not available"

    # Use current date as the start date for price calculations
    start_date = datetime.now()

    # Retry logic for fetching prices
    retries = 3
    valid_prices = []
    for attempt in range(retries):
        prices = get_prices_concurrently(listing_id, start_date)
        valid_prices = [float(price.replace('₹', '').replace(',', '')) for price in prices if price != "not available"]
        
        if valid_prices:
            break

    # Calculate the highest, lowest, and average prices
    if valid_prices:
        highest_price = f"₹{max(valid_prices)}"
        lowest_price = f"₹{min(valid_prices)}"
        average_price = f"₹{calculate_average_price(valid_prices):.2f}"
    else:
        highest_price = "not available"
        lowest_price = "not available"
        average_price = "not available"

    return AirbnbResponse(
        highest_price=highest_price,
        lowest_price=lowest_price,
        average_nightly_price=average_price,
        availability_rate=f"{availability_rate:.2f}%" if isinstance(availability_rate, float) else availability_rate
    )

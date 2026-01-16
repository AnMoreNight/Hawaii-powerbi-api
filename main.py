from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
import httpx
import os
from dotenv import load_dotenv
from typing import Optional, List
import json
from urllib.parse import quote
import logging

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hawaii Car Rental API", description="Filtered API for car rental reservations")

# API Configuration
BASE_URL = "https://api-america-west.caagcrm.com/api-america-west/car-rental/reservations"
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "Basic dTAzNUhSVWRGQUdvZlFPNzg2UVdoQmJEWWVFb3A2Tjk0bUFQODk3UEhRQ1VJY2c0ZG46cmp5YUZsWGVVM2pzQURTdkV5THJEYkpNYUlwYnpJbjFDUEFnRGJHbnF2ckxsNDhuc0Q=")


async def fetch_all_pages(client: httpx.AsyncClient, base_url: str, headers: dict, filters_json: str) -> List[dict]:
    """
    Fetch all pages of results from the paginated API.
    Returns a combined list of all reservations from all pages.
    """
    all_reservations = []
    page = 1
    last_page = None
    
    logger.info("Starting to fetch reservations from API...")
    
    while True:
        # Build URL with page number (URL encode the filters)
        url = f"{base_url}?page={page}&filters={quote(filters_json)}"
        
        try:
            logger.info(f"Fetching page {page}...")
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            # Extract reservations from current page
            if isinstance(data, dict):
                # Handle paginated response
                if "data" in data:
                    page_reservations = data["data"]
                    page_count = len(page_reservations)
                    all_reservations.extend(page_reservations)
                    
                    # Get pagination metadata
                    current_page = data.get("current_page", page)
                    last_page = data.get("last_page", None)
                    total_records = data.get("total", len(all_reservations))
                    
                    logger.info(f"Page {current_page}: Fetched {page_count} reservations (Total so far: {len(all_reservations)}/{total_records})")
                    
                    # If we've reached the last page, break
                    if last_page is not None and current_page >= last_page:
                        logger.info(f"Reached last page ({last_page}). Fetching complete.")
                        break
                    elif not page_reservations:
                        # No data on this page, we're done
                        logger.info(f"No data on page {page}. Fetching complete.")
                        break
                    
                    page += 1
                elif "success" in data and not data.get("success", True):
                    # API returned an error
                    logger.error(f"API returned error on page {page}")
                    break
                else:
                    # No pagination structure, assume single page
                    if isinstance(data, dict) and any(k in data for k in ["id", "prefixed_id"]):
                        # Single reservation object
                        all_reservations.append(data)
                        logger.info(f"Single reservation fetched (no pagination)")
                    break
            elif isinstance(data, list):
                # If response is directly a list
                page_reservations = data
                page_count = len(page_reservations)
                all_reservations.extend(page_reservations)
                logger.info(f"Page {page}: Fetched {page_count} reservations (Total so far: {len(all_reservations)})")
                # If it's a list, assume no more pages (or check if empty)
                if not page_reservations:
                    logger.info(f"No data on page {page}. Fetching complete.")
                    break
                page += 1
            else:
                logger.warning(f"Unexpected response format on page {page}")
                break
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Page doesn't exist, we're done
                logger.info(f"Page {page} not found (404). Fetching complete.")
                break
            logger.error(f"HTTP error on page {page}: {e.response.status_code} - {e.response.text}")
            raise
    
    logger.info(f"Fetching complete. Total reservations collected: {len(all_reservations)}")
    return all_reservations


def filter_reservation_data(reservation: dict) -> dict:
    """
    Filter reservation data to include only the specified fields.
    Returns a filtered dictionary with only the required fields.
    """
    filtered = {}
    
    # Direct fields (always include, set to None if missing)
    filtered["id"] = reservation.get("id")
    filtered["pick_up_date"] = reservation.get("pick_up_date")
    filtered["total_days"] = reservation.get("total_days")
    filtered["total_price"] = reservation.get("total_price")
    filtered["rental_user_id"] = reservation.get("rental_user_id")
    filtered["pick_up_location_label"] = reservation.get("pick_up_location_label")
    filtered["discounts_amount"] = reservation.get("discounts_amount")
    filtered["status"] = reservation.get("status")
    
    # Nested field: active_vehicle_information.vehicle_class_label
    vehicle_class_label = None
    if "active_vehicle_information" in reservation:
        active_vehicle = reservation["active_vehicle_information"]
        if isinstance(active_vehicle, dict):
            # Check if vehicle_class_label exists directly
            if "vehicle_class_label" in active_vehicle:
                vehicle_class_label = active_vehicle["vehicle_class_label"]
            # Otherwise check in vehicle object
            elif "vehicle" in active_vehicle:
                vehicle = active_vehicle["vehicle"]
                if isinstance(vehicle, dict) and "vehicle_class_label" in vehicle:
                    vehicle_class_label = vehicle["vehicle_class_label"]
    
    if vehicle_class_label is not None:
        filtered["active_vehicle_information"] = {
            "vehicle_class_label": vehicle_class_label
        }
    else:
        filtered["active_vehicle_information"] = {
            "vehicle_class_label": None
        }
    
    # Calculate additional_charge_category totals from all_additional_charges
    additional_charge_totals = {
        "additional_charge_category_1": 0.0,
        "additional_charge_category_2": 0.0,
        "additional_charge_category_3": 0.0,
        "additional_charge_category_4": 0.0
    }
    
    if "all_additional_charges" in reservation and isinstance(reservation["all_additional_charges"], list):
        for charge in reservation["all_additional_charges"]:
            if isinstance(charge, dict):
                category_id = charge.get("additional_charge_category_id")
                pivot = charge.get("pivot", {})
                total_price = pivot.get("total_price", "0.0000000")
                
                if category_id in [1, 2, 3, 4]:
                    # Sum up the total_price for this category
                    try:
                        new_price = float(total_price) if total_price else 0.0
                        additional_charge_totals[f"additional_charge_category_{category_id}"] += new_price
                    except (ValueError, TypeError):
                        pass
    
    # Add the calculated totals (format as string with 7 decimal places to match original format)
    filtered["additional_charge_category_1"] = f"{additional_charge_totals['additional_charge_category_1']:.7f}"
    filtered["additional_charge_category_2"] = f"{additional_charge_totals['additional_charge_category_2']:.7f}"
    filtered["additional_charge_category_3"] = f"{additional_charge_totals['additional_charge_category_3']:.7f}"
    filtered["additional_charge_category_4"] = f"{additional_charge_totals['additional_charge_category_4']:.7f}"
    
    return filtered


@app.get("/")
async def root():
    return {"message": "Hawaii Car Rental API - Filtered Reservations Endpoint"}


@app.get("/reservations")
async def get_reservations(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Comma-separated statuses (e.g., 'rental,completed')")
):
    """
    Get filtered car rental reservations.
    
    Returns only the following fields:
    - id
    - pick_up_date
    - total_days
    - total_price
    - additional_charge_category_1 (sum of pivot.total_price from all_additional_charges where category_id=1)
    - additional_charge_category_2 (sum of pivot.total_price from all_additional_charges where category_id=2)
    - additional_charge_category_3 (sum of pivot.total_price from all_additional_charges where category_id=3)
    - additional_charge_category_4 (sum of pivot.total_price from all_additional_charges where category_id=4)
    - active_vehicle_information.vehicle_class_label
    - rental_user_id
    - pick_up_location_label
    - discounts_amount
    - status
    
    Parameters:
    - start_date: Pick up date start (YYYY-MM-DD)
    - end_date: Pick up date end (YYYY-MM-DD)
    - status: Optional comma-separated statuses (default: 'rental,completed')
    """
    try:
        logger.info(f"API Request - start_date: {start_date}, end_date: {end_date}, status: {status or 'rental,completed'}")
        # Build filters
        filters = [
            {
                "type": "date",
                "column": "pick_up_date",
                "operator": "after",
                "value": start_date
            },
            {
                "type": "date",
                "column": "pick_up_date",
                "operator": "before",
                "value": end_date
            }
        ]
        
        # Add status filter
        if status:
            status_list = [s.strip() for s in status.split(",")]
        else:
            status_list = ["rental", "completed"]
        
        filters.append({
            "type": "string",
            "column": "status",
            "operator": "in_list",
            "value": status_list
        })
        
        # Build filters JSON
        filters_json = json.dumps(filters)
        
        # Prepare headers
        headers = {
            "Authorization": AUTH_TOKEN,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Fetch all pages and combine results
        async with httpx.AsyncClient() as client:
            all_reservations = await fetch_all_pages(client, BASE_URL, headers, filters_json)
        
        # Filter each reservation (always filter to only include specified fields)
        logger.info(f"Filtering {len(all_reservations)} reservations...")
        filtered_data = [filter_reservation_data(res) for res in all_reservations]
        
        logger.info(f"Request complete. Returning {len(filtered_data)} filtered reservations.")
        
        # Return response with metadata
        return JSONResponse(content={
            "success": True,
            "total": len(filtered_data),
            "data": filtered_data
        })
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"API Error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

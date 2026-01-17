"""
External API client for fetching reservations.
"""
import httpx
import json
import logging
from typing import List
from urllib.parse import quote
from config import BASE_URL, AUTH_TOKEN

logger = logging.getLogger(__name__)


async def fetch_all_pages(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    filters_json: str
) -> List[dict]:
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
                    
                    logger.info(
                        f"Page {current_page}: Fetched {page_count} reservations "
                        f"(Total so far: {len(all_reservations)}/{total_records})"
                    )
                    
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
                        logger.info("Single reservation fetched (no pagination)")
                    break
            elif isinstance(data, list):
                # If response is directly a list
                page_reservations = data
                page_count = len(page_reservations)
                all_reservations.extend(page_reservations)
                logger.info(
                    f"Page {page}: Fetched {page_count} reservations "
                    f"(Total so far: {len(all_reservations)})"
                )
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


def build_filters(start_date: str, end_date: str, status: str = None) -> str:
    """
    Build filters JSON string for API request.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        status: Optional comma-separated statuses (default: 'rental,completed')
    
    Returns:
        JSON string of filters
    """
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
    
    return json.dumps(filters)


def get_api_headers() -> dict:
    """Get API request headers."""
    return {
        "Authorization": AUTH_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

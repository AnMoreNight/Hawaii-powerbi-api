"""
API routes/endpoints for the application.
"""
from fastapi import Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import httpx
import logging

from api_client import fetch_all_pages, build_filters, get_api_headers, BASE_URL, fetch_available_agents, fetch_single_page
from data_processor import filter_reservation_data
from mongo_database import get_reservations_collection
from datetime import datetime, timedelta, timezone
from pymongo import UpdateOne
import json

logger = logging.getLogger(__name__)


async def get_reservations_route(
    start_date: str,
    end_date: str,
    status: Optional[str] = None
):
    """
    Get filtered car rental reservations from external API.
    
    Returns only the following fields:
    - id, pick_up_date, total_days, total_price
    - additional_charge_category_1/2/3/4
    - active_vehicle_information.vehicle_class_label
    - rental_user_name, pick_up_location_label, discounts_amount, status
    """
    try:
        logger.info(
            f"API Request - start_date: {start_date}, end_date: {end_date}, "
            f"status: {status or 'rental,completed'}"
        )
        
        # Build filters and headers
        filters_json = build_filters(start_date, end_date, status)
        headers = get_api_headers()
        
        # Fetch all pages and combine results
        async with httpx.AsyncClient() as client:
            # Fetch available agents for rental_user_name mapping
            agent_mapping = await fetch_available_agents(client)
            
            # Fetch reservations
            all_reservations = await fetch_all_pages(client, BASE_URL, headers, filters_json)
        
        # Filter each reservation
        logger.info(f"Filtering {len(all_reservations)} reservations...")
        filtered_data = [filter_reservation_data(res, agent_mapping) for res in all_reservations]
        
        logger.info(f"Request complete. Returning {len(filtered_data)} filtered reservations.")
        
        # Return response with metadata
        return JSONResponse(content={
            "success": True,
            "total": len(filtered_data),
            "data": filtered_data
        })
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"API Error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error in get_reservations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


async def sync_reservations_route(
    start_date: str,
    end_date: str,
    status: Optional[str] = None
):
    """
    Sync reservations from external API to database.
    Processes pages incrementally to avoid memory issues.
    Implements upsert logic:
    - If ID exists: update all fields with new values (replace, not merge)
    - If ID doesn't exist: insert new record
    """
    try:
        logger.info(
            f"Sync Request - start_date: {start_date}, end_date: {end_date}, "
            f"status: {status or 'rental,completed'}"
        )
        
        # Build filters and headers
        filters_json = build_filters(start_date, end_date, status)
        headers = get_api_headers()

        # Initialize counters
        inserted_count = 0
        updated_count = 0
        error_count = 0
        total_processed = 0

        # Prepare MongoDB collection and timestamp
        reservations_collection = await get_reservations_collection()
        now_utc = datetime.now(timezone.utc).isoformat()

        # File-based buffer (NDJSON: one JSON object per line)
        buffer_file = "sync_buffer.jsonl"
        # Reset buffer file at start
        try:
            with open(buffer_file, "w", encoding="utf-8"):
                pass
            logger.info(f"Buffer file reset: {buffer_file}")
        except Exception as reset_error:
            logger.warning(f"Failed to reset buffer file {buffer_file}: {reset_error}")

        # Fetch available agents for rental_user_name mapping (once at the start)
        async with httpx.AsyncClient() as client:
            logger.info("Fetching available agents...")
            agent_mapping = await fetch_available_agents(client)

            # Process pages incrementally
            page = 1
            last_page = None

            logger.info("Starting incremental page-by-page sync (MongoDB)...")

            while True:
                # Fetch single page
                logger.info(f"Fetching page {page}...")
                page_reservations, current_page, fetched_last_page = await fetch_single_page(
                    client, BASE_URL, headers, filters_json, page
                )

                # Update last_page if we got it from API
                if fetched_last_page is not None:
                    last_page = fetched_last_page

                # If no reservations on this page, we're done
                if not page_reservations:
                    logger.info(f"No data on page {page}. Sync complete.")
                    break

                # Process this page's reservations and write to buffer file
                logger.info(f"Buffering {len(page_reservations)} reservations from page {current_page}...")

                page_filtered: list[dict] = []

                for reservation in page_reservations:
                    try:
                        # Filter reservation data
                        reservation_data = filter_reservation_data(reservation, agent_mapping)

                        reservation_id = reservation_data.get("id")
                        if not reservation_id:
                            logger.warning("Skipping reservation without ID")
                            error_count += 1
                            continue

                        # Set/update timestamps (will be used for bulk insert)
                        reservation_data["updated_at"] = now_utc
                        reservation_data.setdefault("created_at", now_utc)

                        page_filtered.append(reservation_data)
                        total_processed += 1

                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error buffering reservation {reservation.get('id')}: {str(e)}")
                        logger.error(f"Error type: {type(e).__name__}")
                        continue

                # Append this page's filtered reservations to buffer file as NDJSON
                if page_filtered:
                    try:
                        with open(buffer_file, "a", encoding="utf-8") as f:
                            for doc in page_filtered:
                                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                        logger.info(f"Appended {len(page_filtered)} reservations to {buffer_file}")
                    except Exception as write_error:
                        logger.warning(f"Failed to write to buffer file {buffer_file}: {write_error}")

                # Check if we've reached the last page
                if last_page is not None and current_page >= last_page:
                    logger.info(f"Reached last page ({last_page}). Sync complete.")
                    break

                # Move to next page
                page += 1

                # Safety check: prevent infinite loops
                if page > 10000:
                    logger.warning("Reached maximum page limit (10000). Stopping.")
                    break

        # Read buffer file and bulk upsert into MongoDB
        logger.info(f"Reading buffered reservations from {buffer_file} for bulk upsert...")

        operations = []
        buffered_count = 0

        try:
            with open(buffer_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        doc = json.loads(line)
                    except json.JSONDecodeError as decode_error:
                        logger.warning(f"Skipping invalid JSON line in buffer: {decode_error}")
                        continue

                    reservation_id = doc.get("id")
                    if not reservation_id:
                        continue

                    operations.append(
                        UpdateOne(
                            {"id": reservation_id},
                            {
                                "$set": doc,
                                "$setOnInsert": {"created_at": doc.get("created_at", now_utc)},
                            },
                            upsert=True,
                        )
                    )
                    buffered_count += 1

            logger.info(f"Prepared {buffered_count} buffered reservations for bulk upsert")
        except FileNotFoundError:
            logger.warning(f"Buffer file {buffer_file} not found; nothing to upsert")
        except Exception as read_error:
            logger.error(f"Error reading buffer file {buffer_file}: {read_error}")

        if operations:
            try:
                result = await reservations_collection.bulk_write(operations, ordered=False)
                inserted_count = len(result.upserted_ids)
                # matched_count includes both updated and matched w/o change; approximate updated:
                updated_count = result.matched_count
                logger.info(
                    f"Bulk upsert completed. Inserted: {inserted_count}, "
                    f"Matched/Updated: {updated_count}"
                )
            except Exception as bulk_error:
                logger.error(f"Bulk upsert error: {bulk_error}")
                error_count += 1

        logger.info("=" * 60)
        logger.info(f"Sync completed successfully!")
        logger.info(f"Total processed (buffered): {total_processed}")
        logger.info(f"  - Inserted (bulk): {inserted_count}")
        logger.info(f"  - Updated (bulk matched): {updated_count}")
        logger.info(f"  - Errors: {error_count}")
        logger.info("=" * 60)

        return JSONResponse(content={
            "success": True,
            "message": "Sync completed successfully",
            "total_processed": total_processed,
            "inserted": inserted_count,
            "updated": updated_count,
            "errors": error_count
        })
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"API Error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


async def get_powerbi_data_route():
    """
    Get all reservation data from MongoDB for Power BI.
    Automatically syncs last 60 days of data before returning results.
    Returns all reservations stored in the database.
    """
    try:
        # Calculate date range: last 60 days from today
        today = datetime.now().date()
        start_date = today - timedelta(days=60)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = today.strftime("%Y-%m-%d")

        logger.info(
            f"Power BI request - Syncing data from {start_date_str} to {end_date_str} (last 60 days)..."
        )

        # Call sync API internally first
        try:
            await sync_reservations_route(start_date_str, end_date_str)
            logger.info("✅ Sync completed before Power BI data retrieval")
        except Exception as sync_error:
            logger.warning(f"⚠️  Sync failed before Power BI retrieval: {str(sync_error)}")
            logger.warning("⚠️  Continuing with existing MongoDB data...")

        logger.info("Power BI data request - fetching all reservations from MongoDB...")

        reservations_collection = await get_reservations_collection()
        cursor = reservations_collection.find({})

        data = []
        async for doc in cursor:
            # Remove internal MongoDB _id
            doc.pop("_id", None)
            data.append(doc)

        logger.info(f"Power BI data request complete. Returning {len(data)} reservations.")

        return JSONResponse(content={
            "success": True,
            "total": len(data),
            "data": data
        })

    except Exception as db_error:
        error_msg = str(db_error)
        logger.error(f"Database error in Power BI endpoint: {error_msg}")
        raise HTTPException(
            status_code=503,
            detail=(
                "Database connection failed. Please check your MONGODB_URI. "
                f"Error: {error_msg}"
            )
        )



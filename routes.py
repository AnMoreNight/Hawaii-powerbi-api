"""
API routes/endpoints for the application.
"""
from fastapi import Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
import httpx
import logging
import asyncio
import os
from datetime import datetime, timedelta, timezone

from api_client import fetch_all_pages, build_filters, get_api_headers, BASE_URL, fetch_available_agents, fetch_single_page
from data_processor import filter_reservation_data
from mongo_database import get_reservations_collection
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
import json

logger = logging.getLogger(__name__)

# Sync lock and cache to prevent duplicate syncs when multiple requests come in quickly
_sync_lock = asyncio.Lock()
_last_sync_time: Optional[datetime] = None
_sync_in_progress = False
SYNC_CACHE_MINUTES = 5  # Skip sync if last sync was within this many minutes


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
        total_pages_fetched = 0

        # Prepare MongoDB collection and timestamp
        reservations_collection = await get_reservations_collection()
        now_utc = datetime.now(timezone.utc).isoformat()

        # File-based buffer (NDJSON: one JSON object per line)
        # Use /tmp for Vercel serverless (read-only filesystem except /tmp)
        tmp_dir = os.getenv("TMPDIR", "/tmp")
        buffer_file = os.path.join(tmp_dir, "sync_buffer.jsonl")
        # Reset buffer file at start
        try:
            with open(buffer_file, "w", encoding="utf-8"):
                pass
            logger.info(f"Buffer file reset: {buffer_file}")
        except Exception as reset_error:
            logger.warning(f"Failed to reset buffer file {buffer_file}: {reset_error}")

        # Fetch available agents for rental_user_name mapping (once at the start)
        # Note: "agents" are rental staff/users - used to map rental_user_id -> full_name
        async with httpx.AsyncClient() as client:
            logger.info("Fetching rental user agents (for rental_user_name mapping)...")
            agent_mapping = await fetch_available_agents(client)
            logger.info(f"Loaded {len(agent_mapping)} rental user agents for name mapping")

            # Process pages incrementally
            page = 1
            last_page = None
            total_pages_fetched = 0

            logger.info("Starting incremental page-by-page sync (MongoDB)...")

            while True:
                # Fetch single page
                logger.info(f"Fetching reservations page {page}...")
                page_reservations, current_page, fetched_last_page = await fetch_single_page(
                    client, BASE_URL, headers, filters_json, page
                )

                # Update last_page if we got it from API
                if fetched_last_page is not None:
                    last_page = fetched_last_page
                    logger.info(f"API reports total pages: {last_page}")

                # If no reservations on this page, we're done
                if not page_reservations:
                    logger.info(f"No data on page {page}. Sync complete.")
                    break

                total_pages_fetched += 1
                logger.info(
                    f"Page {current_page}/{last_page if last_page else '?'}: "
                    f"Fetched {len(page_reservations)} reservations "
                    f"(Total pages fetched so far: {total_pages_fetched})"
                )

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
                    logger.info(
                        f"Reached last page ({last_page}/{last_page}). "
                        f"Total pages fetched: {total_pages_fetched}. Sync complete."
                    )
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
                    except json.JSONDecodeError:
                        # Skip invalid JSON lines silently
                        continue

                    reservation_id = doc.get("id")
                    if not reservation_id:
                        continue

                    # Extract created_at so we don't set the same field in both $set and $setOnInsert
                    created_at_value = doc.pop("created_at", None)

                    update_doc = {"$set": doc}
                    if created_at_value:
                        update_doc["$setOnInsert"] = {"created_at": created_at_value}

                    operations.append(
                        UpdateOne(
                            {"id": reservation_id},
                            update_doc,
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
            except BulkWriteError as bulk_error:
                # Avoid dumping full operation details (which include buffer JSON)
                details = bulk_error.details or {}
                write_errors = details.get("writeErrors", [])
                if write_errors:
                    first = write_errors[0]
                    code = first.get("code")
                    msg = first.get("errmsg")
                    logger.error(f"Bulk upsert error (first): code={code}, msg={msg}")
                else:
                    logger.error("Bulk upsert error with no writeErrors details")
                error_count += 1

        logger.info("=" * 60)
        logger.info(f"Sync completed successfully!")
        logger.info(f"Total pages fetched: {total_pages_fetched}")
        logger.info(f"Total reservations processed (buffered): {total_processed}")
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
    Uses sync cache to prevent duplicate syncs when multiple requests come in quickly.
    Returns all reservations stored in the database.
    Uses streaming to avoid memory issues with large datasets.
    """
    global _last_sync_time, _sync_in_progress
    
    try:
        # Calculate date range: last 60 days from today
        today = datetime.now().date()
        start_date = today - timedelta(days=60)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = today.strftime("%Y-%m-%d")

        # Check if we should skip sync (recent sync completed)
        should_sync = True
        now = datetime.now(timezone.utc)
        
        if _last_sync_time is not None:
            time_since_sync = (now - _last_sync_time).total_seconds() / 60
            if time_since_sync < SYNC_CACHE_MINUTES:
                should_sync = False
                logger.info(
                    f"Power BI request - Skipping sync (last sync was {time_since_sync:.1f} minutes ago, "
                    f"cache: {SYNC_CACHE_MINUTES} minutes)"
                )
        
        # Sync last 60 days before returning data (with lock to prevent concurrent syncs)
        if should_sync:
            async with _sync_lock:
                # Double-check after acquiring lock (another request might have synced)
                if _last_sync_time is not None:
                    time_since_sync = (datetime.now(timezone.utc) - _last_sync_time).total_seconds() / 60
                    if time_since_sync < SYNC_CACHE_MINUTES:
                        should_sync = False
                        logger.info("Another request already synced, skipping duplicate sync")
                
                if should_sync and not _sync_in_progress:
                    _sync_in_progress = True
                    try:
                        logger.info(
                            f"Power BI request - Syncing data from {start_date_str} to {end_date_str} (last 60 days)..."
                        )
                        await sync_reservations_route(start_date_str, end_date_str)
                        _last_sync_time = datetime.now(timezone.utc)
                        logger.info("✅ Sync completed before Power BI data retrieval")
                    except Exception as sync_error:
                        logger.warning(f"⚠️  Sync failed before Power BI retrieval: {str(sync_error)}")
                        logger.warning("⚠️  Continuing with existing MongoDB data...")
                    finally:
                        _sync_in_progress = False
                elif _sync_in_progress:
                    logger.info("Sync already in progress from another request, waiting for it to complete...")
                    # Wait a bit for the other sync to complete
                    await asyncio.sleep(1)
                    # Check again
                    if _last_sync_time is not None:
                        time_since_sync = (datetime.now(timezone.utc) - _last_sync_time).total_seconds() / 60
                        if time_since_sync < SYNC_CACHE_MINUTES:
                            logger.info("Sync completed by another request, proceeding with data retrieval")

        logger.info("Power BI data request - streaming all reservations from MongoDB...")

        reservations_collection = await get_reservations_collection()
        cursor = reservations_collection.find({})

        async def generate_json_stream():
            """Generator that streams JSON data without loading everything into memory."""
            count = 0
            yield '{"success":true,"data":['  # Start JSON response
            
            first_item = True
            async for doc in cursor:
                # Remove internal MongoDB _id
                doc.pop("_id", None)
                
                if not first_item:
                    yield ','
                first_item = False
                
                # Stream each document as JSON
                yield json.dumps(doc, ensure_ascii=False)
                count += 1
                
                # Yield control periodically to avoid blocking
                if count % 10000 == 0:
                    await asyncio.sleep(0)  # Yield to event loop
                    logger.info(f"Streamed {count} documents so far...")
            
            yield f'],"total":{count}}}'  # End JSON response
            logger.info(f"Power BI data streaming complete. Streamed {count} reservations.")

        return StreamingResponse(
            generate_json_stream(),
            media_type="application/json",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )

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



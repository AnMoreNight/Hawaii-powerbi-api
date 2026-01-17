"""
API routes/endpoints for the application.
"""
from fastapi import Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import httpx
import logging

from api_client import fetch_all_pages, build_filters, get_api_headers, BASE_URL
from data_processor import filter_reservation_data
from database import async_session_maker
from db_operations import upsert_reservation, get_reservations, reservation_to_dict
from models import Reservation
from sqlalchemy import select

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
    - rental_user_id, pick_up_location_label, discounts_amount, status
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
            all_reservations = await fetch_all_pages(client, BASE_URL, headers, filters_json)
        
        # Filter each reservation
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
        
        # Fetch all pages and combine results
        async with httpx.AsyncClient() as client:
            all_reservations = await fetch_all_pages(client, BASE_URL, headers, filters_json)
        
        # Filter each reservation
        logger.info(f"Filtering {len(all_reservations)} reservations...")
        filtered_data = [filter_reservation_data(res) for res in all_reservations]
        
        # Upsert to database
        logger.info(f"Syncing {len(filtered_data)} reservations to database...")
        async with async_session_maker() as session:
            inserted_count = 0
            updated_count = 0
            
            for reservation_data in filtered_data:
                try:
                    reservation_id = reservation_data.get("id")
                    if not reservation_id:
                        logger.warning("Skipping reservation without ID")
                        continue
                    
                    # Check if exists before upsert
                    result = await session.execute(
                        select(Reservation).where(Reservation.id == reservation_id)
                    )
                    existed = result.scalar_one_or_none() is not None
                    
                    await upsert_reservation(session, reservation_data)
                    
                    if existed:
                        updated_count += 1
                    else:
                        inserted_count += 1
                        
                except Exception as e:
                    logger.error(f"Error upserting reservation {reservation_data.get('id')}: {str(e)}")
                    await session.rollback()
                    continue
        
        logger.info(f"Sync complete. Inserted: {inserted_count}, Updated: {updated_count}")
        
        return JSONResponse(content={
            "success": True,
            "message": "Sync completed successfully",
            "total_processed": len(filtered_data),
            "inserted": inserted_count,
            "updated": updated_count
        })
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"API Error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


async def get_powerbi_data_route(
    limit: int = 1000,
    offset: int = 0
):
    """
    Get reservations from database for Power BI.
    Returns data in a format optimized for Power BI consumption.
    """
    try:
        async with async_session_maker() as session:
            reservations, total_count = await get_reservations(session, limit, offset)
            
            # Convert to dict format
            data = [reservation_to_dict(res) for res in reservations]
            
            return JSONResponse(content={
                "success": True,
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "data": data
            })
    
    except Exception as e:
        logger.error(f"Power BI data fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

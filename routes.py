"""
API routes/endpoints for the application.
"""
from fastapi import Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import httpx
import logging

from api_client import fetch_all_pages, build_filters, get_api_headers, BASE_URL, fetch_available_agents
from data_processor import filter_reservation_data
from database import async_session_maker
from db_operations import upsert_reservation
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
            # Fetch available agents for rental_user_name mapping
            agent_mapping = await fetch_available_agents(client)
            
            # Fetch reservations
            all_reservations = await fetch_all_pages(client, BASE_URL, headers, filters_json)
        
        # Filter each reservation
        logger.info(f"Filtering {len(all_reservations)} reservations...")
        filtered_data = [filter_reservation_data(res, agent_mapping) for res in all_reservations]
        
        # Upsert to database
        logger.info(f"Syncing {len(filtered_data)} reservations to database...")
        try:
            async with async_session_maker() as session:
                inserted_count = 0
                updated_count = 0
                error_count = 0
                
                total_to_process = len(filtered_data)
                for index, reservation_data in enumerate(filtered_data, 1):
                    try:
                        reservation_id = reservation_data.get("id")
                        if not reservation_id:
                            logger.warning("Skipping reservation without ID")
                            error_count += 1
                            continue
                        
                        # Check if exists before upsert (for counting)
                        result = await session.execute(
                            select(Reservation).where(Reservation.id == reservation_id)
                        )
                        existed = result.scalar_one_or_none() is not None
                        
                        # Upsert reservation (logs insert/update inside function)
                        await upsert_reservation(session, reservation_data)
                        
                        # Commit after each upsert (or batch commits)
                        await session.commit()
                        
                        if existed:
                            updated_count += 1
                        else:
                            inserted_count += 1
                        
                        # Log progress every 100 records
                        if index % 100 == 0:
                            logger.info(f"Progress: {index}/{total_to_process} processed (Inserted: {inserted_count}, Updated: {updated_count}, Errors: {error_count})")
                            
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error upserting reservation {reservation_data.get('id')}: {str(e)}")
                        logger.error(f"Error type: {type(e).__name__}")
                        try:
                            await session.rollback()
                        except Exception as rollback_error:
                            logger.error(f"Rollback error: {rollback_error}")
                        continue
                
                logger.info("=" * 60)
                logger.info(f"Sync completed successfully!")
                logger.info(f"Total processed: {len(filtered_data)}")
                logger.info(f"  - Inserted: {inserted_count}")
                logger.info(f"  - Updated: {updated_count}")
                logger.info(f"  - Errors: {error_count}")
                logger.info("=" * 60)
                
                return JSONResponse(content={
                    "success": True,
                    "message": "Sync completed successfully",
                    "total_processed": len(filtered_data),
                    "inserted": inserted_count,
                    "updated": updated_count,
                    "errors": error_count
                })
        except Exception as db_error:
            error_msg = str(db_error)
            logger.error(f"Database connection error: {error_msg}")
            raise HTTPException(
                status_code=503,
                detail=(
                    "Database connection failed. Please check your DATABASE_URL. "
                    f"Error: {error_msg}"
                )
            )
    
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
    Get all reservation data from database for Power BI.
    Returns all reservations stored in the database.
    """
    try:
        logger.info("Power BI data request - fetching all reservations from database...")
        
        async with async_session_maker() as session:
            # Fetch all reservations from database
            result = await session.execute(select(Reservation))
            reservations = result.scalars().all()
            
            # Convert SQLAlchemy models to dictionaries
            data = []
            for reservation in reservations:
                reservation_dict = {
                    "id": reservation.id,
                    "pick_up_date": reservation.pick_up_date.isoformat() if reservation.pick_up_date else None,
                    "total_days": reservation.total_days,
                    "total_price": float(reservation.total_price) if reservation.total_price is not None else None,
                    "rental_user_name": reservation.rental_user_name,
                    "pick_up_location_label": reservation.pick_up_location_label,
                    "discounts_amount": float(reservation.discounts_amount) if reservation.discounts_amount is not None else None,
                    "status": reservation.status,
                    "vehicle_class_label": reservation.vehicle_class_label,
                    "additional_charge_category_1": float(reservation.additional_charge_category_1) if reservation.additional_charge_category_1 is not None else 0.0,
                    "additional_charge_category_2": float(reservation.additional_charge_category_2) if reservation.additional_charge_category_2 is not None else 0.0,
                    "additional_charge_category_3": float(reservation.additional_charge_category_3) if reservation.additional_charge_category_3 is not None else 0.0,
                    "additional_charge_category_4": float(reservation.additional_charge_category_4) if reservation.additional_charge_category_4 is not None else 0.0,
                    "created_at": reservation.created_at.isoformat() if reservation.created_at else None,
                    "updated_at": reservation.updated_at.isoformat() if reservation.updated_at else None,
                }
                data.append(reservation_dict)
            
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
                "Database connection failed. Please check your DATABASE_URL. "
                f"Error: {error_msg}"
            )
        )



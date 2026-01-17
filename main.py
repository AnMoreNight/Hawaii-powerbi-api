"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from config import LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT
from database import init_db, close_db
from routes import (
    get_reservations_route,
    sync_reservations_route,
    get_powerbi_data_route
)

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Hawaii Car Rental API",
    description="Filtered API for car rental reservations"
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await init_db()


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown."""
    await close_db()


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Hawaii Car Rental API - Filtered Reservations Endpoint"}


@app.get("/reservations")
async def get_reservations(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Comma-separated statuses (e.g., 'rental,completed')")
):
    """
    Get filtered car rental reservations from external API.
    
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
    return await get_reservations_route(start_date, end_date, status)


@app.post("/sync")
async def sync_reservations(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Comma-separated statuses (e.g., 'rental,completed')")
):
    """
    Sync reservations from external API to database.
    Implements upsert logic:
    - If ID exists: update all fields with new values (replace, not merge)
    - If ID doesn't exist: insert new record
    
    Parameters:
    - start_date: Pick up date start (YYYY-MM-DD)
    - end_date: Pick up date end (YYYY-MM-DD)
    - status: Optional comma-separated statuses (default: 'rental,completed')
    """
    return await sync_reservations_route(start_date, end_date, status)


@app.get("/powerbi")
async def get_powerbi_data(
    limit: Optional[int] = Query(1000, description="Maximum number of records to return"),
    offset: Optional[int] = Query(0, description="Number of records to skip")
):
    """
    Get reservations from database for Power BI.
    Returns data in a format optimized for Power BI consumption.
    
    Parameters:
    - limit: Maximum number of records (default: 1000)
    - offset: Number of records to skip (default: 0)
    """
    return await get_powerbi_data_route(limit, offset)


if __name__ == "__main__":
    import uvicorn
    import os
    # Use PORT from environment (for cloud platforms) or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

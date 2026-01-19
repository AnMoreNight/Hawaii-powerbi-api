"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from typing import Optional
from contextlib import asynccontextmanager
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="Hawaii Car Rental API",
    description="Filtered API for car rental reservations",
    lifespan=lifespan
)


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
async def get_powerbi_data():
    """
    Get all reservation data from database for Power BI.
    
    Returns all reservations stored in the database with the following fields:
    - id
    - pick_up_date
    - total_days
    - total_price
    - rental_user_id
    - pick_up_location_label
    - discounts_amount
    - status
    - vehicle_class_label
    - additional_charge_category_1
    - additional_charge_category_2
    - additional_charge_category_3
    - additional_charge_category_4
    - created_at
    - updated_at
    """
    return await get_powerbi_data_route()


if __name__ == "__main__":
    import uvicorn
    import os
    # Use PORT from environment (for cloud platforms) or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

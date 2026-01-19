"""
Database operations for reservations.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import logging

from models import Reservation

logger = logging.getLogger(__name__)


def _parse_float_or_default(value, default=0.0):
    """Parse a value to float, returning default if parsing fails."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_reservation_data(reservation_data: dict) -> dict:
    """
    Parse and extract reservation data from dictionary.
    
    Args:
        reservation_data: Raw reservation data dictionary
    
    Returns:
        Parsed data dictionary with proper types
    """
    # Parse pick_up_date - ensure timezone-aware (UTC)
    pick_up_date = None
    if reservation_data.get("pick_up_date"):
        try:
            date_str = reservation_data["pick_up_date"]
            # Parse datetime
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            
            # Ensure timezone-aware (convert to UTC if timezone-naive)
            if dt.tzinfo is None:
                # If no timezone info, assume UTC
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC if timezone-aware
                dt = dt.astimezone(timezone.utc)
            
            pick_up_date = dt
        except Exception as e:
            logger.warning(f"Failed to parse pick_up_date '{reservation_data.get('pick_up_date')}': {e}")
    
    # Extract vehicle_class_label
    vehicle_class_label = None
    if reservation_data.get("active_vehicle_information"):
        vehicle_info = reservation_data["active_vehicle_information"]
        if isinstance(vehicle_info, dict):
            vehicle_class_label = vehicle_info.get("vehicle_class_label")
    
    # Parse total_days - ensure it's an integer or None
    total_days = reservation_data.get("total_days")
    if total_days is not None:
        try:
            total_days = int(total_days)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse total_days '{total_days}', setting to None")
            total_days = None
    
    # Parse rental_user_id - ensure it's an integer or None
    rental_user_id = reservation_data.get("rental_user_id")
    if rental_user_id is not None:
        try:
            rental_user_id = int(rental_user_id)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse rental_user_id '{rental_user_id}', setting to None")
            rental_user_id = None
    
    # Parse total_price - ensure it's a float (or None)
    total_price = reservation_data.get("total_price")
    if total_price is not None:
        try:
            total_price = float(total_price)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse total_price '{total_price}', setting to None")
            total_price = None
    
    # Parse discounts_amount - ensure it's a float (or None)
    discounts_amount = reservation_data.get("discounts_amount")
    if discounts_amount is not None:
        try:
            discounts_amount = float(discounts_amount)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse discounts_amount '{discounts_amount}', setting to None")
            discounts_amount = None
    
    # Ensure pick_up_location_label is a string (or None)
    pick_up_location_label = reservation_data.get("pick_up_location_label")
    if pick_up_location_label is not None:
        pick_up_location_label = str(pick_up_location_label)
    
    # Ensure status is a string (or None)
    status = reservation_data.get("status")
    if status is not None:
        status = str(status)
    
    # Ensure vehicle_class_label is a string (or None)
    if vehicle_class_label is not None:
        vehicle_class_label = str(vehicle_class_label)
    
    return {
        "pick_up_date": pick_up_date,
        "vehicle_class_label": vehicle_class_label,
        "total_days": total_days,
        "total_price": total_price,
        "rental_user_id": rental_user_id,
        "pick_up_location_label": pick_up_location_label,
        "discounts_amount": discounts_amount,
        "status": status,
        "additional_charge_category_1": _parse_float_or_default(reservation_data.get("additional_charge_category_1"), 0.0),
        "additional_charge_category_2": _parse_float_or_default(reservation_data.get("additional_charge_category_2"), 0.0),
        "additional_charge_category_3": _parse_float_or_default(reservation_data.get("additional_charge_category_3"), 0.0),
        "additional_charge_category_4": _parse_float_or_default(reservation_data.get("additional_charge_category_4"), 0.0),
    }


async def upsert_reservation(session: AsyncSession, reservation_data: dict) -> Reservation:
    """
    Upsert a reservation: update if exists, insert if not.
    When updating, replaces all fields with new values (no merging/addition).
    
    Note: This function does NOT commit - caller must handle transaction.
    
    Args:
        session: Database session
        reservation_data: Reservation data dictionary
    
    Returns:
        Reservation model instance
    """
    reservation_id = reservation_data.get("id")
    if not reservation_id:
        raise ValueError("Reservation ID is required")
    
    # Parse reservation data
    parsed_data = _parse_reservation_data(reservation_data)
    
    # Try to get existing reservation
    result = await session.execute(select(Reservation).where(Reservation.id == reservation_id))
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing reservation - replace all fields with new values
        status = parsed_data.get('status', 'N/A')
        pick_up = parsed_data.get('pick_up_date')
        pick_up_str = pick_up.strftime('%Y-%m-%d %H:%M') if pick_up else 'N/A'
        logger.info(f"[UPDATE] Reservation ID: {reservation_id} | Status: {status} | Pick-up: {pick_up_str}")
        
        existing.pick_up_date = parsed_data["pick_up_date"]
        existing.total_days = parsed_data["total_days"]
        existing.total_price = parsed_data["total_price"]
        existing.rental_user_id = parsed_data["rental_user_id"]
        existing.pick_up_location_label = parsed_data["pick_up_location_label"]
        existing.discounts_amount = parsed_data["discounts_amount"]
        existing.status = parsed_data["status"]
        existing.vehicle_class_label = parsed_data["vehicle_class_label"]
        existing.additional_charge_category_1 = parsed_data["additional_charge_category_1"]
        existing.additional_charge_category_2 = parsed_data["additional_charge_category_2"]
        existing.additional_charge_category_3 = parsed_data["additional_charge_category_3"]
        existing.additional_charge_category_4 = parsed_data["additional_charge_category_4"]
        existing.updated_at = datetime.now(timezone.utc)
        
        # Don't commit here - let caller handle transaction
        return existing
    else:
        # Insert new reservation
        status = parsed_data.get('status', 'N/A')
        pick_up = parsed_data.get('pick_up_date')
        pick_up_str = pick_up.strftime('%Y-%m-%d %H:%M') if pick_up else 'N/A'
        logger.info(f"[INSERT] Reservation ID: {reservation_id} | Status: {status} | Pick-up: {pick_up_str}")
        
        new_reservation = Reservation(
            id=reservation_id,
            pick_up_date=parsed_data["pick_up_date"],
            total_days=parsed_data["total_days"],
            total_price=parsed_data["total_price"],
            rental_user_id=parsed_data["rental_user_id"],
            pick_up_location_label=parsed_data["pick_up_location_label"],
            discounts_amount=parsed_data["discounts_amount"],
            status=parsed_data["status"],
            vehicle_class_label=parsed_data["vehicle_class_label"],
            additional_charge_category_1=parsed_data["additional_charge_category_1"],
            additional_charge_category_2=parsed_data["additional_charge_category_2"],
            additional_charge_category_3=parsed_data["additional_charge_category_3"],
            additional_charge_category_4=parsed_data["additional_charge_category_4"],
        )
        
        session.add(new_reservation)
        # Don't commit here - let caller handle transaction
        return new_reservation



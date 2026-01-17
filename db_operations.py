"""
Database operations for reservations.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import logging

from models import Reservation

logger = logging.getLogger(__name__)


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
    
    return {
        "pick_up_date": pick_up_date,
        "vehicle_class_label": vehicle_class_label,
        "total_days": reservation_data.get("total_days"),
        "total_price": reservation_data.get("total_price"),
        "rental_user_id": reservation_data.get("rental_user_id"),
        "pick_up_location_label": reservation_data.get("pick_up_location_label"),
        "discounts_amount": reservation_data.get("discounts_amount"),
        "status": reservation_data.get("status"),
        "additional_charge_category_1": reservation_data.get("additional_charge_category_1", "0.0000000"),
        "additional_charge_category_2": reservation_data.get("additional_charge_category_2", "0.0000000"),
        "additional_charge_category_3": reservation_data.get("additional_charge_category_3", "0.0000000"),
        "additional_charge_category_4": reservation_data.get("additional_charge_category_4", "0.0000000"),
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
        logger.debug(f"Updating existing reservation ID: {reservation_id}")
        
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
        logger.debug(f"Inserting new reservation ID: {reservation_id}")
        
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



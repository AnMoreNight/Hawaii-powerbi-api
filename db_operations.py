"""
Database operations for reservations.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional, List, Dict
import logging

from models import Reservation

logger = logging.getLogger(__name__)


async def upsert_reservation(session: AsyncSession, reservation_data: dict) -> Reservation:
    """
    Upsert a reservation: update if exists, insert if not.
    When updating, replaces all fields with new values (no merging/addition).
    
    Args:
        session: Database session
        reservation_data: Reservation data dictionary
    
    Returns:
        Reservation model instance
    """
    reservation_id = reservation_data.get("id")
    
    # Try to get existing reservation
    result = await session.execute(select(Reservation).where(Reservation.id == reservation_id))
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing reservation - replace all fields with new values
        logger.info(f"Updating existing reservation ID: {reservation_id}")
        
        # Parse pick_up_date
        pick_up_date = None
        if reservation_data.get("pick_up_date"):
            try:
                pick_up_date = datetime.fromisoformat(
                    reservation_data["pick_up_date"].replace("Z", "+00:00")
                )
            except Exception:
                pass
        
        # Extract vehicle_class_label
        vehicle_class_label = None
        if reservation_data.get("active_vehicle_information"):
            vehicle_class_label = reservation_data["active_vehicle_information"].get("vehicle_class_label")
        
        # Update all fields with new values
        existing.pick_up_date = pick_up_date
        existing.total_days = reservation_data.get("total_days")
        existing.total_price = reservation_data.get("total_price")
        existing.rental_user_id = reservation_data.get("rental_user_id")
        existing.pick_up_location_label = reservation_data.get("pick_up_location_label")
        existing.discounts_amount = reservation_data.get("discounts_amount")
        existing.status = reservation_data.get("status")
        existing.vehicle_class_label = vehicle_class_label
        existing.additional_charge_category_1 = reservation_data.get("additional_charge_category_1", "0.0000000")
        existing.additional_charge_category_2 = reservation_data.get("additional_charge_category_2", "0.0000000")
        existing.additional_charge_category_3 = reservation_data.get("additional_charge_category_3", "0.0000000")
        existing.additional_charge_category_4 = reservation_data.get("additional_charge_category_4", "0.0000000")
        existing.updated_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(existing)
        return existing
    else:
        # Insert new reservation
        logger.info(f"Inserting new reservation ID: {reservation_id}")
        
        pick_up_date = None
        if reservation_data.get("pick_up_date"):
            try:
                pick_up_date = datetime.fromisoformat(
                    reservation_data["pick_up_date"].replace("Z", "+00:00")
                )
            except Exception:
                pass
        
        vehicle_class_label = None
        if reservation_data.get("active_vehicle_information"):
            vehicle_class_label = reservation_data["active_vehicle_information"].get("vehicle_class_label")
        
        new_reservation = Reservation(
            id=reservation_id,
            pick_up_date=pick_up_date,
            total_days=reservation_data.get("total_days"),
            total_price=reservation_data.get("total_price"),
            rental_user_id=reservation_data.get("rental_user_id"),
            pick_up_location_label=reservation_data.get("pick_up_location_label"),
            discounts_amount=reservation_data.get("discounts_amount"),
            status=reservation_data.get("status"),
            vehicle_class_label=vehicle_class_label,
            additional_charge_category_1=reservation_data.get("additional_charge_category_1", "0.0000000"),
            additional_charge_category_2=reservation_data.get("additional_charge_category_2", "0.0000000"),
            additional_charge_category_3=reservation_data.get("additional_charge_category_3", "0.0000000"),
            additional_charge_category_4=reservation_data.get("additional_charge_category_4", "0.0000000"),
        )
        
        session.add(new_reservation)
        await session.commit()
        await session.refresh(new_reservation)
        return new_reservation


async def get_reservations(
    session: AsyncSession,
    limit: int = 1000,
    offset: int = 0
) -> tuple[List[Reservation], int]:
    """
    Get paginated reservations from database.
    
    Args:
        session: Database session
        limit: Maximum number of records
        offset: Number of records to skip
    
    Returns:
        Tuple of (reservations list, total count)
    """
    # Get total count
    count_result = await session.execute(select(func.count(Reservation.id)))
    total_count = count_result.scalar()
    
    # Get paginated data
    result = await session.execute(
        select(Reservation)
        .order_by(Reservation.id)
        .limit(limit)
        .offset(offset)
    )
    reservations = result.scalars().all()
    
    return reservations, total_count


def reservation_to_dict(reservation: Reservation) -> dict:
    """
    Convert Reservation model to dictionary.
    
    Args:
        reservation: Reservation model instance
    
    Returns:
        Dictionary representation
    """
    return {
        "id": reservation.id,
        "pick_up_date": reservation.pick_up_date.isoformat() if reservation.pick_up_date else None,
        "total_days": reservation.total_days,
        "total_price": reservation.total_price,
        "rental_user_id": reservation.rental_user_id,
        "pick_up_location_label": reservation.pick_up_location_label,
        "discounts_amount": reservation.discounts_amount,
        "status": reservation.status,
        "vehicle_class_label": reservation.vehicle_class_label,
        "additional_charge_category_1": reservation.additional_charge_category_1,
        "additional_charge_category_2": reservation.additional_charge_category_2,
        "additional_charge_category_3": reservation.additional_charge_category_3,
        "additional_charge_category_4": reservation.additional_charge_category_4,
        "created_at": reservation.created_at.isoformat() if reservation.created_at else None,
        "updated_at": reservation.updated_at.isoformat() if reservation.updated_at else None,
    }

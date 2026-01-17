"""
Database models for the application.
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class Reservation(Base):
    """Reservation model for database storage."""
    __tablename__ = "reservations"
    
    id = Column(Integer, primary_key=True, index=True)
    pick_up_date = Column(DateTime, nullable=True)
    total_days = Column(Integer, nullable=True)
    total_price = Column(String, nullable=True)
    rental_user_id = Column(Integer, nullable=True)
    pick_up_location_label = Column(String, nullable=True)
    discounts_amount = Column(String, nullable=True)
    status = Column(String, nullable=True)
    vehicle_class_label = Column(String, nullable=True)
    additional_charge_category_1 = Column(String, nullable=True, default="0.0000000")
    additional_charge_category_2 = Column(String, nullable=True, default="0.0000000")
    additional_charge_category_3 = Column(String, nullable=True, default="0.0000000")
    additional_charge_category_4 = Column(String, nullable=True, default="0.0000000")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

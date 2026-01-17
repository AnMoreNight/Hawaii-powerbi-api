"""
Data processing functions for filtering and merging reservation data.
"""
from typing import Dict


def filter_reservation_data(reservation: dict) -> dict:
    """
    Filter reservation data to include only the specified fields.
    Returns a filtered dictionary with only the required fields.
    """
    filtered = {}
    
    # Direct fields (always include, set to None if missing)
    filtered["id"] = reservation.get("id")
    filtered["pick_up_date"] = reservation.get("pick_up_date")
    filtered["total_days"] = reservation.get("total_days")
    filtered["total_price"] = reservation.get("total_price")
    filtered["rental_user_id"] = reservation.get("rental_user_id")
    filtered["pick_up_location_label"] = reservation.get("pick_up_location_label")
    filtered["discounts_amount"] = reservation.get("discounts_amount")
    filtered["status"] = reservation.get("status")
    
    # Nested field: active_vehicle_information.vehicle_class_label
    vehicle_class_label = None
    if "active_vehicle_information" in reservation:
        active_vehicle = reservation["active_vehicle_information"]
        if isinstance(active_vehicle, dict):
            # Check if vehicle_class_label exists directly
            if "vehicle_class_label" in active_vehicle:
                vehicle_class_label = active_vehicle["vehicle_class_label"]
            # Otherwise check in vehicle object
            elif "vehicle" in active_vehicle:
                vehicle = active_vehicle["vehicle"]
                if isinstance(vehicle, dict) and "vehicle_class_label" in vehicle:
                    vehicle_class_label = vehicle["vehicle_class_label"]
    
    if vehicle_class_label is not None:
        filtered["active_vehicle_information"] = {
            "vehicle_class_label": vehicle_class_label
        }
    else:
        filtered["active_vehicle_information"] = {
            "vehicle_class_label": None
        }
    
    # Calculate additional_charge_category totals from all_additional_charges
    additional_charge_totals = {
        "additional_charge_category_1": 0.0,
        "additional_charge_category_2": 0.0,
        "additional_charge_category_3": 0.0,
        "additional_charge_category_4": 0.0
    }
    
    if "all_additional_charges" in reservation and isinstance(reservation["all_additional_charges"], list):
        for charge in reservation["all_additional_charges"]:
            if isinstance(charge, dict):
                category_id = charge.get("additional_charge_category_id")
                pivot = charge.get("pivot", {})
                total_price = pivot.get("total_price", "0.0000000")
                
                if category_id in [1, 2, 3, 4]:
                    # Sum up the total_price for this category
                    try:
                        new_price = float(total_price) if total_price else 0.0
                        additional_charge_totals[f"additional_charge_category_{category_id}"] += new_price
                    except (ValueError, TypeError):
                        pass
    
    # Add the calculated totals (format as string with 7 decimal places to match original format)
    filtered["additional_charge_category_1"] = f"{additional_charge_totals['additional_charge_category_1']:.7f}"
    filtered["additional_charge_category_2"] = f"{additional_charge_totals['additional_charge_category_2']:.7f}"
    filtered["additional_charge_category_3"] = f"{additional_charge_totals['additional_charge_category_3']:.7f}"
    filtered["additional_charge_category_4"] = f"{additional_charge_totals['additional_charge_category_4']:.7f}"
    
    return filtered

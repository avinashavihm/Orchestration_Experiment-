"""Rules engine for resupply recommendations."""

from typing import Dict
import pandas as pd
from app.config import Config


def recommend_resupply(
    site_features: pd.Series
) -> Dict[str, any]:
    """
    Generate resupply recommendation based on rules.
    
    Args:
        site_features: Series containing site features (projected_30d_demand,
                      current_inventory, days_to_expiry, etc.)
        
    Returns:
        Dictionary with action, quantity, and reason:
        {
            "action": "resupply" | "no_resupply",
            "quantity": int,
            "reason": str
        }
    """
    projected_demand = int(site_features["projected_30d_demand"])
    current_inventory = int(site_features["current_inventory"])
    days_to_expiry = float(site_features["days_to_expiry"])
    
    # Calculate safety stock
    safety_stock = int(projected_demand * (Config.SAFETY_STOCK_MULTIPLIER - 1))
    
    # Check expiry override
    if days_to_expiry < Config.EXPIRY_THRESHOLD_DAYS:
        recommended_quantity = max(
            Config.MIN_ORDER_QUANTITY,
            projected_demand + safety_stock - current_inventory
        )
        return {
            "action": "resupply",
            "quantity": recommended_quantity,
            "reason": f"Inventory expiring in {int(days_to_expiry)} days. "
                     f"Projected demand: {projected_demand}, "
                     f"Current inventory: {current_inventory}. "
                     f"Resupply needed to maintain stock levels."
        }
    
    # Standard rule: resupply if projected demand exceeds current + safety stock
    if projected_demand > current_inventory + safety_stock:
        recommended_quantity = max(
            Config.MIN_ORDER_QUANTITY,
            projected_demand + safety_stock - current_inventory
        )
        return {
            "action": "resupply",
            "quantity": recommended_quantity,
            "reason": f"Projected 30-day demand ({projected_demand}) exceeds "
                     f"current inventory ({current_inventory}) plus safety stock. "
                     f"Resupply {recommended_quantity} kits recommended."
        }
    else:
        return {
            "action": "no_resupply",
            "quantity": 0,
            "reason": f"Current inventory ({current_inventory}) sufficient for "
                     f"projected 30-day demand ({projected_demand}). "
                     f"No resupply needed at this time."
        }


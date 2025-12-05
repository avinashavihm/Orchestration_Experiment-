from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
from app.enrollment_predictor import EnrollmentPredictor


def compute_site_features(
    data: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Compute features for each site.
    
    Args:
        data: Dictionary containing all loaded DataFrames
        
    Returns:
        DataFrame with computed features per site
    """
    sites_df = data["sites"].copy()
    dispense_df = data["dispense"].copy()
    inventory_df = data["inventory"].copy()
    
    # Handle site_name - create if missing
    if "site_name" not in sites_df.columns:
        sites_df["site_name"] = sites_df["site_id"]
    
    # Handle weekly dispense kits
    if "weekly_dispense_kits" in dispense_df.columns:
        # Already aggregated weekly
        dispense_summary = dispense_df.groupby("site_id")["weekly_dispense_kits"].mean().reset_index()
    elif "kits_dispensed" in dispense_df.columns:
        # Need to calculate from historical data
        if "dispense_date" in dispense_df.columns:
            dispense_df["dispense_date"] = pd.to_datetime(dispense_df["dispense_date"])
            date_range = dispense_df.groupby("site_id")["dispense_date"].agg([
                ("min_date", "min"),
                ("max_date", "max")
            ]).reset_index()
            date_range["days_covered"] = (
                date_range["max_date"] - date_range["min_date"]
            ).dt.days + 1
            
            dispense_summary = dispense_df.groupby("site_id")["kits_dispensed"].sum().reset_index()
            dispense_summary = dispense_summary.merge(date_range, on="site_id")
            dispense_summary["days_covered"] = dispense_summary["days_covered"].clip(lower=1)
            dispense_summary["weekly_dispense_kits"] = (
                dispense_summary["kits_dispensed"] * (7 / dispense_summary["days_covered"])
            )
        else:
            # No dates, assume weekly aggregation
            dispense_summary = dispense_df.groupby("site_id")["kits_dispensed"].mean().reset_index()
            dispense_summary["weekly_dispense_kits"] = dispense_summary["kits_dispensed"]
    else:
        # No dispense data, set to 0
        dispense_summary = pd.DataFrame({"site_id": sites_df["site_id"].unique(), "weekly_dispense_kits": 0})
    
    # Project 30-day demand (base from dispense history)
    dispense_summary["projected_30d_demand_base"] = (
        dispense_summary["weekly_dispense_kits"] * (30 / 7)
    ).round().astype(int)
    
    # Adjust demand based on enrollment predictions
    enrollment_predictor = EnrollmentPredictor()
    enrollment_predictions = enrollment_predictor.predict_enrollment(data.get("enrollment", pd.DataFrame()))
    screen_fail_rates = enrollment_predictor.predict_screen_fail_rate(data.get("enrollment", pd.DataFrame()))
    
    # Adjust demand for each site
    adjusted_demands = []
    for site_id in dispense_summary["site_id"]:
        base_demand = dispense_summary[dispense_summary["site_id"] == site_id]["projected_30d_demand_base"].iloc[0] if len(dispense_summary[dispense_summary["site_id"] == site_id]) > 0 else 0
        pred_enrollment = enrollment_predictions.get(site_id, {}).get("predicted_30d_enrollment", 0)
        fail_rate = screen_fail_rates.get(site_id, 0.30)
        
        adjusted_demand = enrollment_predictor.adjust_demand_for_enrollment(
            base_demand, pred_enrollment, fail_rate
        )
        adjusted_demands.append(adjusted_demand)
    
    dispense_summary["projected_30d_demand"] = adjusted_demands
    
    # Get current inventory per site
    inventory_summary = inventory_df.groupby("site_id")["current_inventory"].sum().reset_index()
    
    # Handle expiry date (could be expiry_date or batch_expiry_date)
    expiry_col = None
    for col in ["expiry_date", "batch_expiry_date"]:
        if col in inventory_df.columns:
            expiry_col = col
            break
    
    if expiry_col:
        expiry_summary = inventory_df.groupby("site_id")[expiry_col].min().reset_index()
        expiry_summary[expiry_col] = pd.to_datetime(expiry_summary[expiry_col])
        expiry_summary["days_to_expiry"] = (
            expiry_summary[expiry_col] - pd.Timestamp.now()
        ).dt.days
    else:
        # No expiry date, set to large number
        expiry_summary = inventory_df[["site_id"]].drop_duplicates().copy()
        expiry_summary["days_to_expiry"] = 999
    
    # Merge all features
    features = sites_df.merge(dispense_summary[["site_id", "weekly_dispense_kits", "projected_30d_demand"]], 
                              on="site_id", how="left")
    features = features.merge(inventory_summary, on="site_id", how="left")
    if expiry_col:
        features = features.merge(expiry_summary[["site_id", "days_to_expiry"]], on="site_id", how="left")
    else:
        features["days_to_expiry"] = 999
    
    # Fill missing values
    features["current_inventory"] = features["current_inventory"].fillna(0).astype(int)
    features["projected_30d_demand"] = features["projected_30d_demand"].fillna(0).astype(int)
    features["weekly_dispense_kits"] = features["weekly_dispense_kits"].fillna(0)
    features["days_to_expiry"] = features["days_to_expiry"].fillna(999)
    
    # Calculate urgency score
    features["urgency_score"] = (
        features["projected_30d_demand"] / (features["current_inventory"] + 1)
    )
    
    # Ensure region mapping exists
    if "region" not in features.columns:
        features["region"] = "Unknown"
    
    # Add enrollment prediction data
    features["predicted_30d_enrollment"] = features["site_id"].map(
        lambda sid: enrollment_predictions.get(sid, {}).get("predicted_30d_enrollment", 0)
    ).astype(int)
    features["avg_weekly_enrollment"] = features["site_id"].map(
        lambda sid: enrollment_predictions.get(sid, {}).get("avg_weekly_enrollment", 0.0)
    ).astype(float)
    features["enrollment_trend"] = features["site_id"].map(
        lambda sid: enrollment_predictions.get(sid, {}).get("enrollment_trend", "unknown")
    )
    features["screen_fail_rate"] = features["site_id"].map(
        lambda sid: screen_fail_rates.get(sid, 0.30)
    ).astype(float)
    
    return features[["site_id", "site_name", "region", "weekly_dispense_kits", 
                     "projected_30d_demand", "current_inventory", "days_to_expiry", 
                     "urgency_score", "predicted_30d_enrollment", "avg_weekly_enrollment",
                     "enrollment_trend", "screen_fail_rate"]]


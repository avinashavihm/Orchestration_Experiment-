from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class EnrollmentPredictor:
    """Predicts future enrollment and screen fail rates."""
    
    def __init__(self):
        """Initialize enrollment predictor."""
        pass
    
    def predict_enrollment(
        self,
        enrollment_df: pd.DataFrame,
        forecast_days: int = 30
    ) -> Dict[str, Any]:
        """
        Predict future enrollment based on historical data.
        
        Args:
            enrollment_df: DataFrame with enrollment data
            forecast_days: Number of days to forecast ahead
            
        Returns:
            Dictionary with enrollment predictions per site
        """
        predictions = {}
        
        # Check if we have weekly enrollment data
        if "weekly_enrollment" in enrollment_df.columns:
            for site_id, group in enrollment_df.groupby("site_id"):
                weekly_enrollment = group["weekly_enrollment"].values
                
                # Use simple moving average for prediction
                # If we have historical data, use average; otherwise use current value
                if len(weekly_enrollment) > 0:
                    avg_weekly = np.mean(weekly_enrollment)
                    predicted_30d = int(avg_weekly * (forecast_days / 7))
                else:
                    # Fallback to current value if available
                    current = group["weekly_enrollment"].iloc[-1] if len(group) > 0 else 0
                    predicted_30d = int(current * (forecast_days / 7))
                
                predictions[site_id] = {
                    "predicted_30d_enrollment": predicted_30d,
                    "avg_weekly_enrollment": float(avg_weekly) if len(weekly_enrollment) > 0 else 0.0,
                    "enrollment_trend": self._calculate_trend(weekly_enrollment)
                }
        elif "enrollment_date" in enrollment_df.columns and "subject_count" in enrollment_df.columns:
            # Calculate from historical enrollment dates
            enrollment_df["enrollment_date"] = pd.to_datetime(enrollment_df["enrollment_date"])
            
            for site_id, group in enrollment_df.groupby("site_id"):
                if len(group) > 0:
                    # Calculate weekly enrollment rate
                    date_range = (group["enrollment_date"].max() - group["enrollment_date"].min()).days + 1
                    total_subjects = group["subject_count"].sum()
                    
                    if date_range > 0:
                        weekly_enrollment = (total_subjects / date_range) * 7
                    else:
                        weekly_enrollment = total_subjects
                    
                    predicted_30d = int(weekly_enrollment * (forecast_days / 7))
                    
                    predictions[site_id] = {
                        "predicted_30d_enrollment": predicted_30d,
                        "avg_weekly_enrollment": float(weekly_enrollment),
                        "enrollment_trend": "stable"  # Would need more data for trend
                    }
                else:
                    predictions[site_id] = {
                        "predicted_30d_enrollment": 0,
                        "avg_weekly_enrollment": 0.0,
                        "enrollment_trend": "unknown"
                    }
        else:
            # No enrollment data available
            for site_id in enrollment_df["site_id"].unique():
                predictions[site_id] = {
                    "predicted_30d_enrollment": 0,
                    "avg_weekly_enrollment": 0.0,
                    "enrollment_trend": "unknown"
                }
        
        return predictions
    
    def predict_screen_fail_rate(
        self,
        enrollment_df: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Predict screen fail rates per site.
        
        Args:
            enrollment_df: DataFrame with enrollment data including screen_fail_rate
            
        Returns:
            Dictionary mapping site_id to predicted screen fail rate
        """
        fail_rates = {}
        
        if "screen_fail_rate" in enrollment_df.columns:
            for site_id, group in enrollment_df.groupby("site_id"):
                # Use average screen fail rate for the site
                avg_fail_rate = float(group["screen_fail_rate"].mean())
                fail_rates[site_id] = avg_fail_rate
        else:
            # Default fail rate if not available (industry average ~30%)
            for site_id in enrollment_df["site_id"].unique():
                fail_rates[site_id] = 0.30
        
        return fail_rates
    
    def adjust_demand_for_enrollment(
        self,
        base_demand: int,
        predicted_enrollment: int,
        screen_fail_rate: float
    ) -> int:
        """
        Adjust projected demand based on enrollment predictions and screen fail rates.
        
        Args:
            base_demand: Base projected demand from dispense history
            predicted_enrollment: Predicted enrollment for the period
            screen_fail_rate: Expected screen fail rate (0.0-1.0)
            
        Returns:
            Adjusted demand projection
        """
        # Calculate expected successful enrollments (after screen failures)
        successful_enrollments = int(predicted_enrollment * (1 - screen_fail_rate))
        
        # If enrollment prediction suggests higher demand, use it
        # Otherwise, stick with historical dispense-based demand
        enrollment_based_demand = successful_enrollments  # Assume 1 kit per successful enrollment
        
        # Use the higher of the two (enrollment-based or historical)
        adjusted_demand = max(base_demand, enrollment_based_demand)
        
        return adjusted_demand
    
    def _calculate_trend(self, values: np.ndarray) -> str:
        """Calculate trend from time series values."""
        if len(values) < 2:
            return "unknown"
        
        # Simple linear trend
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"


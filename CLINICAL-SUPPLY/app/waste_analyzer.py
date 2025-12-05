from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class WasteAnalyzer:
    """Analyzes waste patterns and identifies root causes."""
    
    def __init__(self):
        """Initialize waste analyzer."""
        pass
    
    def analyze_waste_patterns(
        self,
        waste_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
        dispense_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Analyze waste patterns across sites.
        
        Args:
            waste_df: DataFrame with waste records
            inventory_df: DataFrame with inventory data
            dispense_df: DataFrame with dispense data
            
        Returns:
            Dictionary with waste analysis results
        """
        analysis = {
            "total_waste": 0,
            "waste_by_reason": {},
            "waste_by_site": {},
            "waste_rate_by_site": {},
            "trends": {},
            "root_causes": []
        }
        
        if waste_df.empty:
            return analysis
        
        # Ensure date column exists
        if "date" in waste_df.columns:
            waste_df["date"] = pd.to_datetime(waste_df["date"])
        
        # Total waste
        if "wasted_kits" in waste_df.columns:
            analysis["total_waste"] = int(waste_df["wasted_kits"].sum())
        elif "quantity" in waste_df.columns:
            analysis["total_waste"] = int(waste_df["quantity"].sum())
        
        # Waste by reason
        if "reason" in waste_df.columns:
            reason_groups = waste_df.groupby("reason")
            for reason, group in reason_groups:
                waste_qty = group["wasted_kits"].sum() if "wasted_kits" in group.columns else group["quantity"].sum()
                analysis["waste_by_reason"][reason] = {
                    "quantity": int(waste_qty),
                    "percentage": float(waste_qty / analysis["total_waste"] * 100) if analysis["total_waste"] > 0 else 0.0,
                    "occurrences": len(group)
                }
        
        # Waste by site
        site_groups = waste_df.groupby("site_id")
        for site_id, group in site_groups:
            waste_qty = group["wasted_kits"].sum() if "wasted_kits" in group.columns else group["quantity"].sum()
            analysis["waste_by_site"][site_id] = {
                "total_waste": int(waste_qty),
                "waste_by_reason": {}
            }
            
            if "reason" in group.columns:
                for reason, reason_group in group.groupby("reason"):
                    reason_waste = reason_group["wasted_kits"].sum() if "wasted_kits" in reason_group.columns else reason_group["quantity"].sum()
                    analysis["waste_by_site"][site_id]["waste_by_reason"][reason] = int(reason_waste)
        
        # Calculate waste rates (waste / total dispensed)
        if not dispense_df.empty:
            if "kits_dispensed" in dispense_df.columns:
                total_dispensed = dispense_df.groupby("site_id")["kits_dispensed"].sum()
            elif "weekly_dispense_kits" in dispense_df.columns:
                total_dispensed = dispense_df.groupby("site_id")["weekly_dispense_kits"].sum() * 4  # Approximate monthly
            else:
                total_dispensed = pd.Series(dtype=float)
            
            for site_id in analysis["waste_by_site"].keys():
                site_waste = analysis["waste_by_site"][site_id]["total_waste"]
                site_dispensed = total_dispensed.get(site_id, 0)
                
                if site_dispensed > 0:
                    waste_rate = (site_waste / site_dispensed) * 100
                else:
                    waste_rate = 0.0
                
                analysis["waste_rate_by_site"][site_id] = {
                    "waste_rate_percent": float(waste_rate),
                    "waste_quantity": site_waste,
                    "dispensed_quantity": int(site_dispensed)
                }
        
        # Identify trends
        if "date" in waste_df.columns:
            waste_df["month"] = waste_df["date"].dt.to_period("M")
            monthly_waste = waste_df.groupby("month")["wasted_kits"].sum() if "wasted_kits" in waste_df.columns else waste_df.groupby("month")["quantity"].sum()
            
            if len(monthly_waste) >= 2:
                recent_trend = self._calculate_waste_trend(monthly_waste.values)
                # Convert Period indices to strings for JSON serialization
                recent_months_dict = {str(period): int(value) for period, value in monthly_waste.tail(3).items()}
                analysis["trends"]["monthly"] = {
                    "trend": recent_trend,
                    "recent_months": recent_months_dict
                }
        
        # Identify root causes
        analysis["root_causes"] = self._identify_root_causes(analysis, waste_df, inventory_df)
        
        return analysis
    
    def _calculate_waste_trend(self, values: np.ndarray) -> str:
        """Calculate trend from waste values."""
        if len(values) < 2:
            return "insufficient_data"
        
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def _identify_root_causes(
        self,
        analysis: Dict[str, Any],
        waste_df: pd.DataFrame,
        inventory_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Identify root causes of waste."""
        root_causes = []
        
        # Check for expiry-related waste
        if "reason" in waste_df.columns:
            expiry_waste = waste_df[waste_df["reason"].str.contains("expir|Expir", case=False, na=False)]
            if len(expiry_waste) > 0:
                expiry_qty = expiry_waste["wasted_kits"].sum() if "wasted_kits" in expiry_waste.columns else expiry_waste["quantity"].sum()
                root_causes.append({
                    "cause": "Expiry-related waste",
                    "severity": "high" if expiry_qty > 50 else "medium",
                    "quantity_affected": int(expiry_qty),
                    "recommendation": "Improve demand forecasting and reduce safety stock to prevent over-ordering"
                })
        
        # Check for temperature excursion waste
        if "reason" in waste_df.columns:
            temp_waste = waste_df[waste_df["reason"].str.contains("temp|Temp|temperature", case=False, na=False)]
            if len(temp_waste) > 0:
                temp_qty = temp_waste["wasted_kits"].sum() if "wasted_kits" in temp_waste.columns else temp_waste["quantity"].sum()
                root_causes.append({
                    "cause": "Temperature excursion waste",
                    "severity": "high",
                    "quantity_affected": int(temp_qty),
                    "recommendation": "Implement enhanced cold chain monitoring and improve shipping procedures"
                })
        
        # Check for damage-related waste
        if "reason" in waste_df.columns:
            damage_waste = waste_df[waste_df["reason"].str.contains("damage|Damage", case=False, na=False)]
            if len(damage_waste) > 0:
                damage_qty = damage_waste["wasted_kits"].sum() if "wasted_kits" in damage_waste.columns else damage_waste["quantity"].sum()
                root_causes.append({
                    "cause": "Damage-related waste",
                    "severity": "medium",
                    "quantity_affected": int(damage_qty),
                    "recommendation": "Review packaging and handling procedures"
                })
        
        # Identify high waste rate sites
        for site_id, site_data in analysis.get("waste_rate_by_site", {}).items():
            if site_data["waste_rate_percent"] > 10.0:  # >10% waste rate
                root_causes.append({
                    "cause": f"High waste rate at site {site_id}",
                    "severity": "high",
                    "waste_rate": site_data["waste_rate_percent"],
                    "recommendation": f"Investigate site-specific issues at {site_id}. Current waste rate: {site_data['waste_rate_percent']:.1f}%"
                })
        
        return root_causes
    
    def recommend_waste_reduction(
        self,
        analysis: Dict[str, Any],
        site_id: Optional[str] = None
    ) -> List[str]:
        """
        Generate waste reduction recommendations.
        
        Args:
            analysis: Waste analysis results
            site_id: Optional site ID for site-specific recommendations
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        if site_id and site_id in analysis.get("waste_by_site", {}):
            site_data = analysis["waste_by_site"][site_id]
            
            # Check for specific issues
            if "Expiry" in str(site_data.get("waste_by_reason", {})):
                recommendations.append("Reduce safety stock and improve demand forecasting to prevent expiry")
            
            if "Temp Excursion" in str(site_data.get("waste_by_reason", {})):
                recommendations.append("Implement enhanced temperature monitoring and cold chain procedures")
            
            if "Damage" in str(site_data.get("waste_by_reason", {})):
                recommendations.append("Review packaging specifications and handling procedures")
        else:
            # General recommendations
            if analysis.get("total_waste", 0) > 100:
                recommendations.append("Overall waste levels are high. Review ordering patterns and inventory management")
            
            if "Expiry" in str(analysis.get("waste_by_reason", {})):
                recommendations.append("Expiry-related waste detected. Optimize safety stock levels and improve demand forecasting")
            
            if "Temp Excursion" in str(analysis.get("waste_by_reason", {})):
                recommendations.append("Temperature excursion waste detected. Enhance cold chain monitoring and shipping procedures")
        
        return recommendations


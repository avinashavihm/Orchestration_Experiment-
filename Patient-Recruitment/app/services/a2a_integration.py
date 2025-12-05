#!/usr/bin/env python3
"""
A2A Integration Helper for Patient Recruitment Agent
Extracts enrollment curves from analysis results and prepares data for A2A calls
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_enrollment_curve_from_site_ranking(
    site_ranking: pd.DataFrame,
    elig_df: pd.DataFrame,
    monthly_rate: float = 10.0,
    screen_fail_rate: float = 0.3,
    months: int = 12
) -> List[int]:
    """
    Extract enrollment curve from site ranking results.
    
    Uses real site ranking data to project monthly enrollment numbers.
    
    Args:
        site_ranking: DataFrame with site ranking results (columns: Site_ID, Enrollment_Probability, etc.)
        elig_df: DataFrame with eligibility results
        monthly_rate: Base monthly enrollment rate per site
        screen_fail_rate: Screen failure rate (0.0-1.0)
        months: Number of months to project
        
    Returns:
        List of monthly enrollment numbers
    """
    try:
        enrollment_curve = []
        
        if site_ranking.empty or "Enrollment_Probability" not in site_ranking.columns:
            logger.warning("Site ranking is empty or missing Enrollment_Probability column")
            # Fallback: use simple projection
            num_sites = len(site_ranking) if not site_ranking.empty else 10
            base_enrollment = int(monthly_rate * num_sites * (1 - screen_fail_rate))
            return [base_enrollment] * months
        
        # Calculate total enrollment probability
        total_enrollment_probability = site_ranking["Enrollment_Probability"].sum()
        
        # Get eligible count per site from site_ranking (already computed)
        eligible_counts = {}
        if "Site_ID" in site_ranking.columns and "Eligible_Pool" in site_ranking.columns:
            for _, row in site_ranking.iterrows():
                site_id = row.get("Site_ID", "")
                eligible_counts[site_id] = int(row.get("Eligible_Pool", 0))
        
        # Project enrollment for each month
        for month in range(months):
            month_enrollment = 0
            
            for _, row in site_ranking.iterrows():
                site_id = row.get("Site_ID", "")
                enrollment_prob = row.get("Enrollment_Probability", 0)
                
                # Get eligible pool for this site
                eligible_pool = eligible_counts.get(site_id, 0)
                
                # Calculate monthly enrollment: base_rate * prob_factor * (1 - screen_fail_rate)
                if total_enrollment_probability > 0:
                    prob_factor = enrollment_prob / total_enrollment_probability
                else:
                    prob_factor = 1.0 / len(site_ranking) if len(site_ranking) > 0 else 1.0
                
                # Scale monthly rate by probability and eligible pool
                site_monthly = monthly_rate * prob_factor * (1 - screen_fail_rate)
                
                # Adjust for eligible pool size (if we have it)
                if eligible_pool > 0:
                    # Cap at eligible pool if monthly rate would exceed it
                    site_monthly = min(site_monthly, eligible_pool * (1 - screen_fail_rate) / months)
                
                month_enrollment += int(site_monthly)
            
            enrollment_curve.append(month_enrollment)
        
        logger.info(f"Generated enrollment curve: {enrollment_curve} (total: {sum(enrollment_curve)})")
        return enrollment_curve
        
    except Exception as e:
        logger.error(f"Error extracting enrollment curve: {e}", exc_info=True)
        # Fallback to simple projection
        num_sites = len(site_ranking) if not site_ranking.empty else 10
        base_enrollment = int(monthly_rate * num_sites * (1 - screen_fail_rate))
        return [base_enrollment] * months


async def call_supply_agent_with_real_data(
    enrollment_curve: List[int],
    site_list: List[str],
    visit_schedule: Optional[Dict[str, Any]] = None,
    kit_usage_per_visit: float = 1.0
) -> Dict[str, Any]:
    """
    Call Supply agent A2A with real enrollment curve data.
    
    Args:
        enrollment_curve: Real enrollment curve from analysis
        site_list: List of site IDs
        visit_schedule: Optional visit schedule details
        kit_usage_per_visit: Kits per visit (default 1.0)
        
    Returns:
        Supply forecast results from Supply agent
    """
    try:
        # Import here to avoid circular dependencies
        import sys
        from pathlib import Path
        
        # Add parent directory to path if needed
        parent_dir = Path(__file__).parent.parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        
        from call_supply_agent import SupplyAgentClient
        
        logger.info(f"Calling Supply agent with real enrollment curve: {sum(enrollment_curve)} total enrollment")
        
        client = SupplyAgentClient()
        await client.connect()
        
        try:
            # Call supply agent with real data
            supply_forecast = await client.calculate_supply_forecast(
                enrollment_curve=enrollment_curve,
                visit_schedule=visit_schedule or {
                    "visits_per_patient": 5,
                    "visit_frequency_weeks": 4
                },
                kit_usage_per_visit=kit_usage_per_visit
            )
            
            logger.info("Successfully received supply forecast from Supply agent")
            return supply_forecast
            
        finally:
            await client.disconnect()
            
    except Exception as e:
        logger.error(f"Error calling Supply agent: {e}", exc_info=True)
        # Return empty result instead of failing
        return {
            "error": str(e),
            "summary": {
                "total_kits_needed": 0,
                "sites_covered": len(site_list),
                "demand_met_percentage": 0.0
            },
            "depot_forecast": {},
            "site_resupply_plan": {},
            "expiry_and_safety_stock": {}
        }


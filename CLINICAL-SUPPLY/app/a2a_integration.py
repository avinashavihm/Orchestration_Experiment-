#!/usr/bin/env python3
"""
A2A Integration Helper for Clinical Supply Agent
Calls Recruitment agent to get updated enrollment data
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


async def call_recruitment_agent_for_enrollment(
    study_id: str = "STUDY_001",
    site_list: Optional[List[str]] = None,
    monthly_rate: float = 10.0,
    screen_fail_rate: float = 0.3
) -> Dict[str, Any]:
    """
    Call Recruitment agent A2A to get updated enrollment forecast.
    
    Args:
        study_id: Study identifier
        site_list: Optional list of site IDs (if None, will use sites from data)
        monthly_rate: Monthly enrollment rate per site
        screen_fail_rate: Screen failure rate (0.0-1.0)
        
    Returns:
        Enrollment projection from Recruitment agent
    """
    try:
        # Import here to avoid circular dependencies
        import sys
        from pathlib import Path
        
        # Add parent directory to path if needed
        parent_dir = Path(__file__).parent.parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        
        from call_recruitment_agent import RecruitmentAgentClient
        
        logger.info(f"Calling Recruitment agent for enrollment forecast: study_id={study_id}")
        
        client = RecruitmentAgentClient()
        await client.connect()
        
        try:
            # Get site list from data if not provided
            if site_list is None:
                from app.data_loader import load_data
                data = load_data(upload_dir=None)
                if "sites" in data and not data["sites"].empty:
                    site_list = data["sites"]["site_id"].tolist()
                else:
                    site_list = [f"SITE_{i:03d}" for i in range(1, 11)]  # Default
            
            # Request enrollment projection
            enrollment_projection = await client.request_enrollment_projection(
                study_id=study_id,
                site_list=site_list,
                monthly_rate=monthly_rate,
                screen_fail_rate=screen_fail_rate
            )
            
            logger.info("Successfully received enrollment projection from Recruitment agent")
            return enrollment_projection
            
        finally:
            await client.disconnect()
            
    except Exception as e:
        logger.error(f"Error calling Recruitment agent: {e}", exc_info=True)
        # Return empty result instead of failing
        return {
            "error": str(e),
            "study_id": study_id,
            "enrollment_curve": [],
            "total_sites": 0,
            "screen_fail_rate": screen_fail_rate,
            "projected_total_enrollment": 0,
            "site_ranking_summary": []
        }


def extract_enrollment_curve_from_supply_data(
    enrollment_df: pd.DataFrame,
    months: int = 12
) -> List[int]:
    """
    Extract enrollment curve from Clinical Supply enrollment data.
    
    Supports multiple data formats:
    - weekly_enrollment: Weekly enrollment per site (converted to monthly)
    - enrollment_date + subject_count: Historical enrollment dates
    
    Args:
        enrollment_df: DataFrame with enrollment data
        months: Number of months to project
        
    Returns:
        List of monthly enrollment numbers
    """
    try:
        enrollment_curve = []
        
        if enrollment_df.empty:
            logger.warning("Enrollment data is empty")
            return [0] * months
        
        # Check for weekly_enrollment column (current data format)
        if "weekly_enrollment" in enrollment_df.columns:
            # Convert weekly enrollment to monthly enrollment
            # Average weeks per month = 365.25 / 12 / 7 ≈ 4.348
            weeks_per_month = 4.348
            
            # Get average weekly enrollment across all sites
            if "site_id" in enrollment_df.columns:
                # Group by site and get average weekly enrollment per site
                site_weekly_avg = enrollment_df.groupby("site_id")["weekly_enrollment"].mean()
                total_weekly_enrollment = site_weekly_avg.sum()
            else:
                # Sum all weekly enrollment values
                total_weekly_enrollment = enrollment_df["weekly_enrollment"].sum()
            
            # Convert to monthly enrollment
            avg_monthly_enrollment = int(total_weekly_enrollment * weeks_per_month)
            
            # Apply screen fail rate if available (adjust for successful enrollments)
            if "screen_fail_rate" in enrollment_df.columns:
                avg_screen_fail_rate = enrollment_df["screen_fail_rate"].mean()
                # Adjust for successful enrollments (1 - screen_fail_rate)
                avg_monthly_enrollment = int(avg_monthly_enrollment * (1 - avg_screen_fail_rate))
            
            # Project forward for all months
            for month in range(months):
                enrollment_curve.append(avg_monthly_enrollment)
            
            logger.info(f"Extracted enrollment curve from weekly_enrollment: {enrollment_curve} (total: {sum(enrollment_curve)})")
            return enrollment_curve
        
        # Check for enrollment_date + subject_count format (historical format)
        elif "enrollment_date" in enrollment_df.columns and "subject_count" in enrollment_df.columns:
            enrollment_df["enrollment_date"] = pd.to_datetime(enrollment_df["enrollment_date"])
            
            # Calculate monthly totals
            enrollment_df["year_month"] = enrollment_df["enrollment_date"].dt.to_period("M")
            monthly_totals = enrollment_df.groupby("year_month")["subject_count"].sum()
            
            # Get average monthly enrollment
            if len(monthly_totals) > 0:
                avg_monthly = monthly_totals.mean()
            else:
                avg_monthly = enrollment_df["subject_count"].sum() / max(1, months)
            
            # Project forward
            for month in range(months):
                enrollment_curve.append(int(avg_monthly))
            
            logger.info(f"Extracted enrollment curve from enrollment_date: {enrollment_curve} (total: {sum(enrollment_curve)})")
            return enrollment_curve
        
        else:
            # Fallback: try to use subject_count if available
            if "subject_count" in enrollment_df.columns:
                total = enrollment_df["subject_count"].sum()
                avg_monthly = int(total / max(1, months))
                enrollment_curve = [avg_monthly] * months
                logger.warning(f"Using fallback calculation from subject_count: {enrollment_curve}")
                return enrollment_curve
            else:
                logger.warning("No recognized enrollment columns found. Returning zero enrollment curve.")
                return [0] * months
        
    except Exception as e:
        logger.error(f"Error extracting enrollment curve from supply data: {e}", exc_info=True)
        return [0] * months


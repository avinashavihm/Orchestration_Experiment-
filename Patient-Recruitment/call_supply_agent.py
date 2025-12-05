#!/usr/bin/env python3
"""
A2A Client for Patient Recruitment Agent to call Clinical Supply Agent
Connects to ws://localhost:4002
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import websockets
from websockets.client import connect

# Import recruitment agent modules to generate enrollment curve
from app.services.site_ranking import compute_site_ranking
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SupplyAgentClient:
    """A2A Client to call Clinical Supply Agent MCP server"""
    
    def __init__(self, url: str = None):
        # Default to container name in Docker, fallback to localhost for local testing
        import os
        if url is None:
            url = os.getenv("SUPPLY_AGENT_MCP_URL", "ws://clin-supply-backend:4002")
        self.url = url
        self.websocket = None
    
    async def connect(self):
        """Connect to the supply agent MCP server"""
        try:
            logger.info(f"Connecting to supply agent at {self.url}")
            self.websocket = await connect(self.url)
            logger.info("Connected to supply agent")
        except Exception as e:
            logger.error(f"Failed to connect to supply agent: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the supply agent"""
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from supply agent")
    
    async def _call_method(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a method on the supply agent via JSON-RPC"""
        if not self.websocket:
            await self.connect()
        
        request = {
            "jsonrpc": "2.0",
            "id": int(datetime.now().timestamp() * 1000),
            "method": method,
            "params": params
        }
        
        logger.info(f"Calling supply agent method: {method}")
        await self.websocket.send(json.dumps(request))
        
        # Wait for response
        response_str = await self.websocket.recv()
        response = json.loads(response_str)
        
        if "error" in response:
            logger.error(f"Supply agent error: {response['error']}")
            raise Exception(f"Supply agent error: {response['error']}")
        
        logger.info(f"Received response from supply agent: {method}")
        return response.get("result", {})
    
    async def calculate_supply_forecast(
        self,
        enrollment_curve: List[int],
        visit_schedule: Optional[Dict[str, Any]] = None,
        kit_usage_per_visit: float = 1.0
    ) -> Dict[str, Any]:
        """
        Send enrollment curve to supply agent and get full supply forecast.
        
        Args:
            enrollment_curve: List of monthly enrollment numbers
            visit_schedule: Optional visit schedule details
            kit_usage_per_visit: Number of kits per visit
            
        Returns:
            Full supply forecast with depot and site resupply plan
        """
        logger.info(f"Sending enrollment curve to supply agent: {len(enrollment_curve)} months")
        
        params = {
            "enrollment_curve": enrollment_curve,
            "visit_schedule": visit_schedule,
            "kit_usage_per_visit": kit_usage_per_visit
        }
        
        return await self._call_method("calculate_supply_forecast", params)
    
    async def adjust_resupply_based_on_enrollment(
        self,
        updated_curves: Dict[str, List[int]]
    ) -> Dict[str, Any]:
        """
        Update supply plan if recruitment changes.
        
        Args:
            updated_curves: Dictionary mapping site_id to updated enrollment curve
            
        Returns:
            Updated resupply plan
        """
        logger.info(f"Requesting supply plan adjustment for {len(updated_curves)} sites")
        
        params = {
            "updated_curves": updated_curves
        }
        
        return await self._call_method("adjust_resupply_based_on_enrollment", params)
    
    async def request_supply_summary(self) -> Dict[str, Any]:
        """
        Request supply summary from supply agent.
        
        Returns:
            Supply status summary
        """
        logger.info("Requesting supply summary")
        
        params = {}
        return await self._call_method("generate_supply_summary_for_recruitment", params)


def generate_enrollment_curve_from_ranking(
    site_ranking: pd.DataFrame,
    monthly_rate: float,
    screen_fail_rate: float,
    num_months: int = 12
) -> List[int]:
    """
    Generate enrollment curve using real prediction logic from site ranking.
    
    Args:
        site_ranking: DataFrame from compute_site_ranking
        monthly_rate: Base monthly enrollment rate
        screen_fail_rate: Screen failure rate (0.0-1.0)
        num_months: Number of months to project
        
    Returns:
        List of monthly enrollment numbers
    """
    enrollment_curve = []
    total_enrollment_probability = site_ranking["Enrollment_Probability"].sum()
    
    if total_enrollment_probability > 0:
        for month in range(num_months):
            month_enrollment = 0
            for _, row in site_ranking.iterrows():
                enrollment_prob = row["Enrollment_Probability"]
                site_monthly = monthly_rate * (enrollment_prob / total_enrollment_probability) * (1 - screen_fail_rate)
                month_enrollment += int(site_monthly)
            enrollment_curve.append(month_enrollment)
    else:
        # Fallback
        num_sites = len(site_ranking)
        for month in range(num_months):
            month_enrollment = int(monthly_rate * num_sites * (1 - screen_fail_rate))
            enrollment_curve.append(month_enrollment)
    
    return enrollment_curve


async def task_flow_recruitment_to_supply():
    """
    Task Flow 1: Recruitment → Supply
    
    1. Predict enrollment curve using internal logic
    2. Send it via A2A to supply agent
    3. Receive depot + site resupply forecast
    4. Print + log the result
    """
    logger.info("=" * 60)
    logger.info("TASK FLOW 1: Recruitment → Supply")
    logger.info("=" * 60)
    
    try:
        # Step 1: Predict enrollment curve using internal logic
        logger.info("Step 1: Generating enrollment curve using internal logic...")
        
        # Create sample data for demonstration
        elig_df = pd.DataFrame({
            "patient_id": [f"P{i}" for i in range(100)],
            "eligible": [True] * 100
        })
        
        map_df = pd.DataFrame({
            "Patient_ID": [f"P{i}" for i in range(100)],
            "Site_ID": np.random.choice([f"SITE_{i:03d}" for i in range(1, 11)], 100)
        })
        
        site_hist_df = pd.DataFrame({
            "siteId": [f"SITE_{i:03d}" for i in range(1, 11)],
            "status": ["Ongoing"] * 10,
            "screeningFailureRate": [0.3] * 10
        })
        
        # Use real site ranking logic
        from app.services.site_ranking import compute_site_ranking
        site_ranking = compute_site_ranking(
            elig_df=elig_df,
            map_df=map_df,
            site_hist_df=site_hist_df
        )
        
        logger.info(f"Site ranking computed: {len(site_ranking)} sites")
        
        # Generate enrollment curve
        monthly_rate = 10.0
        screen_fail_rate = 0.3
        enrollment_curve = generate_enrollment_curve_from_ranking(
            site_ranking=site_ranking,
            monthly_rate=monthly_rate,
            screen_fail_rate=screen_fail_rate
        )
        
        logger.info(f"Enrollment curve generated: {enrollment_curve}")
        logger.info(f"Total projected enrollment: {sum(enrollment_curve)} patients")
        
        # Step 2: Send to supply agent via A2A
        logger.info("\nStep 2: Sending enrollment curve to supply agent...")
        
        client = SupplyAgentClient()
        await client.connect()
        
        try:
            # Step 3: Receive depot + site resupply forecast
            logger.info("Step 3: Requesting supply forecast from supply agent...")
            
            supply_forecast = await client.calculate_supply_forecast(
                enrollment_curve=enrollment_curve,
                visit_schedule={
                    "visits_per_patient": 5,
                    "visit_frequency_weeks": 4
                },
                kit_usage_per_visit=1.0
            )
            
            # Step 4: Print + log the result
            logger.info("\nStep 4: Supply Forecast Received:")
            logger.info("=" * 60)
            logger.info(f"Total Kits Required: {supply_forecast['summary']['total_kits_needed']}")
            logger.info(f"Sites Covered: {supply_forecast['summary']['sites_covered']}")
            logger.info(f"Demand Met: {supply_forecast['summary']['demand_met_percentage']:.2f}%")
            logger.info(f"Total Safety Stock: {supply_forecast['expiry_and_safety_stock']['total_safety_stock']}")
            
            print("\n" + "=" * 60)
            print("SUPPLY FORECAST RESULTS")
            print("=" * 60)
            print(json.dumps(supply_forecast, indent=2, default=str))
            print("=" * 60)
            
            # Request supply summary
            logger.info("\nRequesting supply summary...")
            supply_summary = await client.request_supply_summary()
            logger.info(f"Supply Summary: {supply_summary.get('summary_text', 'N/A')}")
            
        finally:
            await client.disconnect()
        
        logger.info("\nTask Flow 1 completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in task flow: {e}", exc_info=True)
        raise


async def main():
    """Main entry point for testing"""
    await task_flow_recruitment_to_supply()


if __name__ == "__main__":
    asyncio.run(main())


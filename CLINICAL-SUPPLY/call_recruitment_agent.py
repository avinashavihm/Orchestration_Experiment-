#!/usr/bin/env python3
"""
A2A Client for Clinical Supply Agent to call Patient Recruitment Agent
Connects to ws://localhost:4001
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import websockets
from websockets.client import connect

# Import supply agent modules to use returned results
from app.depot_optimizer import DepotOptimizer
from app.enrollment_predictor import EnrollmentPredictor
from app.features import compute_site_features

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RecruitmentAgentClient:
    """A2A Client to call Patient Recruitment Agent MCP server"""
    
    def __init__(self, url: str = None):
        # Default to container name in Docker, fallback to localhost for local testing
        import os
        if url is None:
            url = os.getenv("RECRUITMENT_AGENT_MCP_URL", "ws://patient-recruitment-backend:4001")
        self.url = url
        self.websocket = None
    
    async def connect(self):
        """Connect to the recruitment agent MCP server"""
        try:
            logger.info(f"Connecting to recruitment agent at {self.url}")
            self.websocket = await connect(self.url)
            logger.info("Connected to recruitment agent")
        except Exception as e:
            logger.error(f"Failed to connect to recruitment agent: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the recruitment agent"""
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from recruitment agent")
    
    async def _call_method(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a method on the recruitment agent via JSON-RPC"""
        if not self.websocket:
            await self.connect()
        
        request = {
            "jsonrpc": "2.0",
            "id": int(datetime.now().timestamp() * 1000),
            "method": method,
            "params": params
        }
        
        logger.info(f"Calling recruitment agent method: {method}")
        await self.websocket.send(json.dumps(request))
        
        # Wait for response
        response_str = await self.websocket.recv()
        response = json.loads(response_str)
        
        if "error" in response:
            logger.error(f"Recruitment agent error: {response['error']}")
            raise Exception(f"Recruitment agent error: {response['error']}")
        
        logger.info(f"Received response from recruitment agent: {method}")
        return response.get("result", {})
    
    async def request_enrollment_projection(
        self,
        study_id: str,
        site_list: List[str],
        monthly_rate: float,
        screen_fail_rate: float
    ) -> Dict[str, Any]:
        """
        Request enrollment projection from recruitment agent.
        
        Args:
            study_id: Study identifier
            site_list: List of site IDs
            monthly_rate: Base monthly enrollment rate
            screen_fail_rate: Screen failure rate
            
        Returns:
            Enrollment projection with curve
        """
        logger.info(f"Requesting enrollment projection for study: {study_id}")
        
        params = {
            "study_id": study_id,
            "site_list": site_list,
            "monthly_rate": monthly_rate,
            "screen_fail_rate": screen_fail_rate
        }
        
        return await self._call_method("predict_enrollment_curve", params)
    
    async def request_site_risk_analysis(
        self,
        site_id: str,
        operational_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Request site-level risk scores from recruitment agent.
        
        Args:
            site_id: Site identifier
            operational_metrics: Optional operational metrics
            
        Returns:
            Risk analysis with scores and indicators
        """
        logger.info(f"Requesting risk analysis for site: {site_id}")
        
        params = {
            "site_id": site_id,
            "operational_metrics": operational_metrics
        }
        
        return await self._call_method("site_risk_analysis", params)
    
    async def request_recruitment_summary(self) -> Dict[str, Any]:
        """
        Request a short recruitment summary from recruitment agent.
        
        Returns:
            Recruitment status summary
        """
        logger.info("Requesting recruitment summary")
        
        params = {}
        return await self._call_method("recruitment_summary_for_supply", params)


async def task_flow_supply_to_recruitment():
    """
    Task Flow 2: Supply → Recruitment
    
    1. Supply agent needs updated enrollment
    2. Call recruitment agent via A2A
    3. Receive updated forecast
    4. Recalculate resupply plan
    5. Print + log final output
    """
    logger.info("=" * 60)
    logger.info("TASK FLOW 2: Supply → Recruitment")
    logger.info("=" * 60)
    
    try:
        # Step 1: Supply agent needs updated enrollment
        logger.info("Step 1: Supply agent needs updated enrollment data...")
        
        study_id = "STUDY_001"
        site_list = [f"SITE_{i:03d}" for i in range(1, 11)]
        monthly_rate = 10.0
        screen_fail_rate = 0.3
        
        # Step 2: Call recruitment agent via A2A
        logger.info("\nStep 2: Calling recruitment agent for updated enrollment forecast...")
        
        client = RecruitmentAgentClient()
        await client.connect()
        
        try:
            # Request enrollment projection
            enrollment_projection = await client.request_enrollment_projection(
                study_id=study_id,
                site_list=site_list,
                monthly_rate=monthly_rate,
                screen_fail_rate=screen_fail_rate
            )
            
            logger.info(f"Received enrollment projection: {enrollment_projection.get('projected_total_enrollment')} total patients")
            enrollment_curve = enrollment_projection.get("enrollment_curve", [])
            
            # Request site risk analysis for a few sites
            logger.info("\nRequesting site risk analysis...")
            risk_analyses = {}
            for site_id in site_list[:3]:  # Sample first 3 sites
                risk_analysis = await client.request_site_risk_analysis(
                    site_id=site_id,
                    operational_metrics={
                        "status": "Ongoing",
                        "screeningFailureRate": screen_fail_rate
                    }
                )
                risk_analyses[site_id] = risk_analysis
                logger.info(f"  {site_id}: {risk_analysis.get('risk_level')} risk (score: {risk_analysis.get('risk_score')})")
            
            # Request recruitment summary
            logger.info("\nRequesting recruitment summary...")
            recruitment_summary = await client.request_recruitment_summary()
            logger.info(f"Recruitment Summary: {recruitment_summary.get('summary_text', 'N/A')}")
            
        finally:
            await client.disconnect()
        
        # Step 3: Receive updated forecast (already received above)
        logger.info("\nStep 3: Received updated enrollment forecast")
        logger.info(f"  Enrollment curve: {enrollment_curve}")
        logger.info(f"  Total enrollment: {sum(enrollment_curve)} patients")
        
        # Step 4: Recalculate resupply plan using real supply forecasting code
        logger.info("\nStep 4: Recalculating resupply plan using supply forecasting logic...")
        
        depot_optimizer = DepotOptimizer()
        enrollment_predictor = EnrollmentPredictor()
        
        # Calculate site demands from enrollment curve
        total_enrollment = sum(enrollment_curve)
        visits_per_patient = 5
        kit_usage_per_visit = 1.0
        total_kits_needed = int(total_enrollment * visits_per_patient * kit_usage_per_visit)
        
        # Distribute enrollment across sites
        num_sites = len(site_list)
        site_demands = {}
        for i, month_enrollment in enumerate(enrollment_curve):
            per_site = month_enrollment // num_sites
            for site_idx, site_id in enumerate(site_list):
                if site_id not in site_demands:
                    site_demands[site_id] = 0
                site_demands[site_id] += int(per_site * visits_per_patient * kit_usage_per_visit)
        
        # Use real depot optimizer
        depot_inventory = {"DEPOT_001": total_kits_needed * 2}
        site_inventory = {site_id: 0 for site_id in site_demands.keys()}
        lead_times = {
            "DEPOT_001": {site_id: 7 for site_id in site_demands.keys()}
        }
        
        resupply_plan = depot_optimizer.optimize_depot_allocation(
            site_demands=site_demands,
            depot_inventory=depot_inventory,
            site_inventory=site_inventory,
            lead_times=lead_times
        )
        
        # Calculate safety stocks
        avg_monthly_demand = sum(enrollment_curve) / len(enrollment_curve) if enrollment_curve else 0
        avg_weekly_demand = avg_monthly_demand / 4.33
        
        site_demands_for_safety = {
            site_id: avg_weekly_demand / num_sites
            for site_id in site_demands.keys()
        }
        
        safety_stocks = depot_optimizer.optimize_safety_stock(
            site_demands=site_demands_for_safety,
            lead_times={site_id: 7 for site_id in site_demands.keys()},
            service_level=0.95
        )
        
        # Step 5: Print + log final output
        logger.info("\nStep 5: Final Resupply Plan:")
        logger.info("=" * 60)
        logger.info(f"Total Kits Required: {total_kits_needed}")
        logger.info(f"Sites Covered: {len(site_demands)}")
        logger.info(f"Total Allocated: {resupply_plan.get('total_allocated', 0)}")
        logger.info(f"Optimization Score: {resupply_plan.get('optimization_score', 0.0):.2f}%")
        logger.info(f"Total Safety Stock: {sum(safety_stocks.values())}")
        logger.info(f"Unmet Demand Sites: {len(resupply_plan.get('unmet_demand', {}))}")
        
        final_output = {
            "enrollment_data": {
                "enrollment_curve": enrollment_curve,
                "total_enrollment": sum(enrollment_curve),
                "site_risk_analyses": risk_analyses
            },
            "resupply_plan": {
                "total_kits_needed": total_kits_needed,
                "site_demands": site_demands,
                "allocations": resupply_plan.get("allocations", []),
                "optimization_score": resupply_plan.get("optimization_score", 0.0),
                "safety_stocks": safety_stocks
            },
            "recruitment_summary": recruitment_summary
        }
        
        print("\n" + "=" * 60)
        print("FINAL RESUPPLY PLAN")
        print("=" * 60)
        print(json.dumps(final_output, indent=2, default=str))
        print("=" * 60)
        
        logger.info("\nTask Flow 2 completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in task flow: {e}", exc_info=True)
        raise


async def main():
    """Main entry point for testing"""
    await task_flow_supply_to_recruitment()


if __name__ == "__main__":
    asyncio.run(main())


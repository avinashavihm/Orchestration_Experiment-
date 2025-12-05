#!/usr/bin/env python3
"""
MCP Server for Clinical Supply Copilot
Exposes supply forecasting tools via WebSocket on ws://0.0.0.0:4002
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd

import websockets
from websockets.server import WebSocketServerProtocol

# Import existing supply agent modules
from app.depot_optimizer import DepotOptimizer
from app.enrollment_predictor import EnrollmentPredictor
from app.data_loader import load_data
from app.features import compute_site_features
from app.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SupplyMCPServer:
    """MCP Server for Clinical Supply Copilot"""
    
    def __init__(self):
        self.server_name = "clinical-supply-copilot"
        # Allow port to be configured via environment variable
        import os
        self.port = int(os.getenv("MCP_PORT", "4002"))
        self.host = os.getenv("MCP_HOST", "0.0.0.0")
        self.depot_optimizer = DepotOptimizer()
        self.enrollment_predictor = EnrollmentPredictor()
    
    def calculate_supply_forecast(
        self,
        enrollment_curve: List[int],
        visit_schedule: Optional[Dict[str, Any]] = None,
        kit_usage_per_visit: float = 1.0
    ) -> Dict[str, Any]:
        """
        Calculate supply forecast based on enrollment curve.
        
        Uses real supply forecasting logic from depot optimizer and enrollment predictor.
        
        Args:
            enrollment_curve: List of monthly enrollment numbers
            visit_schedule: Optional dict with visit schedule details
            kit_usage_per_visit: Number of kits per visit (default 1.0)
            
        Returns:
            Dictionary with depot forecast, site resupply plan, and expiry/safety stock requirements
            
        Raises:
            ValueError: If enrollment_curve is invalid (empty, None, or all zeros)
        """
        logger.info(f"calculate_supply_forecast called: enrollment_curve={len(enrollment_curve) if enrollment_curve else 0} months")
        
        # Validate enrollment_curve parameter
        if enrollment_curve is None:
            error_msg = "enrollment_curve cannot be None"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if not isinstance(enrollment_curve, list):
            error_msg = f"enrollment_curve must be a list, got {type(enrollment_curve)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if len(enrollment_curve) == 0:
            error_msg = "enrollment_curve cannot be empty"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Check if all values are zero or negative
        total_enrollment = sum(enrollment_curve)
        if total_enrollment <= 0:
            error_msg = f"enrollment_curve contains invalid values (total enrollment: {total_enrollment}). All values must be positive integers."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Check for negative values
        if any(x < 0 for x in enrollment_curve):
            error_msg = "enrollment_curve contains negative values. All values must be non-negative integers."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"Valid enrollment curve received: {len(enrollment_curve)} months, total enrollment: {total_enrollment}")
        
        try:
            
            # Default visit schedule if not provided
            if visit_schedule is None:
                visit_schedule = {
                    "visits_per_patient": 5,
                    "visit_frequency_weeks": 4
                }
            
            visits_per_patient = visit_schedule.get("visits_per_patient", 5)
            total_kits_needed = int(total_enrollment * visits_per_patient * kit_usage_per_visit)
            
            # Create site demands based on enrollment curve
            # Distribute enrollment across sites (simplified - in real usage would use actual site data)
            num_sites = 10  # Default number of sites
            site_demands = {}
            for i, month_enrollment in enumerate(enrollment_curve):
                # Distribute monthly enrollment across sites
                per_site = month_enrollment // num_sites
                for site_idx in range(num_sites):
                    site_id = f"SITE_{site_idx+1:03d}"
                    if site_id not in site_demands:
                        site_demands[site_id] = 0
                    site_demands[site_id] += int(per_site * visits_per_patient * kit_usage_per_visit)
            
            # Use real depot optimizer
            depot_inventory = {"DEPOT_001": total_kits_needed * 2}  # 2x safety margin
            site_inventory = {site_id: 0 for site_id in site_demands.keys()}
            lead_times = {
                "DEPOT_001": {site_id: 7 for site_id in site_demands.keys()}
            }
            
            allocation_plan = self.depot_optimizer.optimize_depot_allocation(
                site_demands=site_demands,
                depot_inventory=depot_inventory,
                site_inventory=site_inventory,
                lead_times=lead_times
            )
            
            # Calculate safety stock requirements
            avg_monthly_demand = sum(enrollment_curve) / len(enrollment_curve) if len(enrollment_curve) > 0 else 0
            avg_weekly_demand = avg_monthly_demand / 4.33  # Approximate weeks per month
            
            site_demands_for_safety = {
                site_id: avg_weekly_demand / num_sites
                for site_id in site_demands.keys()
            }
            
            safety_stocks = self.depot_optimizer.optimize_safety_stock(
                site_demands=site_demands_for_safety,
                lead_times={site_id: 7 for site_id in site_demands.keys()},
                service_level=0.95
            )
            
            # Calculate expiry requirements (simplified)
            expiry_requirements = {
                site_id: {
                    "min_shelf_life_days": 90,
                    "safety_stock": safety_stocks.get(site_id, 0),
                    "reorder_point": int(site_demands.get(site_id, 0) * 0.3)
                }
                for site_id in site_demands.keys()
            }
            
            result = {
                "depot_forecast": {
                    "total_kits_required": total_kits_needed,
                    "depot_inventory_required": depot_inventory,
                    "allocation_plan": allocation_plan
                },
                "site_resupply_plan": {
                    "site_demands": site_demands,
                    "allocations": allocation_plan.get("allocations", []),
                    "unmet_demand": allocation_plan.get("unmet_demand", {}),
                    "optimization_score": allocation_plan.get("optimization_score", 0.0)
                },
                "expiry_and_safety_stock": {
                    "safety_stocks": safety_stocks,
                    "expiry_requirements": expiry_requirements,
                    "total_safety_stock": sum(safety_stocks.values())
                },
                "summary": {
                    "total_enrollment": total_enrollment,
                    "total_kits_needed": total_kits_needed,
                    "sites_covered": len(site_demands),
                    "demand_met_percentage": allocation_plan.get("optimization_score", 0.0)
                }
            }
            
            logger.info(f"Supply forecast complete: {total_kits_needed} kits needed")
            return result
            
        except Exception as e:
            logger.error(f"Error in calculate_supply_forecast: {e}", exc_info=True)
            raise
    
    def adjust_resupply_based_on_enrollment(
        self,
        updated_curves: Dict[str, List[int]]
    ) -> Dict[str, Any]:
        """
        Recalculate site shipments and depot inventory based on updated enrollment curves.
        
        Args:
            updated_curves: Dictionary mapping site_id to updated enrollment curve
            
        Returns:
            Updated resupply plan with recalculated shipments and depot inventory
        """
        logger.info(f"adjust_resupply_based_on_enrollment called: {len(updated_curves)} sites")
        
        try:
            # Calculate new site demands from updated curves
            site_demands = {}
            for site_id, curve in updated_curves.items():
                total_enrollment = sum(curve)
                # Assume 5 visits per patient, 1 kit per visit
                site_demands[site_id] = int(total_enrollment * 5)
            
            # Use real depot optimizer to recalculate
            total_demand = sum(site_demands.values())
            depot_inventory = {"DEPOT_001": total_demand * 2}  # 2x safety margin
            site_inventory = {site_id: 0 for site_id in site_demands.keys()}
            lead_times = {
                "DEPOT_001": {site_id: 7 for site_id in site_demands.keys()}
            }
            
            allocation_plan = self.depot_optimizer.optimize_depot_allocation(
                site_demands=site_demands,
                depot_inventory=depot_inventory,
                site_inventory=site_inventory,
                lead_times=lead_times
            )
            
            # Calculate updated depot inventory recommendations
            depot_recommendations = self.depot_optimizer.optimize_depot_inventory(
                all_site_demands=site_demands,
                depot_capacity={"DEPOT_001": total_demand * 3}
            )
            
            result = {
                "updated_site_shipments": {
                    "allocations": allocation_plan.get("allocations", []),
                    "total_allocated": allocation_plan.get("total_allocated", 0),
                    "unmet_demand": allocation_plan.get("unmet_demand", {})
                },
                "updated_depot_inventory": depot_recommendations,
                "summary": {
                    "total_demand": total_demand,
                    "sites_updated": len(updated_curves),
                    "demand_met_percentage": allocation_plan.get("optimization_score", 0.0)
                }
            }
            
            logger.info(f"Resupply plan adjusted: {total_demand} total demand")
            return result
            
        except Exception as e:
            logger.error(f"Error in adjust_resupply_based_on_enrollment: {e}", exc_info=True)
            raise
    
    def generate_supply_summary_for_recruitment(self) -> Dict[str, Any]:
        """
        Generate plain-text summary to send back to recruitment agent.
        
        Returns:
            Human-readable summary of supply status
        """
        logger.info("generate_supply_summary_for_recruitment called")
        
        try:
            # In real implementation, this would read from actual data
            # For now, generate a summary structure
            
            summary = {
                "summary_text": "Clinical Supply Status Summary",
                "timestamp": pd.Timestamp.now().isoformat(),
                "supply_status": {
                    "total_inventory": 0,  # Would come from actual data
                    "sites_covered": 0,
                    "depot_capacity_utilization": 0.0,
                    "safety_stock_levels": "Adequate"
                },
                "forecast_status": {
                    "projected_demand_met": True,
                    "supply_risks": [],
                    "recommendations": []
                },
                "recommendations_for_recruitment": [
                    "Current supply levels can support projected enrollment",
                    "Monitor high-enrollment sites for increased demand",
                    "Consider adjusting enrollment targets if supply constraints exist"
                ]
            }
            
            logger.info("Supply summary generated")
            return summary
            
        except Exception as e:
            logger.error(f"Error in generate_supply_summary_for_recruitment: {e}", exc_info=True)
            raise
    
    async def handle_request(self, websocket: WebSocketServerProtocol, path: str = None):
        """Handle incoming WebSocket requests"""
        client_address = getattr(websocket, 'remote_address', 'unknown')
        logger.info(f"New connection from {client_address} (path: {path})")
        
        try:
            async for message in websocket:
                try:
                    request = json.loads(message)
                    logger.info(f"Received request: {request.get('method')}")
                    
                    method = request.get("method")
                    params = request.get("params", {})
                    request_id = request.get("id")
                    
                    # Route to appropriate method
                    if method == "calculate_supply_forecast":
                        result = self.calculate_supply_forecast(
                            enrollment_curve=params.get("enrollment_curve", []),
                            visit_schedule=params.get("visit_schedule"),
                            kit_usage_per_visit=params.get("kit_usage_per_visit", 1.0)
                        )
                    elif method == "adjust_resupply_based_on_enrollment":
                        result = self.adjust_resupply_based_on_enrollment(
                            updated_curves=params.get("updated_curves", {})
                        )
                    elif method == "generate_supply_summary_for_recruitment":
                        result = self.generate_supply_summary_for_recruitment()
                    else:
                        result = {
                            "error": f"Unknown method: {method}"
                        }
                    
                    # Send response
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result
                    }
                    
                    await websocket.send(json.dumps(response))
                    logger.info(f"Sent response for method: {method}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": request.get("id") if 'request' in locals() else None,
                        "error": {
                            "code": -32700,
                            "message": "Parse error",
                            "data": str(e)
                        }
                    }
                    await websocket.send(json.dumps(error_response))
                    
                except Exception as e:
                    logger.error(f"Error handling request: {e}", exc_info=True)
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": request.get("id") if 'request' in locals() else None,
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e)
                        }
                    }
                    await websocket.send(json.dumps(error_response))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed")
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
    
    async def start(self):
        """Start the MCP server"""
        logger.info(f"Starting MCP server: {self.server_name} on ws://{self.host}:{self.port}")
        
        async def handler(websocket, *args):
            path = args[0] if args else None
            await self.handle_request(websocket, path)
        
        async with websockets.serve(handler, self.host, self.port):
            logger.info(f"Server running on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever


async def main():
    """Main entry point"""
    server = SupplyMCPServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())


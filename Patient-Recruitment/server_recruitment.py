#!/usr/bin/env python3
"""
MCP Server for Patient Recruitment Agent
Exposes recruitment tools via WebSocket on ws://0.0.0.0:4001
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import websockets
from websockets.server import WebSocketServerProtocol

# Import existing recruitment agent modules
from app.services.site_ranking import compute_site_ranking
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RecruitmentMCPServer:
    """MCP Server for Patient Recruitment Agent"""
    
    def __init__(self):
        self.server_name = "patient-recruitment-agent"
        # Allow port to be configured via environment variable
        import os
        self.port = int(os.getenv("MCP_PORT", "4001"))
        self.host = os.getenv("MCP_HOST", "0.0.0.0")
    
    def predict_enrollment_curve(
        self,
        study_id: str,
        site_list: List[str],
        monthly_rate: float,
        screen_fail_rate: float
    ) -> Dict[str, Any]:
        """
        Predict enrollment curve based on site performance and rates.
        
        Uses real site ranking logic to calculate enrollment probabilities,
        then projects monthly enrollment numbers.
        
        Args:
            study_id: Study identifier
            site_list: List of site IDs
            monthly_rate: Base monthly enrollment rate per site
            screen_fail_rate: Screen failure rate (0.0-1.0)
            
        Returns:
            Dictionary with enrollment curve (list of monthly numbers)
        """
        logger.info(f"predict_enrollment_curve called: study_id={study_id}, sites={len(site_list)}")
        
        try:
            # Create synthetic eligibility and mapping data for site list
            # In real usage, this would come from actual patient data
            elig_df = pd.DataFrame({
                "patient_id": [f"P{i}" for i in range(100)],
                "eligible": [True] * 100
            })
            
            map_df = pd.DataFrame({
                "Patient_ID": [f"P{i}" for i in range(100)],
                "Site_ID": np.random.choice(site_list, 100) if site_list else ["SITE_001"] * 100
            })
            
            # Create site history with performance factors
            site_hist_data = []
            for site_id in site_list:
                site_hist_data.append({
                    "siteId": site_id,
                    "status": "Ongoing",  # Default to ongoing
                    "screeningFailureRate": screen_fail_rate
                })
            site_hist_df = pd.DataFrame(site_hist_data)
            
            # Use real site ranking logic
            site_ranking = compute_site_ranking(
                elig_df=elig_df,
                map_df=map_df,
                site_hist_df=site_hist_df
            )
            
            # Calculate enrollment curve for next 12 months
            enrollment_curve = []
            total_enrollment_probability = site_ranking["Enrollment_Probability"].sum()
            
            # Normalize probabilities to get per-site monthly rates
            if total_enrollment_probability > 0:
                # Scale monthly_rate by enrollment probability
                for month in range(12):
                    month_enrollment = 0
                    for _, row in site_ranking.iterrows():
                        site_id = row["Site_ID"]
                        enrollment_prob = row["Enrollment_Probability"]
                        
                        # Monthly enrollment = base_rate * (prob / max_prob) * (1 - screen_fail_rate)
                        site_monthly = monthly_rate * (enrollment_prob / total_enrollment_probability) * (1 - screen_fail_rate)
                        month_enrollment += int(site_monthly)
                    
                    enrollment_curve.append(month_enrollment)
            else:
                # Fallback: use monthly_rate directly
                for month in range(12):
                    month_enrollment = int(monthly_rate * len(site_list) * (1 - screen_fail_rate))
                    enrollment_curve.append(month_enrollment)
            
            result = {
                "study_id": study_id,
                "enrollment_curve": enrollment_curve,
                "total_sites": len(site_list),
                "screen_fail_rate": screen_fail_rate,
                "projected_total_enrollment": sum(enrollment_curve),
                "site_ranking_summary": site_ranking.to_dict(orient="records")[:5]  # Top 5 sites
            }
            
            logger.info(f"Enrollment curve generated: {sum(enrollment_curve)} total patients")
            return result
            
        except Exception as e:
            logger.error(f"Error in predict_enrollment_curve: {e}", exc_info=True)
            raise
    
    def site_risk_analysis(
        self,
        site_id: str,
        operational_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze site risk based on performance indicators.
        
        Uses real site ranking logic to calculate risk scores.
        
        Args:
            site_id: Site identifier
            operational_metrics: Optional dict with metrics like status, screeningFailureRate
            
        Returns:
            Dictionary with risk score and performance indicators
        """
        logger.info(f"site_risk_analysis called: site_id={site_id}")
        
        try:
            # Default metrics if not provided
            if operational_metrics is None:
                operational_metrics = {
                    "status": "Ongoing",
                    "screeningFailureRate": 0.3
                }
            
            status = operational_metrics.get("status", "Ongoing")
            sfr = operational_metrics.get("screeningFailureRate", 0.3)
            
            # Normalize screen fail rate
            if sfr > 1.0:
                sfr = sfr / 100.0
            sfr = max(0.0, min(1.0, sfr))
            
            # Calculate status multiplier (from real logic)
            status_mult = settings.STATUS_MULTIPLIER.get(str(status).strip().lower(), 0.0)
            
            # Calculate Site Performance Factor (from real logic)
            spf = status_mult * (1.0 - sfr)
            
            # Calculate risk score (inverse of performance)
            risk_score = 1.0 - spf
            
            # Determine risk level
            if risk_score >= 0.7:
                risk_level = "High"
            elif risk_score >= 0.4:
                risk_level = "Medium"
            else:
                risk_level = "Low"
            
            result = {
                "site_id": site_id,
                "risk_score": round(risk_score, 3),
                "risk_level": risk_level,
                "site_performance_factor": round(spf, 3),
                "status": status,
                "screening_failure_rate": round(sfr, 3),
                "status_multiplier": status_mult,
                "performance_indicators": {
                    "enrollment_capability": "High" if spf > 0.7 else "Medium" if spf > 0.4 else "Low",
                    "screening_efficiency": "High" if sfr < 0.2 else "Medium" if sfr < 0.4 else "Low",
                    "operational_status": "Active" if status_mult > 0 else "Inactive"
                }
            }
            
            logger.info(f"Risk analysis complete: {site_id} - {risk_level} risk")
            return result
            
        except Exception as e:
            logger.error(f"Error in site_risk_analysis: {e}", exc_info=True)
            raise
    
    def recruitment_summary_for_supply(self) -> Dict[str, Any]:
        """
        Generate human-readable recruitment summary for supply agent.
        
        Returns:
            Short enrollment and site status summary
        """
        logger.info("recruitment_summary_for_supply called")
        
        try:
            # In real implementation, this would read from actual data files
            # For now, generate a summary structure
            
            summary = {
                "summary_text": "Patient Recruitment Status Summary",
                "timestamp": datetime.now().isoformat(),
                "enrollment_status": {
                    "total_eligible_patients": 0,  # Would come from actual data
                    "sites_active": 0,
                    "average_enrollment_rate": 0.0,
                    "screen_fail_rate_avg": 0.3
                },
                "site_status": {
                    "high_performance_sites": [],
                    "medium_performance_sites": [],
                    "low_performance_sites": []
                },
                "recommendations": [
                    "Monitor high-performing sites for increased supply needs",
                    "Review low-performing sites for potential intervention",
                    "Adjust enrollment targets based on site performance"
                ]
            }
            
            logger.info("Recruitment summary generated")
            return summary
            
        except Exception as e:
            logger.error(f"Error in recruitment_summary_for_supply: {e}", exc_info=True)
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
                    if method == "predict_enrollment_curve":
                        result = self.predict_enrollment_curve(
                            study_id=params.get("study_id", "STUDY_001"),
                            site_list=params.get("site_list", []),
                            monthly_rate=params.get("monthly_rate", 10.0),
                            screen_fail_rate=params.get("screen_fail_rate", 0.3)
                        )
                    elif method == "site_risk_analysis":
                        result = self.site_risk_analysis(
                            site_id=params.get("site_id", "SITE_001"),
                            operational_metrics=params.get("operational_metrics")
                        )
                    elif method == "recruitment_summary_for_supply":
                        result = self.recruitment_summary_for_supply()
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
    server = RecruitmentMCPServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())


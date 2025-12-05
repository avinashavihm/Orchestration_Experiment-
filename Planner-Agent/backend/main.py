from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import shutil
import os
from planner import Planner
from agent_client import AgentClient
from typing import List, Dict, Any
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Planner Agent API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

planner = Planner()
client = AgentClient()

def combine_agent_results(results: Dict[str, Any], agent_status: Dict) -> Dict[str, Any]:
    """
    Combine analysis results from multiple agents and create cross-agent insights.
    """
    combined = {
        "summary": {
            "recruitment_analyzed": "recruitment" in results,
            "supply_analyzed": "supply" in results,
            "both_analyzed": "recruitment" in results and "supply" in results
        },
        "insights": [],
        "recommendations": []
    }
    
    # Extract key data from each agent
    recruitment_data = results.get("recruitment", {})
    supply_data = results.get("supply", {})
    
    # Cross-agent insights when both agents have completed analysis
    if combined["summary"]["both_analyzed"]:
        insights = []
        enrollment_curve = None
        total_enrollment = 0
        sites_needing_resupply = 0
        
        # Extract enrollment data from recruitment
        recruitment_meta = recruitment_data.get("metadata", {})
        a2a_data = recruitment_meta.get("a2a_integration", {})
        
        if a2a_data and a2a_data.get("enabled"):
            enrollment_curve = a2a_data.get("enrollment_curve", [])
            total_enrollment = a2a_data.get("total_enrollment", 0)
            
            if enrollment_curve and total_enrollment > 0:
                insights.append({
                    "type": "enrollment_forecast",
                    "message": f"Recruitment analysis projects {total_enrollment} total enrollment",
                    "data": {
                        "total_enrollment": total_enrollment,
                        "monthly_enrollment": enrollment_curve
                    }
                })
        
        # Extract supply forecast data
        if "summary" in supply_data:
            supply_summary = supply_data["summary"]
            sites_needing_resupply = supply_summary.get("sites_needing_resupply", 0)
            total_quantity = supply_summary.get("total_quantity", 0)
            
            if sites_needing_resupply > 0:
                insights.append({
                    "type": "supply_requirements",
                    "message": f"Supply analysis indicates {sites_needing_resupply} sites need resupply with {total_quantity} total units",
                    "data": {
                        "sites_needing_resupply": sites_needing_resupply,
                        "total_quantity": total_quantity
                    }
                })
        
        # Cross-reference site data
        recruitment_sites = []
        if "site_ranking" in str(recruitment_data):
            # Try to extract site IDs from recruitment results
            # This would need to be adjusted based on actual response structure
            pass
        
        supply_sites = []
        if "results" in supply_data:
            supply_results = supply_data.get("results", [])
            supply_sites = [r.get("site_id") for r in supply_results if isinstance(r, dict) and "site_id" in r]
        
        if recruitment_sites and supply_sites:
            common_sites = set(recruitment_sites) & set(supply_sites)
            if common_sites:
                insights.append({
                    "type": "site_overlap",
                    "message": f"Found {len(common_sites)} sites in both recruitment and supply analyses",
                    "data": {
                        "common_sites": list(common_sites),
                        "recruitment_only": len(set(recruitment_sites) - set(supply_sites)),
                        "supply_only": len(set(supply_sites) - set(recruitment_sites))
                    }
                })
        
        combined["insights"] = insights
        
        # Generate recommendations based on combined analysis
        recommendations = []
        
        if enrollment_curve and total_enrollment > 0 and sites_needing_resupply > 0:
            recommendations.append({
                "type": "supply_planning",
                "priority": "high",
                "message": "Consider aligning supply planning with projected enrollment from recruitment analysis",
                "action": "Review supply forecasts in context of enrollment projections"
            })
        
        combined["recommendations"] = recommendations
    
    return combined

@app.post("/analyze")
async def analyze_files(files: List[UploadFile] = File(...)):
    """
    Analyze uploaded files (any number), determine which agents have all required files,
    call those agents, and combine the results. Only uses files needed by agents.
    """
    logger.info(f"Received {len(files)} files")
    
    # Read all files into memory
    uploaded_files = []
    for file in files:
        content = await file.read()
        uploaded_files.append((file.filename, content))
    
    # Check which agents have all required files
    agent_status = planner.check_agent_completeness(uploaded_files)
    
    logger.info("Agent completeness check:")
    for agent_name, status in agent_status.items():
        logger.info(f"  {agent_name}: has_all_files={status['has_all_files']}, "
                   f"missing={status['missing_files']}, matched={list(status['matched_files'].keys())}")
    
    results = {}
    planner_summary = {
        "recruitment": {
            "can_analyze": False,
            "matched_files": [],
            "missing_files": []
        },
        "supply": {
            "can_analyze": False,
            "matched_files": [],
            "missing_files": []
        }
    }
    
    # Build file lists for agents that have all required files
    recruitment_files_map = {}
    supply_files_map = {}
    
    if agent_status["recruitment"]["has_all_files"]:
        # Map files according to what recruitment agent expects
        file_map = {filename: content for filename, content in uploaded_files}
        matched_files = agent_status["recruitment"]["matched_files"]
        
        # Prepare files in the format recruitment agent expects
        for file_type, filename in matched_files.items():
            if filename in file_map:
                recruitment_files_map[file_type] = (filename, file_map[filename])
        
        planner_summary["recruitment"]["can_analyze"] = True
        planner_summary["recruitment"]["matched_files"] = list(matched_files.keys())
    
    if agent_status["supply"]["has_all_files"]:
        # Map files according to what supply agent expects
        file_map = {filename: content for filename, content in uploaded_files}
        matched_files = agent_status["supply"]["matched_files"]
        
        # Prepare files in the format supply agent expects
        for file_type, filename in matched_files.items():
            if filename in file_map:
                supply_files_map[file_type] = (filename, file_map[filename])
        
        planner_summary["supply"]["can_analyze"] = True
        planner_summary["supply"]["matched_files"] = list(matched_files.keys())
    
    # Set missing files in summary
    if not agent_status["recruitment"]["has_all_files"]:
        planner_summary["recruitment"]["missing_files"] = agent_status["recruitment"]["missing_files"]
    if not agent_status["supply"]["has_all_files"]:
        planner_summary["supply"]["missing_files"] = agent_status["supply"]["missing_files"]
    
    # Call agents that have all required files (in parallel if both)
    tasks = []
    
    if recruitment_files_map:
        logger.info(f"Calling Recruitment Agent with {len(recruitment_files_map)} files")
        tasks.append(("recruitment", client.forward_to_recruitment(recruitment_files_map)))
    
    if supply_files_map:
        logger.info(f"Calling Supply Agent with {len(supply_files_map)} files")
        tasks.append(("supply", client.forward_to_supply(supply_files_map)))
    
    # Execute agent calls in parallel
    if tasks:
        task_results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
        
        for (agent_name, _), result in zip(tasks, task_results):
            if isinstance(result, Exception):
                logger.error(f"Error calling {agent_name} agent: {result}")
                results[agent_name] = {"error": str(result)}
            else:
                results[agent_name] = result
    
    # Combine results from multiple agents
    combined_analysis = combine_agent_results(results, agent_status)
    
    # Return combined result
    return {
        "planner_summary": planner_summary,
        "analysis_results": results,
        "combined_analysis": combined_analysis,
        "total_files_uploaded": len(files),
        "agents_called": [agent for agent in ["recruitment", "supply"] if agent in results]
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)

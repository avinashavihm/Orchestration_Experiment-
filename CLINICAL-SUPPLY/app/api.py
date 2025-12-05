import uuid
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

from app.config import Config
from app.upload_handler import save_uploaded_files, UploadValidationError
from app.orchestrator import Orchestrator
from app.waste_analyzer import WasteAnalyzer
from app.temp_excursion_handler import TempExcursionHandler
from app.depot_optimizer import DepotOptimizer
from app.data_loader import load_data
from app.a2a_integration import call_recruitment_agent_for_enrollment
import logging

logger = logging.getLogger(__name__)


app = FastAPI(
    title="Clinical Supply Copilot API",
    description="API for clinical supply forecasting and resupply recommendations",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Clinical Supply Copilot",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/upload-and-run")
async def upload_and_run(
    sites: UploadFile = File(..., description="sites.csv"),
    enrollment: UploadFile = File(..., description="enrollment.csv"),
    dispense: UploadFile = File(..., description="dispense.csv"),
    inventory: UploadFile = File(..., description="inventory.csv"),
    shipment: UploadFile = File(..., description="shipment_logs.csv"),
    waste: UploadFile = File(..., description="waste.csv"),
    enable_a2a: bool = Query(False, description="Enable A2A integration with Recruitment agent"),  # Optional, disabled by default
):
    """
    Upload CSV files and run forecasting pipeline.
    
    Accepts 6 CSV files via multipart/form-data:
    - sites.csv
    - enrollment.csv
    - dispense.csv
    - inventory.csv
    - shipment_logs.csv
    - waste.csv
    
    Returns:
        JSON response with results, summary, session_id, and output_path
    """
    session_id = str(uuid.uuid4())
    upload_dir = Config.get_upload_dir(session_id)
    
    try:
        # Validate filenames
        uploaded_files = {
            sites.filename: sites,
            enrollment.filename: enrollment,
            dispense.filename: dispense,
            inventory.filename: inventory,
            shipment.filename: shipment,
            waste.filename: waste,
        }
        
        # Check all required files are present
        received_filenames = set(uploaded_files.keys())
        required_filenames = set(Config.REQUIRED_CSV_FILES.values())
        
        missing_files = required_filenames - received_filenames
        if missing_files:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required files: {', '.join(missing_files)}"
            )
        
        # Save uploaded files
        saved_paths = await save_uploaded_files(uploaded_files, upload_dir)
        
        # Run orchestrator
        output_path = upload_dir / "results.jsonl"
        orchestrator = Orchestrator()
        result = orchestrator.run(upload_dir=upload_dir, output_path=output_path)
        
        # A2A Integration: Optionally call Recruitment agent for updated enrollment
        if enable_a2a:
            try:
                logger.info("[A2A] Starting A2A integration with Recruitment agent...")
                
                # Get site list from results
                site_list = None
                if "results" in result and len(result["results"]) > 0:
                    site_list = [r.get("site_id") for r in result["results"] if r.get("site_id")]
                
                # Call Recruitment agent for enrollment forecast
                enrollment_projection = await call_recruitment_agent_for_enrollment(
                    study_id="STUDY_001",
                    site_list=site_list,
                    monthly_rate=10.0,  # Default, could be configurable
                    screen_fail_rate=0.3  # Default
                )
                
                # Validate enrollment projection
                enrollment_curve = enrollment_projection.get("enrollment_curve", [])
                supply_forecast = None
                
                if enrollment_curve and len(enrollment_curve) > 0 and sum(enrollment_curve) > 0:
                    # Calculate supply forecast using A2A enrollment curve
                    try:
                        from server_supply import SupplyMCPServer
                        supply_server = SupplyMCPServer()
                        supply_forecast = supply_server.calculate_supply_forecast(
                            enrollment_curve=enrollment_curve,
                            visit_schedule=None,  # Use defaults
                            kit_usage_per_visit=1.0
                        )
                        logger.info(f"[A2A] Supply forecast calculated: {supply_forecast.get('summary', {}).get('total_kits_needed', 0)} kits needed")
                    except Exception as forecast_error:
                        logger.error(f"[A2A] Error calculating supply forecast: {forecast_error}", exc_info=True)
                        supply_forecast = {"error": str(forecast_error)}
                else:
                    logger.warning("[A2A] Enrollment curve is empty or invalid, skipping supply forecast calculation")
                    # Try to extract from local data as fallback
                    try:
                        from app.a2a_integration import extract_enrollment_curve_from_supply_data
                        data = load_data(upload_dir=upload_dir)
                        if "enrollment" in data and not data["enrollment"].empty:
                            local_curve = extract_enrollment_curve_from_supply_data(data["enrollment"], months=12)
                            if local_curve and sum(local_curve) > 0:
                                from server_supply import SupplyMCPServer
                                supply_server = SupplyMCPServer()
                                supply_forecast = supply_server.calculate_supply_forecast(
                                    enrollment_curve=local_curve,
                                    visit_schedule=None,
                                    kit_usage_per_visit=1.0
                                )
                                logger.info("[A2A] Used local enrollment data as fallback for supply forecast")
                    except Exception as fallback_error:
                        logger.error(f"[A2A] Fallback enrollment extraction failed: {fallback_error}", exc_info=True)
                
                # Add A2A results to response
                result["a2a_integration"] = {
                    "enabled": True,
                    "enrollment_projection": enrollment_projection,
                    "supply_forecast": supply_forecast,
                    "status": "success"
                }
                
                logger.info("[A2A] Successfully integrated with Recruitment agent")
                
            except Exception as a2a_error:
                # Don't fail the whole request if A2A fails
                logger.error(f"[A2A] Error in A2A integration: {a2a_error}", exc_info=True)
                
                # Try fallback: extract enrollment from local data
                supply_forecast = None
                try:
                    from app.a2a_integration import extract_enrollment_curve_from_supply_data
                    data = load_data(upload_dir=upload_dir)
                    if "enrollment" in data and not data["enrollment"].empty:
                        local_curve = extract_enrollment_curve_from_supply_data(data["enrollment"], months=12)
                        if local_curve and sum(local_curve) > 0:
                            from server_supply import SupplyMCPServer
                            supply_server = SupplyMCPServer()
                            supply_forecast = supply_server.calculate_supply_forecast(
                                enrollment_curve=local_curve,
                                visit_schedule=None,
                                kit_usage_per_visit=1.0
                            )
                            logger.info("[A2A] Used local enrollment data as fallback after A2A failure")
                except Exception as fallback_error:
                    logger.error(f"[A2A] Fallback enrollment extraction also failed: {fallback_error}", exc_info=True)
                
                result["a2a_integration"] = {
                    "enabled": True,
                    "error": str(a2a_error),
                    "status": "failed",
                    "supply_forecast": supply_forecast  # May be None if fallback also failed
                }
        else:
            result["a2a_integration"] = {"enabled": False}
        
        return JSONResponse(content=result)
        
    except UploadValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/run-default")
async def run_default():
    """
    Run forecasting pipeline using default data directory.
    
    Returns:
        JSON response with results and summary
    """
    try:
        orchestrator = Orchestrator()
        output_path = Config.DATA_DIR / "results.jsonl"
        result = orchestrator.run(upload_dir=None, output_path=output_path)
        
        return JSONResponse(content=result)
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/waste-analysis")
async def get_waste_analysis():
    """
    Analyze waste patterns from default data directory.
    
    Returns:
        JSON response with waste analysis results
    """
    try:
        data = load_data(upload_dir=None)
        waste_analyzer = WasteAnalyzer()
        analysis = waste_analyzer.analyze_waste_patterns(
            data.get("waste", pd.DataFrame()),
            data.get("inventory", pd.DataFrame()),
            data.get("dispense", pd.DataFrame())
        )
        return JSONResponse(content=analysis)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/temp-excursions")
async def get_temp_excursions():
    """
    Detect temperature excursions from default data directory.
    
    Returns:
        JSON response with temperature excursion data
    """
    try:
        data = load_data(upload_dir=None)
        temp_handler = TempExcursionHandler()
        excursions = temp_handler.detect_excursions(
            data.get("shipment", pd.DataFrame()),
            data.get("waste", pd.DataFrame())
        )
        return JSONResponse(content=excursions)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/temp-excursion-justification")
async def generate_temp_justification(
    site_id: str,
    quantity_affected: int,
    date: str,
    temperature: Optional[float] = None
):
    """
    Generate temperature excursion justification document.
    
    Args:
        site_id: Site identifier
        quantity_affected: Number of kits affected
        date: Date of excursion (YYYY-MM-DD)
        temperature: Optional temperature value
        
    Returns:
        JSON response with justification text
    """
    try:
        from datetime import datetime
        data = load_data(upload_dir=None)
        temp_handler = TempExcursionHandler()
        
        # Get site name
        sites_df = data.get("sites", pd.DataFrame())
        site_name = "Unknown"
        if not sites_df.empty and "site_id" in sites_df.columns:
            site_row = sites_df[sites_df["site_id"] == site_id]
            if len(site_row) > 0:
                site_name = site_row.iloc[0].get("site_name", site_id)
        
        # Get excursion data
        excursions = temp_handler.detect_excursions(
            data.get("shipment", pd.DataFrame()),
            data.get("waste", pd.DataFrame())
        )
        excursion_data = excursions.get(site_id, {})
        
        excursion_date = datetime.strptime(date, "%Y-%m-%d")
        
        justification = temp_handler.generate_justification(
            excursion_data,
            site_id,
            site_name,
            quantity_affected,
            excursion_date,
            temperature
        )
        
        return JSONResponse(content={
            "site_id": site_id,
            "site_name": site_name,
            "justification": justification
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# app/routers/run.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from datetime import datetime
import json
import traceback
import asyncio
import logging

from ..config import settings
from ..utils.fileio import ensure_dirs
from ..pipeline_v3 import run_pipeline
from ..services.a2a_integration import (
    extract_enrollment_curve_from_site_ranking,
    call_supply_agent_with_real_data
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/run")
async def run_pipeline_v3(
    protocol_pdf: UploadFile = File(..., description="Protocol PDF"),
    patients_xlsx: UploadFile = File(..., description="Patients.xlsx (no Site_ID)"),
    mapping_xlsx: UploadFile = File(..., description="Patient↔Site mapping.xlsx"),
    site_history_xlsx: UploadFile = File(..., description="Site history.xlsx"),
    return_json: bool = False,  # Optional query parameter to return JSON instead of file
    enable_a2a: bool = Query(True, description="Enable A2A integration with Supply agent"),  # Enable A2A by default
):
    """
    Version 3 pipeline endpoint:
      - Accepts 4 files (PDF + 3 xlsx)
      - Calls the v3 pipeline to evaluate eligibility in 100-row batches
      - Computes site ranking (Option A)
      - Returns a 4-sheet XLSX as a downloadable file or JSON with metadata
    """
    ensure_dirs()

    # Read all files into memory (bytes)
    try:
        pdf_bytes = await protocol_pdf.read()
        patients_bytes = await patients_xlsx.read()
        mapping_bytes = await mapping_xlsx.read()
        site_hist_bytes = await site_history_xlsx.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading uploaded files: {e}")

    # Run the v3 pipeline (criteria cache is in-memory per request)
    try:
        print("[V3] Starting pipeline processing...")
        xlsx_bytes, meta = run_pipeline(
            pdf_bytes=pdf_bytes,
            patients_xlsx=patients_bytes,
            map_xlsx=mapping_bytes,
            site_hist_xlsx=site_hist_bytes,
        )
        print("[V3] Pipeline completed successfully")
        print("[V3] META:", meta)
        
        # A2A Integration: Call Supply agent with real analysis results
        if enable_a2a:
            try:
                logger.info("[A2A] Starting A2A integration with Supply agent...")
                
                # Re-extract data to get site_ranking (we need to re-run part of pipeline)
                # We'll use the same logic but in a simplified way
                from io import BytesIO
                import pandas as pd
                from ..services.site_ranking import compute_site_ranking
                from ..services.criteria_extractor import extract_or_load_criteria_text
                from ..pipeline_v3 import (
                    _read_excel_bytes_auto_header,
                    PATIENT_REQUIRED_COLS,
                    MAPPING_REQUIRED_COLS,
                    SITE_HISTORY_REQUIRED_COLS,
                    evaluate_in_batches
                )
                
                # Re-read data (cached, fast)
                cache = {}
                criteria_text = extract_or_load_criteria_text(
                    pdf_bytes=pdf_bytes,
                    cache_store=cache,
                    start_page=38,
                    end_page=41,
                )
                
                patients_df = _read_excel_bytes_auto_header(patients_bytes, expected_cols=PATIENT_REQUIRED_COLS)
                map_df = _read_excel_bytes_auto_header(mapping_bytes, expected_cols=MAPPING_REQUIRED_COLS)
                site_hist_df = _read_excel_bytes_auto_header(site_hist_bytes, expected_cols=SITE_HISTORY_REQUIRED_COLS)
                
                # Re-evaluate eligibility (cached, fast)
                elig_df, _ = evaluate_in_batches(criteria_text=criteria_text, patients_df=patients_df)
                
                # Compute site ranking
                site_ranking = compute_site_ranking(elig_df=elig_df, map_df=map_df, site_hist_df=site_hist_df)
                
                # Extract enrollment curve from real data
                # Get screen fail rate from site history
                avg_screen_fail_rate = 0.3  # Default
                if not site_hist_df.empty and "screeningFailureRate" in site_hist_df.columns:
                    avg_screen_fail_rate = float(site_hist_df["screeningFailureRate"].mean())
                    if avg_screen_fail_rate > 1.0:
                        avg_screen_fail_rate = avg_screen_fail_rate / 100.0
                
                # Get site list
                site_list = site_ranking["Site_ID"].tolist() if not site_ranking.empty else []
                
                # Extract enrollment curve
                enrollment_curve = extract_enrollment_curve_from_site_ranking(
                    site_ranking=site_ranking,
                    elig_df=elig_df,
                    monthly_rate=10.0,  # Default, could be configurable
                    screen_fail_rate=avg_screen_fail_rate,
                    months=12
                )
                
                logger.info(f"[A2A] Extracted enrollment curve: {enrollment_curve} (total: {sum(enrollment_curve)})")
                
                # Call Supply agent A2A with real data
                supply_forecast = await call_supply_agent_with_real_data(
                    enrollment_curve=enrollment_curve,
                    site_list=site_list,
                    visit_schedule={
                        "visits_per_patient": 5,
                        "visit_frequency_weeks": 4
                    },
                    kit_usage_per_visit=1.0
                )
                
                # Add A2A results to metadata
                meta["a2a_integration"] = {
                    "enabled": True,
                    "supply_forecast": supply_forecast,
                    "enrollment_curve": enrollment_curve,
                    "total_enrollment": sum(enrollment_curve),
                    "sites": site_list
                }
                
                logger.info("[A2A] Successfully integrated with Supply agent")
                
            except Exception as a2a_error:
                # Don't fail the whole request if A2A fails
                logger.error(f"[A2A] Error in A2A integration: {a2a_error}", exc_info=True)
                meta["a2a_integration"] = {
                    "enabled": True,
                    "error": str(a2a_error),
                    "status": "failed"
                }
        else:
            meta["a2a_integration"] = {"enabled": False}
            
    except KeyboardInterrupt:
        print("[V3] Pipeline interrupted by user")
        raise HTTPException(status_code=500, detail="Processing was interrupted")
    except Exception as e:
        # Log full traceback for debugging
        error_traceback = traceback.format_exc()
        print(f"[ERROR] Processing failed: {e}")
        print(f"[ERROR] Full traceback:\n{error_traceback}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}\n\nTraceback:\n{error_traceback}")

    # Persist output to disk
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"eligibility_results_v3_{ts}.xlsx"
    out_path = Path(settings.OUTPUT_DIR) / out_name
    try:
        out_path.write_bytes(xlsx_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write XLSX output: {e}")

    # If JSON response requested, return metadata with file as base64
    if return_json:
        import base64
        file_base64 = base64.b64encode(xlsx_bytes).decode('utf-8')
        return JSONResponse({
            "filename": out_name,
            "file_data": file_base64,
            "metadata": meta,
        })

    # Return file with metadata in headers
    response = FileResponse(
        path=str(out_path),
        filename=out_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    # Add metadata to headers (JSON-encoded)
    meta_json = json.dumps(meta)
    response.headers["X-Metadata"] = meta_json
    print(f"[V3] Sending metadata in headers: {meta_json[:200]}...")  # Log first 200 chars
    return response



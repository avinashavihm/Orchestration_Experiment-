# app/pipeline_v3.py
from __future__ import annotations

import io
import json
from typing import Any, Dict, Tuple, List

import pandas as pd

# from .services.criteria_extractor import extract_or_load_criteria
from .agents.eligibility_agent import evaluate_in_batches
from .services.site_ranking import compute_site_ranking
from .services.criteria_extractor import extract_or_load_criteria_text

# from .agents.eligibility_agent import evaluate_in_batches, DEBUG_CAPTURE

# ----- Required headers (per your spec) -----
# Patients: all columns are required (as agreed)
PATIENT_REQUIRED_COLS = [
    "Patient_ID",
    "Age",
    "Weight_kg",
    "T_cruzi_Diagnosis",
    "Informed_Consent_Signed",
    "Lives_in_Vector_Free_Area",
    "Chronic_Chagas_Symptoms",
    "Previous_Chagas_Treatment",
    "History_of_Azole_Hypersensitivity",
    "Concomitant_CYP3A4_Meds",
]

# Mapping: ONLY Patient_ID and Site_ID are required; rest optional
MAPPING_REQUIRED_COLS = ["Patient_ID", "Site_ID"]
MAPPING_OPTIONAL_COLS = ["Assignment_Date", "Assignment_Method", "Enrollment_Status", "Cohort", "Priority_Flag"]

# Site history: only these are required for Option A scoring
SITE_HISTORY_REQUIRED_COLS = ["siteId", "status", "screeningFailureRate"]
# Everything else is optional and ignored by the Option A formula


# ----- Helpers -----
def _read_excel_bytes(file_bytes: bytes, header_row: int = 0) -> pd.DataFrame:
    """Read a single-sheet .xlsx from raw bytes and normalize headers (trim spaces)."""
    buf = io.BytesIO(file_bytes)
    df = pd.read_excel(buf, engine="openpyxl", header=header_row)
    # Normalize column names by stripping whitespace
    df.columns = [str(c).strip() for c in df.columns]
    return df

def _read_excel_bytes_auto_header(file_bytes: bytes, expected_cols: List[str] = None) -> pd.DataFrame:
    """Read Excel file, trying to auto-detect header row if first attempt fails."""
    # First try with header=0 (first row)
    df = _read_excel_bytes(file_bytes, header_row=0)
    
    # Check if we got "Unnamed" columns or if expected columns are missing
    has_unnamed = any('Unnamed' in str(col) for col in df.columns)
    missing_expected = False
    
    if expected_cols:
        # Normalize and check if any expected columns are found
        df_cols_norm = {_normalize_column_name(c) for c in df.columns}
        expected_norm = {_normalize_column_name(c) for c in expected_cols}
        missing_expected = len(expected_norm.intersection(df_cols_norm)) == 0
    
    # If we have "Unnamed" columns or missing expected columns, try header=1
    if has_unnamed or missing_expected:
        df = _read_excel_bytes(file_bytes, header_row=1)
    
    return df

def _normalize_column_name(col: str) -> str:
    """Normalize column name for comparison: lowercase, strip, replace spaces/underscores."""
    return str(col).strip().lower().replace(' ', '_').replace('-', '_')

def _find_column_mapping(df: pd.DataFrame, required_cols: List[str]) -> Dict[str, str]:
    """Find case-insensitive column mappings."""
    mapping = {}
    df_cols_normalized = {_normalize_column_name(c): c for c in df.columns}
    
    for req_col in required_cols:
        req_normalized = _normalize_column_name(req_col)
        if req_normalized in df_cols_normalized:
            mapping[req_col] = df_cols_normalized[req_normalized]
        else:
            # Try partial matches (e.g., "patient_id" matches "Patient ID" or "patientid")
            for df_col_norm, df_col_orig in df_cols_normalized.items():
                if req_normalized.replace('_', '') == df_col_norm.replace('_', ''):
                    mapping[req_col] = df_col_orig
                    break
    return mapping

def _validate_headers(df: pd.DataFrame, required_cols: List[str], context: str) -> None:
    """Validate headers with case-insensitive matching and helpful error messages."""
    missing = []
    found_mapping = _find_column_mapping(df, required_cols)
    
    for req_col in required_cols:
        if req_col not in found_mapping:
            missing.append(req_col)
    
    if missing:
        # Provide helpful suggestions
        suggestions = []
        for req_col in missing:
            req_norm = _normalize_column_name(req_col)
            similar = [c for c in df.columns if _normalize_column_name(c) == req_norm or 
                      req_norm.replace('_', '') in _normalize_column_name(c).replace('_', '')]
            if similar:
                suggestions.append(f"  '{req_col}' might be: {similar}")
        
        error_msg = f"{context} missing required columns: {missing}.\n"
        error_msg += f"Found columns: {list(df.columns)}\n"
        if suggestions:
            error_msg += "Similar column names found:\n" + "\n".join(suggestions)
        error_msg += "\nTip: Ensure your Excel file has the correct column headers in the first row."
        raise ValueError(error_msg)
    
    # Rename columns to standard names if they match (case-insensitive)
    rename_map = {found_mapping[req]: req for req in required_cols if req in found_mapping}
    if rename_map:
        df.rename(columns=rename_map, inplace=True)

def _pretty_json_cell(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)

def _build_rosters(
    patients_df: pd.DataFrame,
    elig_df: pd.DataFrame,
    map_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:

    base = patients_df.merge(
        map_df[["Patient_ID", "Site_ID"]],
        on="Patient_ID",
        how="left",
    )
    e = elig_df.rename(
        columns={
            "patient_id": "Patient_ID",
            "eligible": "Eligible",
            "reasons": "Reasons",
            "missing": "Missing_Data",
            "confidence": "Confidence",
        }
    )

    merged = base.merge(
        e[["Patient_ID", "Eligible", "Reasons", "Missing_Data", "Confidence"]],
        on="Patient_ID",
        how="left",
    )

    # 3) Ensure eligibility columns exist even if model failed
    for c in ["Eligible", "Reasons", "Missing_Data", "Confidence"]:
        if c not in merged.columns:
            merged[c] = None

    # 4) Order columns: all patient cols -> Site_ID -> eligibility cols
    patient_cols = [c for c in patients_df.columns]
    final_cols = patient_cols + ["Site_ID", "Eligible", "Reasons", "Missing_Data", "Confidence"]
    # Keep only unique and existing (guard)
    final_cols = [c for i, c in enumerate(final_cols) if c in merged.columns and c not in final_cols[:i]]
    all_roster = merged[final_cols].copy()

    # 5) Eligible-only view
    eligible_roster = all_roster[all_roster["Eligible"] == True].copy()

    return eligible_roster, all_roster


def _build_xlsx_bytes(
    site_ranking: pd.DataFrame,
    eligible_roster: pd.DataFrame,
    all_roster: pd.DataFrame,
    criteria_text: str,
) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        site_ranking.to_excel(writer, index=False, sheet_name="Site Ranking")
        eligible_roster.to_excel(writer, index=False, sheet_name="Eligible Patients Roster")
        all_roster.to_excel(writer, index=False, sheet_name="All Patients Roster")
        pd.DataFrame({"Extracted Criteria Text": [criteria_text]}).to_excel(
            writer, index=False, sheet_name="Extracted Criteria"
        )
    return out.getvalue()


# ----- Public API -----
def run_pipeline(
    pdf_bytes: bytes,
    patients_xlsx: bytes,
    map_xlsx: bytes,
    site_hist_xlsx: bytes,
) -> Tuple[bytes, Dict[str, Any]]:
    # 1) Criteria extraction with hash cache
    cache: Dict[str, Any] = {}
    # If you want a page range, pass start_page/end_page here
    # criteria_json = extract_or_load_criteria(pdf_bytes=pdf_bytes, cache_store=cache, start_page=37, end_page=41)
    criteria_text = extract_or_load_criteria_text(
        pdf_bytes=pdf_bytes,
        cache_store=cache,
        start_page=38,
        end_page=41,
    )

    # 2) Read Excel inputs (normalize headers, auto-detect header row)
    patients_df = _read_excel_bytes_auto_header(patients_xlsx, expected_cols=PATIENT_REQUIRED_COLS)
    map_df = _read_excel_bytes_auto_header(map_xlsx, expected_cols=MAPPING_REQUIRED_COLS)
    site_hist_df = _read_excel_bytes_auto_header(site_hist_xlsx, expected_cols=SITE_HISTORY_REQUIRED_COLS)

    # 2a) Validate headers (relaxed for mapping, minimal for site history)
    _validate_headers(patients_df, PATIENT_REQUIRED_COLS, context="Patients.xlsx")
    _validate_headers(map_df, MAPPING_REQUIRED_COLS, context="Patient↔Site mapping.xlsx")
    _validate_headers(site_hist_df, SITE_HISTORY_REQUIRED_COLS, context="Site history.xlsx")

    # 2b) Optional mapping columns: create if missing so downstream code never breaks
    for col in MAPPING_OPTIONAL_COLS:
        if col not in map_df.columns:
            map_df[col] = None

    # 2c) Sanity: Patient_ID must be unique
    if patients_df["Patient_ID"].duplicated().any():
        dups = patients_df.loc[patients_df["Patient_ID"].duplicated(), "Patient_ID"].unique().tolist()
        raise ValueError(f"Duplicate Patient_ID(s) in Patients.xlsx: {dups}")

    # 3) Evaluate eligibility in batches of 100 rows
    # elig_df, errors = evaluate_in_batches(criteria_json=criteria_json, patients_df=patients_df)
    elig_df, errors = evaluate_in_batches(criteria_text=criteria_text, patients_df=patients_df)

   
    # 4) Build rosters (keep Site_ID = NULL if mapping is missing)
    # eligible_roster, all_roster = _build_rosters(elig_df=elig_df, map_df=map_df)
    eligible_roster, all_roster = _build_rosters(patients_df=patients_df, elig_df=elig_df, map_df=map_df)

    # 5) Compute site ranking (Option A uses only siteId, status, screeningFailureRate)
    site_ranking = compute_site_ranking(elig_df=elig_df, map_df=map_df, site_hist_df=site_hist_df)

    # 6) Build XLSX (4 sheets)
    xlsx_bytes = _build_xlsx_bytes(
        site_ranking=site_ranking,
        eligible_roster=eligible_roster,
        all_roster=all_roster,
        criteria_text=criteria_text,
    )

    # 7) Metadata summary - count eligible patients (handle both boolean True and string "True")
    if "eligible" in elig_df.columns:
        # Count True (boolean) or "True" (string) as eligible
        eligible_count = int(((elig_df["eligible"] == True) | (elig_df["eligible"] == "True") | (elig_df["eligible"] == "true")).sum())
        inconclusive_count = int(((elig_df["eligible"] == "Inconclusive") | (elig_df["eligible"] == "inconclusive")).sum())
    else:
        eligible_count = 0
        inconclusive_count = 0
    
    meta = {
        "errors": errors,
        "counts": {
            "patients": int(len(patients_df)),
            "eligible_true": eligible_count,
            "inconclusive": inconclusive_count,
        },
    }
    return xlsx_bytes, meta

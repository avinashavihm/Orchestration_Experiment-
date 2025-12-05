from datetime import datetime
from pathlib import Path
import json
import pandas as pd
from ..config import settings


def _ensure_output_dir() -> None:
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


def _pretty_json_cell(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def write_results_xlsx(
    site_rank_df: pd.DataFrame,
    eligible_roster_df: pd.DataFrame,
    all_patients_roster_df: pd.DataFrame,
    criteria_json: dict,
    filename: str | None = None,
) -> str:
    """
    Version 3 writer: produces the 4 required sheets with exact names.

    Sheets:
      1) Site Ranking
      2) Eligible Patients Roster
      3) All Patients Roster
      4) Extracted Criteria  (single pretty-printed JSON cell)

    Returns: output file path (str)
    """
    _ensure_output_dir()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = filename or f"eligibility_results_v3_{ts}.xlsx"
    fpath = Path(settings.OUTPUT_DIR) / fname

    # Ensure expected columns exist (robustness)
    for df, cols in [
        (site_rank_df, ["Site_ID", "Eligible_Patient_Pool", "Site_Performance_Factor", "Enrollment_Probability", "Rank"]),
        (eligible_roster_df, ["Patient_ID", "Site_ID", "Eligible", "Reasons", "Missing_Data", "Confidence"]),
        (all_patients_roster_df, ["Patient_ID", "Site_ID", "Eligible", "Reasons", "Missing_Data", "Confidence"]),
    ]:
        for c in cols:
            if c not in df.columns:
                df[c] = None

    with pd.ExcelWriter(fpath, engine="openpyxl") as writer:
        site_rank_df.to_excel(writer, index=False, sheet_name="Site Ranking")
        # Eligible roster: only Eligible=True rows (just in case caller passed all patients)
        elig_only = eligible_roster_df[eligible_roster_df["Eligible"] == True].copy()
        elig_only.to_excel(writer, index=False, sheet_name="Eligible Patients Roster")
        all_patients_roster_df.to_excel(writer, index=False, sheet_name="All Patients Roster")

        # criteria as one pretty JSON cell
        crit_df = pd.DataFrame({"Extracted Criteria JSON": [_pretty_json_cell(criteria_json)]})
        crit_df.to_excel(writer, index=False, sheet_name="Extracted Criteria")

    return str(fpath)


# --------- Backward-compat wrapper (deprecated) ----------
def write_xlsx(
    site_rank_df: pd.DataFrame,
    eligible_patients_df: pd.DataFrame,
    criteria_dict: dict
) -> str:
    """
    DEPRECATED (kept for backward compatibility with older code paths).

    Older signature wrote:
      - Site Ranking
      - Eligible Patients (filtered inside)
      - Extracted Criteria (json_normalize)

    In V3 we need 4 sheets. This wrapper will:
      - Treat 'eligible_patients_df' as the FULL patients roster if it contains 'Eligible' column,
        else it will assume it's already filtered.
      - Build 'All Patients Roster' if possible; otherwise duplicate the eligible subset.
      - Write all 4 sheets using the new function.
    """
    # Try to detect if this is the full roster
    df = eligible_patients_df.copy()
    if "Eligible" in df.columns:
        # Build both rosters from provided df
        all_roster = df.copy()
        elig_roster = df[df["Eligible"] == True].copy()
    elif "eligible" in df.columns:
        # Old casing: build standardized columns
        df_std = df.rename(columns={
            "patient_id": "Patient_ID",
            "site_id": "Site_ID",
            "eligible": "Eligible",
            "reasons": "Reasons",
            "missing": "Missing_Data",
            "confidence": "Confidence",
        })
        all_roster = df_std.copy()
        elig_roster = df_std[df_std["Eligible"] == True].copy()
    else:
        # Fallback: we don't know; write what we can
        all_roster = df.copy()
        all_roster.rename(columns=str.title, inplace=True)
        elig_roster = all_roster.copy()
        if "Eligible" in elig_roster.columns:
            elig_roster = elig_roster[elig_roster["Eligible"] == True]
        else:
            # If no Eligible column, we can’t filter; keep as-is
            pass

    return write_results_xlsx(
        site_rank_df=site_rank_df,
        eligible_roster_df=elig_roster,
        all_patients_roster_df=all_roster,
        criteria_json=criteria_dict,
        filename=None,
    )


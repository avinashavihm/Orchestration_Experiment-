# app/services/site_ranking.py
import pandas as pd
from typing import Optional
from ..config import settings


def _normalize_sfr(val) -> float:
    """
    screeningFailureRate can be 0..1 or a percentage (>1).
    Missing -> 0.5 (neutral).
    """
    try:
        x = float(val)
    except Exception:
        return 0.5
    if x > 1.0:
        x = x / 100.0
    # clamp defensively
    if x < 0.0:
        x = 0.0
    if x > 1.0:
        x = 1.0
    return x


def _status_multiplier(val: Optional[str]) -> float:
    if val is None:
        return 0.0
    return settings.STATUS_MULTIPLIER.get(str(val).strip().lower(), 0.0)


def compute_site_ranking(elig_df: pd.DataFrame, map_df: pd.DataFrame, site_hist_df: pd.DataFrame) -> pd.DataFrame:
    """
    Version 3 ranking (Option A):

      SPF(site) = StatusMult(site) * (1 - SFR01(site))
        - StatusMult: Ongoing=1.0, Completed=0.8, Closed=0.0, Terminated=0.0
        - SFR01: screeningFailureRate in 0..1 (if >1, treat as percentage)
        - Missing SFR -> 0.5
        - Site missing in history -> SPF = settings.DEFAULT_SITE_PERF_FACTOR

      Enrollment_Probability(site) = Eligible_Pool(site) * SPF(site)

    Inputs:
      elig_df columns:   ["patient_id", "eligible", ...]
      map_df columns:    ["Patient_ID", "Site_ID", ...]
      site_hist_df cols: ["siteId", "status", "screeningFailureRate", ...]
    """
    # 1) Eligible pool per site (join eligibility -> mapping)
    elig_only = elig_df[elig_df["eligible"] == True].copy()
    elig_only = elig_only.merge(
        map_df[["Patient_ID", "Site_ID"]],
        left_on="patient_id",
        right_on="Patient_ID",
        how="left",
    )

    # Count eligible patients per site; exclude Site_ID = NULL from ranking
    pool = (
        elig_only[~elig_only["Site_ID"].isna()]
        .groupby("Site_ID", dropna=False)
        .size()
        .reset_index(name="Eligible_Patient_Pool")
    )

    # 2) Prepare site history with SPF
    sh = site_hist_df.copy()
    # normalize column names (use exactly provided headers)
    if "status" not in sh.columns or "screeningFailureRate" not in sh.columns or "siteId" not in sh.columns:
        missing = [c for c in ["siteId", "status", "screeningFailureRate"] if c not in sh.columns]
        raise ValueError(f"site_hist_df missing required columns: {missing}")

    sh["StatusMult"] = sh["status"].map(_status_multiplier)
    sh["SFR01"] = sh["screeningFailureRate"].map(_normalize_sfr)
    sh["Site_Performance_Factor"] = sh["StatusMult"] * (1.0 - sh["SFR01"])

    # 3) Merge pool with SPF; default SPF when site not found
    base = pool.merge(
        sh[["siteId", "Site_Performance_Factor"]],
        left_on="Site_ID",
        right_on="siteId",
        how="left",
    )
    base["Site_Performance_Factor"] = base["Site_Performance_Factor"].fillna(settings.DEFAULT_SITE_PERF_FACTOR)

    # 4) Enrollment Probability and Rank
    base["Enrollment_Probability"] = base["Eligible_Patient_Pool"] * base["Site_Performance_Factor"]

    base = base.sort_values(
        ["Enrollment_Probability", "Site_Performance_Factor", "Eligible_Patient_Pool"],
        ascending=[False, False, False],
        kind="mergesort",
    ).reset_index(drop=True)
    base["Rank"] = base.index + 1

    # 5) Final columns in required order
    out = base[["Site_ID", "Eligible_Patient_Pool", "Site_Performance_Factor", "Enrollment_Probability", "Rank"]].copy()
    return out


# ---------- Backward-compat wrapper (optional) ----------
def build_site_ranking(patients_df: pd.DataFrame, site_hist_df: pd.DataFrame) -> pd.DataFrame:
    """
    Legacy wrapper to support older calls that passed a DataFrame with
    columns ["site_id", "eligible"] only.

    This wrapper:
      - Renames "site_id" -> "Site_ID"
      - Builds a minimal elig_df with ["patient_id","eligible"] (patient_id unknown)
      - Delegates to compute_site_ranking with an empty mapping (Site_ID already present)

    Note: In V3, prefer compute_site_ranking(elig_df, map_df, site_hist_df).
    """
    if "site_id" not in patients_df.columns or "eligible" not in patients_df.columns:
        raise ValueError("patients_df must include columns: ['site_id', 'eligible']")

    # Build a minimal elig_df (no patient_id available here)
    # We synthesize a unique patient_id just to satisfy the schema, though it's not used for pooling in this path.
    temp = patients_df.copy()
    temp = temp.rename(columns={"site_id": "Site_ID"})
    temp["patient_id"] = range(len(temp))  # synthetic
    elig_df = temp[["patient_id", "eligible"]].copy()

    # Minimal mapping that already has Site_ID aligned
    map_df = temp[["patient_id", "Site_ID"]].rename(columns={"patient_id": "Patient_ID"})  # key names to satisfy signature

    return compute_site_ranking(elig_df=elig_df, map_df=map_df, site_hist_df=site_hist_df)


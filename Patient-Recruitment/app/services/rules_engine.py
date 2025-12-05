# from typing import Any, Dict
# import pandas as pd
# import numpy as np
# import re
# import json
# import re



# # Supported ops: eq, neq, gt, gte, lt, lte, in, contains, regex, between, exists, true, false

# def _coerce(val):
#     # try numeric; else return as-is
#     try:
#         if pd.isna(val): return np.nan
#         return float(val)
#     except Exception:
#         return val

# def _match_op(series: pd.Series, rule: Dict[str, Any]) -> pd.Series:
#     op = rule.get("op")
#     field = rule.get("field")
#     value = rule.get("value", None)
#     s = series[field]

#     if op in ("true", "false"):
#         target = (op == "true")
#         return s.astype(str).str.lower().isin(["true", "1", "yes", "y"]) if target \
#                else s.astype(str).str.lower().isin(["false", "0", "no", "n"])

#     if op == "exists":
#         return ~s.isna() & (s.astype(str).str.len() > 0)

#     if op == "contains":
#         return s.astype(str).str.contains(str(value), case=False, na=False)

#     if op == "regex":
#         return s.astype(str).str.contains(re.compile(str(value)), na=False)

#     if op == "in":
#         vals = set([str(v).lower() for v in value]) if isinstance(value, (list, tuple, set)) else {str(value).lower()}
#         return s.astype(str).str.lower().isin(vals)

#     if op == "between":
#         lo = value.get("min", None)
#         hi = value.get("max", None)
#         sn = pd.to_numeric(s, errors="coerce")
#         mask = pd.Series(True, index=sn.index)
#         if lo is not None: mask &= (sn >= float(lo))
#         if hi is not None: mask &= (sn <= float(hi))
#         return mask.fillna(False)

#     # numeric/equality ops
#     left = s
#     right = value
#     # attempt numeric compare
#     ln = pd.to_numeric(left, errors="coerce")
#     rn = None
#     try:
#         rn = float(right)
#         numeric_ok = True
#     except Exception:
#         numeric_ok = False

#     if op == "eq":
#         if numeric_ok:
#             return (ln == rn).fillna(False)
#         return left.astype(str).str.lower().eq(str(right).lower()).fillna(False)

#     if op == "neq":
#         if numeric_ok:
#             return (ln != rn).fillna(False)
#         return ~left.astype(str).str.lower().eq(str(right).lower()).fillna(False)

#     if op in ("gt", "gte", "lt", "lte"):
#         if not numeric_ok:
#             # fallback string comparison
#             if op == "gt":  return (left.astype(str) >  str(right)).fillna(False)
#             if op == "gte": return (left.astype(str) >= str(right)).fillna(False)
#             if op == "lt":  return (left.astype(str) <  str(right)).fillna(False)
#             if op == "lte": return (left.astype(str) <= str(right)).fillna(False)
#         else:
#             if op == "gt":  return (ln >  rn).fillna(False)
#             if op == "gte": return (ln >= rn).fillna(False)
#             if op == "lt":  return (ln <  rn).fillna(False)
#             if op == "lte": return (ln <= rn).fillna(False)

#     # default deny (be conservative)
#     return pd.Series(False, index=s.index)

# def apply_criteria(df: pd.DataFrame, criteria: dict) -> pd.DataFrame:
#     # # --- Step 1: normalize incoming data (strip whitespace from strings) ---
#     # df = df.copy()
#     # obj_cols = df.select_dtypes(include=["object"]).columns
#     # if len(obj_cols) > 0:
#     #     df[obj_cols] = df[obj_cols].apply(lambda s: s.astype(str).str.strip())

#     # inc = criteria.get("inclusion", []) or []
#     # exc = criteria.get("exclusion", []) or []

#     # # --- Initialize masks before applying rules ---
#     # mask_inc = pd.Series(True, index=df.index)
#     # mask_exc = pd.Series(False, index=df.index)

#     # --- normalize incoming data ---
#     df = df.copy()
#     obj_cols = df.select_dtypes(include=["object"]).columns
#     if len(obj_cols) > 0:
#         df[obj_cols] = df[obj_cols].apply(lambda s: s.astype(str).str.strip())

#     # ---- NEW: semantic normalization so strict rules can pass ----
#     # 1) diagnosis → canonical if it mentions T. cruzi / Chagas
#     if "diagnosis" in df.columns:
#         diag = df["diagnosis"].str.lower()
#         canonical = []
#         for x in diag.fillna(""):
#             if ("t. cruzi" in x) or ("trypanosoma cruzi" in x) or ("chagas" in x):
#                 canonical.append("t. cruzi infection")
#             else:
#                 canonical.append(x.strip())
#         df["diagnosis"] = pd.Series(canonical, index=df.index)

#     # 2) residence_or_travel_history → canonical phrase if equivalent
#     if "residence_or_travel_history" in df.columns:
#         r = df["residence_or_travel_history"].str.lower()
#         canon_r = []
#         for x in r.fillna(""):
#             if ("vectorial transmission free area" in x) or ("free of vectorial transmission" in x):
#                 canon_r.append("free of vectorial transmission")
#             else:
#                 canon_r.append(x.strip())
#         df["residence_or_travel_history"] = pd.Series(canon_r, index=df.index)

#     # 3) cardiac_eval JSON → compute "normal EKG" if thresholds satisfied
#     # Inclusion requires: PR ≤200 ms, QRS <120 ms, QTc 350–450 (males) / ≤470 (females)
#     if "cardiac_eval" in df.columns:
#         def _calc_cardiac_status(row):
#             raw = str(row.get("cardiac_eval", "")).strip()
#             gender = str(row.get("gender", "")).strip().lower()
#             # If the field already is a simple label
#             if raw.lower() in ("normal ekg", "normal ecg"):
#                 return "normal EKG"
#             # Try parse JSON-ish content
#             if raw.startswith("{") and raw.endswith("}"):
#                 try:
#                     data = json.loads(raw)
#                     ecg_abnormal = bool(data.get("ecg_abnormal", False))
#                     pr = float(data.get("pr_interval_ms", np.nan))
#                     qrs = float(data.get("qrs_duration_ms", np.nan))
#                     qtc = float(data.get("qtc_interval_ms", np.nan))
#                     if ecg_abnormal:
#                         return raw  # keep as-is (abnormal)
#                     if not (np.isfinite(pr) and np.isfinite(qrs) and np.isfinite(qtc)):
#                         return raw  # insufficient info
#                     if pr <= 200 and qrs < 120:
#                         # gender-specific QTc
#                         if gender == "male" or gender == "m":
#                             if 350 <= qtc <= 450:
#                                 return "normal EKG"
#                         else:
#                             # treat non-male as female bounds
#                             if 350 <= qtc <= 470:
#                                 return "normal EKG"
#                     return raw
#                 except Exception:
#                     return raw
#             return raw

#         df["cardiac_eval"] = df.apply(_calc_cardiac_status, axis=1)
#       # 4) Normalize T_cruzi_PCR and T_cruzi_serology to boolean-style strings
#     for col in ["T_cruzi_PCR", "T_cruzi_serology"]:
#         if col in df.columns:
#             v = df[col].astype(str).str.lower().str.strip()
#             df[col] = v.replace(
#                 {
#                     "positive": "true",
#                     "pos": "true",
#                     "yes": "true",
#                     "1": "true",
#                     "negative": "false",
#                     "neg": "false",
#                     "no": "false",
#                     "0": "false"
#                 }
#             )
#     if "pregnancy_test" in df.columns:
#         v = df["pregnancy_test"].astype(str).str.lower().str.strip()
#         df["pregnancy_test"] = v.replace({
#             "negative": "false",
#             "neg": "false",
#             "positive": "true",
#             "pos": "true"
#         })
#     # --------------------------------------------------------------
#     inc = criteria.get("inclusion", []) or []
#     exc = criteria.get("exclusion", []) or []

#     mask_inc = pd.Series(True, index=df.index)
#     mask_exc = pd.Series(False, index=df.index)

#     print("\nApplying inclusion rules...")
#     for rule in inc:
#         if rule.get("field") in df.columns:
#             result = _match_op(df, rule)
#             print(rule, "->", result.values)
#             mask_inc &= result

#     print("\nApplying exclusion rules...")
#     for rule in exc:
#         if rule.get("field") in df.columns:
#             result = _match_op(df, rule)
#             print(rule, "->", result.values)
#             mask_exc |= result

#     eligible = mask_inc & ~mask_exc
#     out = df.copy()
#     out["eligible"] = eligible
#     out["eligibility_reason"] = np.where(
#         eligible,
#         "Meets inclusion & not excluded",
#         "Fails inclusion or meets exclusion"
#     )
#     print(f"Checking eligibility")
#     return out


import re
import pandas as pd
import numpy as np
import json

# --- helper: numeric coercion ---
def _num(x):
    try:
        return float(x)
    except Exception:
        return np.nan

# --- helper: interpret and evaluate one text criterion ---
def _eval_text_rule(df, line: str, positive=True) -> pd.Series:
    """
    Convert a natural language criterion line into a boolean mask over df.
    positive=True means inclusion, False means exclusion.
    """
    line = line.strip().lower()

    # Start with all True for inclusion, all False for exclusion
    mask = pd.Series(True if positive else False, index=df.index)

    # AGE
    if "age" in line:
        m = re.findall(r'(\d+)', line)
        if len(m) == 2:   # range
            lo, hi = map(float, m)
            mask = (df["Age"] >= lo) & (df["Age"] <= hi)
        elif "≥" in line or ">" in line or "older" in line:
            val = float(m[0]) if m else 18
            mask = df["Age"] >= val
        elif "≤" in line or "<" in line or "younger" in line:
            val = float(m[0]) if m else 65
            mask = df["Age"] <= val

    # WEIGHT
    elif "weight" in line:
        m = re.findall(r'(\d+)', line)
        if len(m) == 2:
            lo, hi = map(float, m)
            mask = (df["Weight"] >= lo) & (df["Weight"] <= hi)
        elif ">" in line or "≥" in line:
            mask = df["Weight"] >= _num(m[0])
        elif "<" in line or "≤" in line:
            mask = df["Weight"] <= _num(m[0])

    # GENDER
    elif "female" in line and "male" not in line:
        mask = df["gender"].str.lower().str.contains("female", na=False)
    elif "male" in line and "female" not in line:
        mask = df["gender"].str.lower().str.contains("male", na=False)

    # CONSENT
    elif "consent" in line:
        mask = df["consent_signed"].astype(str).str.lower().isin(["true", "yes", "1"])

    # PCR / SEROLOGY
    elif "pcr" in line or "serology" in line or "t. cruzi" in line:
        cols = [c for c in df.columns if "pcr" in c.lower() or "serology" in c.lower()]
        if cols:
            submasks = []
            for c in cols:
                s = df[c].astype(str).str.lower()
                positive_hits = s.str.contains("positive|pos|true|detected", na=False)
                submasks.append(positive_hits)
            mask = np.logical_or.reduce(submasks)

    # PREGNANCY / CONTRACEPTION
    elif "pregnan" in line:
        mask = ~df["pregnancy_test"].astype(str).str.lower().isin(["positive", "true", "1"])
    elif "contraception" in line or "barrier method" in line:
        mask = df["contraception_agreement"].astype(str).str.lower().isin(["true", "yes", "1"])

    # CARDIAC / EKG
    elif "ekg" in line or "ecg" in line or "cardiac" in line:
        mask = df["cardiac_eval"].astype(str).str.lower().str.contains("normal", na=False)

    # HIV / CREATININE / HEART FAILURE (exclusion heavy)
    elif "hiv" in line:
        mask = ~df["hiv_status"].astype(str).str.lower().isin(["true", "positive", "yes"])
    elif "creatinin" in line:
        mask = df["lab_Creatinine"].astype(float) < 1.1
    elif "heart failure" in line or "cardiomyopathy" in line:
        mask = ~df["cardiac_eval"].astype(str).str.lower().str.contains("failure|cardiomyopathy", na=False)

    # fallback: if phrase exists as substring of any column
    else:
        matched = None
        for c in df.columns:
            if c.lower().replace("_", " ") in line:
                matched = c
                break
        if matched:
            s = df[matched].astype(str).str.lower()
            # heuristic: "no"/"negative" in inclusion means True if not containing those words
            if "no " in line or "negative" in line:
                mask = ~s.str.contains("positive|true|1|yes", na=False)
            elif "positive" in line or "detected" in line:
                mask = s.str.contains("positive|true|1|yes", na=False)

        # --- ensure consistent Series return ---
    if isinstance(mask, np.ndarray):
        mask = pd.Series(mask, index=df.index)
    elif not isinstance(mask, pd.Series):
        mask = pd.Series([bool(mask)] * len(df), index=df.index)

    return mask.fillna(False)



def apply_criteria(df: pd.DataFrame, criteria: dict) -> pd.DataFrame:
    """
    criteria format expected:
    {
      "inclusion": ["Criterion sentence 1", "Criterion sentence 2", ...],
      "exclusion": ["Criterion sentence 1", "Criterion sentence 2", ...]
    }
    """

    df = df.copy()
    # strip whitespace for object columns
    obj_cols = df.select_dtypes(include=["object"]).columns
    if len(obj_cols) > 0:
        df[obj_cols] = df[obj_cols].apply(lambda s: s.astype(str).str.strip())

    inc = criteria.get("inclusion", []) or []
    exc = criteria.get("exclusion", []) or []

    mask_inc = pd.Series(True, index=df.index)
    mask_exc = pd.Series(False, index=df.index)

    print("\nApplying inclusion criteria:")
    for crit in inc:
        rule_mask = _eval_text_rule(df, crit, positive=True)
        print(f"{crit} -> {rule_mask.values}")
        mask_inc &= rule_mask

    print("\nApplying exclusion criteria:")
    for crit in exc:
        rule_mask = _eval_text_rule(df, crit, positive=False)
        print(f"{crit} -> {rule_mask.values}")
        mask_exc |= ~rule_mask  # if fails exclusion condition, mark as excluded

    eligible = mask_inc & ~mask_exc
    df["eligible"] = eligible
    df["eligibility_reason"] = np.where(
        eligible,
        "Meets inclusion & not excluded",
        "Fails inclusion or meets exclusion"
    )
    return df

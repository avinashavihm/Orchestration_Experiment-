import json
from typing import Any, Dict, List, Tuple
import google.generativeai as genai
import pandas as pd

from ..config import settings








genai.configure(api_key=settings.GEMINI_API_KEY)

SHORT_KEYS = {
    "Patient_ID": "pid",
    "Age": "age",
    "Weight_kg": "wt",
    "T_cruzi_Diagnosis": "dx",   # "C" or "NC"
    "Informed_Consent_Signed": "consent",       # 1/0
    "Lives_in_Vector_Free_Area": "vector_free", # 1/0
    "Chronic_Chagas_Symptoms": "chronic",       # 1/0
    "Previous_Chagas_Treatment": "prev_tx",     # 1/0
    "History_of_Azole_Hypersensitivity": "azole_hx", # 1/0
    "Concomitant_CYP3A4_Meds": "cyp3a4",       # 1/0
}

def _to01(v):
    s = str(v).strip().lower()
    return "1" if s in {"yes","y","true","1"} else ("0" if s in {"no","n","false","0"} else "")

def _dx_code(v):
    s = str(v).strip().lower()
    return "C" if s == "confirmed" else ("NC" if s else "")

def _rows_to_csv(rows: list[dict]) -> str:
    cols = [k for k in SHORT_KEYS.keys() if rows and k in rows[0]]
    lines = [",".join(SHORT_KEYS[c] for c in cols)]
    for r in rows:
        vals = []
        for c in cols:
            val = r.get(c, "")
            if c in ("Informed_Consent_Signed","Lives_in_Vector_Free_Area","Chronic_Chagas_Symptoms",
                     "Previous_Chagas_Treatment","History_of_Azole_Hypersensitivity","Concomitant_CYP3A4_Meds"):
                val = _to01(val)
            elif c == "T_cruzi_Diagnosis":
                val = _dx_code(val)
            else:
                val = str(val).replace("\n"," ").replace(","," ")
            vals.append(val)
        lines.append(",".join(vals))
    return "\n".join(lines)

def _build_batch_prompt(criteria_text: str, rows: List[Dict[str, Any]]) -> str:
    N = len(rows)
    csv = _rows_to_csv(rows)
    return (
        "You are screening de-identified records for research eligibility only. "
        "Do NOT give medical advice. Return ONLY the JSON array described below.\n\n"

        "INPUTS\n"
        "- CRITERIA_TEXT with headings 'Inclusion Criteria:' and 'Exclusion Criteria:' and bracketed items.\n"
        f"- PATIENT_ROWS (N={N}) as CSV with columns: {', '.join(SHORT_KEYS.values())}\n\n"

        "DECISION RULES\n"
        "- ELIGIBLE only if ALL inclusion pass AND NO exclusion is violated.\n"
        "- 'between X and Y' and 'X to Y' are inclusive (≤/≥) unless explicitly 'strictly'.\n"
        "- If a ULN-dependent check is required but ULN is missing, set eligible = \"Inconclusive\".\n"
        "- Use ONLY provided data; do not invent values.\n\n"

        "OUTPUT FORMAT (STRICT JSON, NO MARKDOWN; EXACTLY " + str(N) + " items, same order as input):\n"
        "[\n"
        "  {\"patient_id\":\"<pid>\",\n"
        "   \"eligible\": true|false|\"Inconclusive\",\n"
        "   \"reasons\": [\n"
        "       \"incl: <short reason>\" | \"excl: <short reason>\" | \"insufficient_data\" | \"uln_missing\"\n"
        "   ],\n"
        "   \"missing\": [\"age\"|\"wt\"|\"dx\"|\"consent\"|\"vector_free\"|\"chronic\"|\"prev_tx\"|\"azole_hx\"|\"cyp3a4\"],\n"
        "   \"confidence\": 0.0\n"
        "  }\n"
        "]\n\n"
        "REASON CONSTRAINTS\n"
        "- Put at most 2 items in 'reasons'.\n"
        "- Each reason ≤ 60 chars, ASCII only, NO double quotes; use apostrophes instead if needed.\n"
        "- Examples: \"incl: age <18 (needs >=18)\", \"excl: prior azole hypersensitivity\".\n"
        "- Do NOT paste full criterion text; use a short paraphrase like above.\n\n"

        "NOW RETURN ONLY THE JSON ARRAY (no prose, no code fences). Begin with '[' and end with ']'.\n\n"

        "CRITERIA_TEXT:\n"
        f"{criteria_text}\n\n"

        "PATIENT_ROWS CSV:\n"
        f"{csv}\n"
    )


# def _build_batch_prompt(criteria_text: str, rows: List[Dict[str, Any]]) -> str:
#     N = len(rows)
#     return (
#         "You are screening de-identified records for research eligibility only. "
#         "Do NOT provide advice. Return only the JSON array described.\n\n"
#         "INPUTS:\n"
#         "• CRITERIA_TEXT with headings 'Inclusion Criteria:' and 'Exclusion Criteria:' and bracketed items.\n"
#         f"• PATIENT_ROWS (N={N}) as key/value pairs.\n\n"
#         "EVALUATION RULES:\n"
#         "- ELIGIBLE only if ALL inclusion pass AND NO exclusion is violated.\n"
#         "- Treat 'between X and Y' and 'X to Y' as inclusive (≤/≥) unless explicitly 'strictly'.\n"
#         "- If any ULN-dependent check is required but ULN is missing, set eligible = \"Inconclusive\".\n"
#         "- Use only provided data; do not invent values.\n\n"
#         "OUTPUT (strict JSON, no markdown; JSON array of EXACTLY " + str(N) + " items, same order as input):\n"
#         "[\n"
#         "  {\"patient_id\":\"<Patient_ID>\","
#         "\"eligible\":true|false|\"Inconclusive\","
#         "\"reasons\":[\"short reason 1\",\"short reason 2\"],"
#         "\"missing\":[\"field1\",\"field2\"],"
#         "\"confidence\":0.0}\n"
#         "]\n\n"
#         "CRITERIA_TEXT:\n"
#         f"{criteria_text}\n\n"
#         "PATIENT_ROWS:\n"
#         f"{json.dumps(rows, ensure_ascii=False)}\n"
#     )

# def _gemini_call(prompt: str) -> str:
#     model = genai.GenerativeModel(
#         model_name=settings.GEMINI_MODEL,
#         generation_config={
#             "temperature": settings.LLM_TEMPERATURE,
#             "max_output_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
#             "response_mime_type": settings.LLM_RESPONSE_MIME_TYPE,  # ask for raw JSON
#         },
#     )
#     resp = model.generate_content(prompt)
#     return (resp.text or "").strip()
def _gemini_call(prompt: str) -> str:
    """Call Gemini API with timeout protection."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
    
    def _call_api():
        """Internal function to make the actual API call."""
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config={
                "temperature": settings.LLM_TEMPERATURE,
                "max_output_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
            },
        )
        return model.generate_content(prompt)
    
    try:
        # Use ThreadPoolExecutor for timeout handling (works on all platforms)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call_api)
            try:
                resp = future.result(timeout=settings.LLM_TIMEOUT_SECS)
            except FutureTimeoutError:
                future.cancel()
                raise TimeoutError(f"Gemini API call timed out after {settings.LLM_TIMEOUT_SECS} seconds")
    except TimeoutError:
        raise
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}")

    # Join text from all parts across candidates
    chunks = []
    for cand in getattr(resp, "candidates", []) or []:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        for p in parts:
            t = getattr(p, "text", None)
            if not t and isinstance(p, dict):
                t = p.get("text")
            if isinstance(t, str) and t.strip():
                chunks.append(t.strip())

    return "\n".join(chunks).strip()




# def _gemini_call(prompt: str) -> Tuple[str, List[str]]:
#     """
#     Returns (text, safety_reasons). If response is blocked or empty, text == "" and reasons are populated.
#     """
#     last_err = None
#     for _ in range(settings.LLM_MAX_RETRIES):
#         try:
#             model = genai.GenerativeModel(
#                 settings.GEMINI_MODEL,
#                 generation_config={
#                     "temperature": settings.LLM_TEMPERATURE,
#                     "max_output_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
#                 },
#             )
#             resp = model.generate_content(prompt)

#             # Try safe text extraction
#             text = ""
#             try:
#                 # resp.text sometimes raises when blocked
#                 if getattr(resp, "text", None):
#                     text = (resp.text or "").strip()
#             except Exception:
#                 text = ""

#             safety_reasons = []
#             try:
#                 # Collect any safety reasons
#                 cands = getattr(resp, "candidates", None) or []
#                 for c in cands:
#                     # blocked candidates may have safety_ratings / finish_reason
#                     ratings = getattr(c, "safety_ratings", None) or []
#                     for r in ratings:
#                         if getattr(r, "blocked", False) or getattr(r, "probability", "") in ("HIGH", "MEDIUM"):
#                             # best-effort stringification across SDK versions
#                             cat = getattr(r, "category", "UNKNOWN")
#                             safety_reasons.append(str(cat))
#                     # If no resp.text but parts might exist, try parts
#                     if not text:
#                         parts = getattr(getattr(c, "content", None), "parts", None) or []
#                         for p in parts:
#                             if getattr(p, "text", None):
#                                 text = (p.text or "").strip()
#                                 break
#             except Exception:
#                 pass

#             return text, safety_reasons

#         except Exception as e:
#             last_err = e
#             time.sleep(1.0)

#     raise RuntimeError(f"Gemini call failed after {settings.LLM_MAX_RETRIES} retries: {last_err}")


# def _strip_code_fences(s: str) -> str:
#     s = s.strip()
#     if s.startswith("```"):
#         # remove leading ``` or ```json and trailing ```
#         import re
#         s = re.sub(r'^```[a-zA-Z]*\s*', '', s)
#         s = re.sub(r'\s*```$', '', s)
#     return s.strip()


def evaluate_in_batches(criteria_text: str, patients_df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    import re

    def _extract_first_json_array(s: str):
        """Return (list_obj, err_str_or_None) by extracting the first top-level JSON array from s.
        Tries to recover partial results if array is incomplete."""
        if not s:
            return None, "empty"
        
        # First, try to find and parse complete array
        # find first '[' followed by '{' (start of array of objects)
        m = re.search(r'\[\s*{', s, re.S)
        if not m:
            return None, "no_array_start"
        start = m.start()  # at '['
        
        # Try to find complete array by matching brackets
        depth = 0
        array_end = -1
        for i, ch in enumerate(s[start:], start=start):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    array_end = i + 1
                    break
        
        # If we found a complete array, try to parse it
        if array_end > start:
            try:
                return json.loads(s[start:array_end]), None
            except Exception as e:
                # Array structure looks complete but JSON is invalid, continue to recovery
                pass
        
        # Recovery: Try to extract complete objects from incomplete array
        # Find all complete JSON objects in the string
        objects = []
        i = start + 1  # Start after '['
        while i < len(s):
            # Find next '{'
            obj_start = s.find('{', i)
            if obj_start == -1:
                break
            
            # Try to find matching '}'
            obj_depth = 0
            obj_end = -1
            for j in range(obj_start, len(s)):
                if s[j] == '{':
                    obj_depth += 1
                elif s[j] == '}':
                    obj_depth -= 1
                    if obj_depth == 0:
                        obj_end = j + 1
                        break
            
            if obj_end > obj_start:
                # Try to parse this object
                try:
                    obj_str = s[obj_start:obj_end]
                    obj = json.loads(obj_str)
                    objects.append(obj)
                    i = obj_end
                except:
                    i = obj_start + 1
            else:
                break
        
        # If we found any complete objects, return them
        if objects:
            return objects, None
        
        return None, "unterminated_array"

    if "Patient_ID" not in patients_df.columns:
        raise ValueError("patients_df must include 'Patient_ID' column")

    df = patients_df
    outputs: List[Dict[str, Any]] = []
    errors: List[str] = []

    total_batches = (len(df) + settings.BATCH_SIZE - 1) // settings.BATCH_SIZE
    
    for batch_num, start in enumerate(range(0, len(df), settings.BATCH_SIZE), 1):
        chunk = df.iloc[start : start + settings.BATCH_SIZE].copy()
        rows = chunk.to_dict(orient="records")
        prompt = _build_batch_prompt(criteria_text, rows)
        
        print(f"[Batch {batch_num}/{total_batches}] Processing patients {start} to {start+len(chunk)-1}...")
        
        # Retry logic for empty responses
        max_retries = 2
        resp_text = None
        for retry in range(max_retries + 1):
            try:
                resp_text = _gemini_call(prompt)
                print(f"[Batch {batch_num}/{total_batches}] Received response ({len(resp_text)} chars)")
                if resp_text and resp_text.strip():  # If we got a non-empty response, break
                    break
                elif retry < max_retries:
                    print(f"[Batch {batch_num}/{total_batches}] Empty response, retrying ({retry + 1}/{max_retries})...")
                    import time
                    time.sleep(1)  # Brief delay before retry
            except TimeoutError as e:
                error_msg = f"Batch {start}-{start+len(chunk)-1} timed out after {settings.LLM_TIMEOUT_SECS}s: {e}"
                print(f"[ERROR] {error_msg}")
                if retry == max_retries:  # Only add error and mark as inconclusive on final retry
                    errors.append(error_msg)
                    for r in rows:
                        outputs.append({
                            "patient_id": r.get("Patient_ID"),
                            "eligible": "Inconclusive",
                            "reasons": [],
                            "missing": ["LLM call timeout"],
                            "confidence": None,
                        })
                    break
                elif retry < max_retries:
                    print(f"[Batch {batch_num}/{total_batches}] Retrying after timeout ({retry + 1}/{max_retries})...")
                    import time
                    time.sleep(2)  # Longer delay for timeouts
                continue
            except Exception as e:
                error_msg = f"Batch {start}-{start+len(chunk)-1} failed: {e}"
                print(f"[ERROR] {error_msg}")
                if retry == max_retries:  # Only add error and mark as inconclusive on final retry
                    errors.append(error_msg)
                    for r in rows:
                        outputs.append({
                            "patient_id": r.get("Patient_ID"),
                            "eligible": "Inconclusive",
                            "reasons": [],
                            "missing": ["LLM call failure"],
                            "confidence": None,
                        })
                    break
                elif retry < max_retries:
                    print(f"[Batch {batch_num}/{total_batches}] Retrying after error ({retry + 1}/{max_retries})...")
                    import time
                    time.sleep(2)  # Longer delay for errors
                continue

        # Check if we still have an empty response after retries
        if not resp_text or not resp_text.strip():
            errors.append(f"Batch {start}-{start+len(chunk)-1} empty response (likely prompt too large).")
            for r in rows:
                outputs.append({
                    "patient_id": r.get("Patient_ID"),
                    "eligible": "Inconclusive",
                    "reasons": [],
                    "missing": ["Empty LLM response"],
                    "confidence": None,
                })
            continue

        # tolerate code fences if model adds them
        if resp_text.startswith("```"):
            import re as _re
            resp_text = _re.sub(r'^```[a-zA-Z]*\s*', '', resp_text)
            resp_text = _re.sub(r'\s*```$', '', resp_text).strip()
        print("RESPONSE code fences\n")
        print(resp_text[:300])
        # Parse exactly the first JSON array; NO post-processing of items
        parsed, jerr = _extract_first_json_array(resp_text)
        if jerr or not isinstance(parsed, list):
            errors.append(f"Batch {start}-{start+len(chunk)-1} JSON extract error: {jerr or 'not_list'} | head: {resp_text[:200]}")
            for r in rows:
                outputs.append({
                    "patient_id": r.get("Patient_ID"),
                    "eligible": "Inconclusive",
                    "reasons": [],
                    "missing": ["LLM JSON parse error"],
                    "confidence": None,
                })
            continue
        
        # Log if we got partial results (fewer than expected)
        if len(parsed) < len(rows):
            print(f"[WARNING] Batch {start}-{start+len(chunk)-1} got partial results: {len(parsed)}/{len(rows)} patients")
            errors.append(f"Batch {start}-{start+len(chunk)-1} partial results: got {len(parsed)}/{len(rows)} (response may have been truncated)")
        
        print(f"[Batch {batch_num}/{total_batches}] Parsed {len(parsed)} results")

        # Push items THROUGH AS-IS (only ensure we have a patient_id)
        for idx in range(len(rows)):
            r = rows[idx]
            item = parsed[idx] if idx < len(parsed) else {}
            outputs.append({
                "patient_id": item.get("patient_id") or r.get("Patient_ID"),
                "eligible": item.get("eligible"),
                "reasons": item.get("reasons"),
                "missing": item.get("missing"),
                "confidence": item.get("confidence"),
            })

    out_df = pd.DataFrame(outputs)

    # Ensure expected columns exist (no coercion/rounding/cleaning)
    for col in ["patient_id", "eligible", "reasons", "missing", "confidence"]:
        if col not in out_df.columns:
            out_df[col] = None

    return out_df, errors

# def evaluate_in_batches(criteria_text: str, patients_df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
#     if "Patient_ID" not in patients_df.columns:
#         raise ValueError("patients_df must include 'Patient_ID' column")

#     df = patients_df
#     outputs: List[Dict[str, Any]] = []
#     errors: List[str] = []

#     for start in range(0, len(df), settings.BATCH_SIZE):
#         chunk = df.iloc[start : start + settings.BATCH_SIZE].copy()
#         rows = chunk.to_dict(orient="records")
#         prompt = _build_batch_prompt(criteria_text, rows)

#         try:
#             resp_text = _gemini_call(prompt)
#         except Exception as e:
#             errors.append(f"Batch {start}-{start+len(chunk)-1} failed: {e}")
#             # ensure one result per input row
#             for r in rows:
#                 outputs.append({
#                     "patient_id": r.get("Patient_ID"),
#                     "eligible": "Inconclusive",
#                     "reasons": [],
#                     "missing": ["LLM call failure"],
#                     "confidence": None,
#                 })
#             continue
#         if not resp_text:
#             errors.append(f"Batch {start}-{start+len(chunk)-1} empty response (likely prompt too large).")
#             for r in rows:
#                 outputs.append({
#                     "patient_id": r.get("Patient_ID"),
#                     "eligible": "Inconclusive",
#                     "reasons": [],
#                     "missing": ["Empty LLM response"],
#                     "confidence": None,
#                 })
#             continue

        
#         # tolerate code fences if model adds them
#         if resp_text.startswith("```"):
#             import re
#             resp_text = re.sub(r'^```[a-zA-Z]*\s*', '', resp_text)
#             resp_text = re.sub(r'\s*```$', '', resp_text).strip()
#         print("RESPONSE\n")
#         print(resp_text[:300])
#         try:
#             parsed = json.loads(resp_text)
#             if not isinstance(parsed, list):
#                 raise ValueError("Expected a JSON array.")
#         except Exception as e:
#             errors.append(f"Batch {start}-{start+len(chunk)-1} JSON parse error: {e} | head: {resp_text[:200]}")
#             for r in rows:
#                 outputs.append({
#                     "patient_id": r.get("Patient_ID"),
#                     "eligible": "Inconclusive",
#                     "reasons": [],
#                     "missing": ["LLM JSON parse error"],
#                     "confidence": None,
#                 })
#             continue

#         # align by order if counts differ (still guarantee one output per input)
#         if len(parsed) != len(rows):
#             errors.append(f"Batch {start}-{start+len(chunk)-1} length mismatch: got {len(parsed)} vs {len(rows)}")
        
#         for idx in range(len(rows)):
#             r = rows[idx]
#             item = parsed[idx] if idx < len(parsed) else {}
#             outputs.append({
#                 "patient_id": item.get("patient_id") or r.get("Patient_ID"),
#                 "eligible": item.get("eligible", "Inconclusive"),
#                 "reasons": item.get("reasons") if isinstance(item.get("reasons"), list) else [],
#                 "missing": item.get("missing") if isinstance(item.get("missing"), list) else [],
#                 "confidence": item.get("confidence"),
#             })

#     out_df = pd.DataFrame(outputs)
#     for col in ["patient_id", "eligible", "reasons", "missing", "confidence"]:
#         if col not in out_df.columns:
#             out_df[col] = None
#     out_df["confidence"] = pd.to_numeric(out_df["confidence"], errors="coerce").round(settings.CONF_DECIMALS)
#     return out_df, errors

# def evaluate_in_batches(criteria_text: str, patients_df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
#     errors: List[str] = []
#     if "Patient_ID" not in patients_df.columns:
#         raise ValueError("patients_df must include 'Patient_ID' column")

#     df = _preprocess_for_llm(patients_df)

#     proj = _project_context_tokens(min(len(df), settings.BATCH_SIZE), df.shape[1])
#     if settings.ABORT_ON_CONTEXT_OVERFLOW and proj > 120_000:
#         raise RuntimeError("Projected context too large for a 100-row batch. Reduce batch size or fields.")

#     outputs: List[Dict[str, Any]] = []

#     for start in range(0, len(df), settings.BATCH_SIZE):
#         chunk = df.iloc[start : start + settings.BATCH_SIZE].copy()
#         rows = chunk.to_dict(orient="records")
#         prompt = _build_batch_prompt(criteria_text, rows)
#         print("PROMPT\n")
#         print(prompt)

#         try:
#             resp_text, safety_reasons = _gemini_call(prompt)
#         except Exception as e:
#             errors.append(f"Batch {start}-{start+len(chunk)-1} failed: {e}")
#             continue

#         if not DEBUG_CAPTURE["last_resp_head"]:
#             DEBUG_CAPTURE["last_resp_head"] = (resp_text or "")[:500]

#         if not resp_text:
#             msg = f"Batch {start}-{start+len(chunk)-1} blocked/empty from LLM"
#             if safety_reasons:
#                 msg += f" | safety: {', '.join(set(safety_reasons))}"
#             errors.append(msg)
#             for r in rows:
#                 outputs.append({
#                     "patient_id": r.get("Patient_ID"),
#                     "eligible": "Inconclusive",
#                     "reasons": [],
#                     "missing": ["LLM blocked"],
#                     "confidence": None,
#                 })
#             continue

#         resp_text = _strip_code_fences(resp_text)

#         try:
#             parsed = json.loads(resp_text)
#             if not isinstance(parsed, list):
#                 raise ValueError("LLM did not return a JSON array.")
#         except Exception as e:
#             errors.append(f"Batch {start}-{start+len(chunk)-1} JSON parse error: {e} | head: {resp_text[:200]}")
#             for r in rows:
#                 outputs.append({
#                     "patient_id": r.get("Patient_ID"),
#                     "eligible": "Inconclusive",
#                     "reasons": [],
#                     "missing": ["LLM JSON parse error"],
#                     "confidence": None,
#                 })
#             continue

#         if len(parsed) != len(rows):
#             errors.append(
#                 f"Batch {start}-{start+len(chunk)-1} length mismatch: got {len(parsed)} for {len(rows)} rows."
#             )

#         for idx in range(len(rows)):
#             r = rows[idx]
#             item = parsed[idx] if idx < len(parsed) else {}

#             outputs.append({
#                 "patient_id": item.get("patient_id") or r.get("Patient_ID"),
#                 "eligible": item.get("eligible", "Inconclusive"),
#                 "reasons": item.get("reasons") if isinstance(item.get("reasons"), list) else [],
#                 "missing": item.get("missing") if isinstance(item.get("missing"), list) else [],
#                 "confidence": item.get("confidence"),
#             })

#     out_df = pd.DataFrame(outputs)

#     for col in ["patient_id", "eligible", "reasons", "missing", "confidence"]:
#         if col not in out_df.columns:
#             out_df[col] = None

#     if "confidence" in out_df.columns:
#         out_df["confidence"] = pd.to_numeric(out_df["confidence"], errors="coerce").round(settings.CONF_DECIMALS)

#     return out_df, errors


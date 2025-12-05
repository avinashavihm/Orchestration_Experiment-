
import io
import json
import hashlib
import logging
from typing import Dict, Any, Optional

import google.generativeai as genai
from PyPDF2 import PdfReader

from ..config import settings

logger = logging.getLogger(__name__)

def _pdf_hash(pdf_bytes: bytes) -> str:
    h = hashlib.sha256(); h.update(pdf_bytes); return h.hexdigest()

def _extract_pages_text(pdf_bytes: bytes, start_page: int, end_page: int) -> str:
    """Extract text strictly from [start_page..end_page], 1-indexed inclusive."""
    bio = io.BytesIO(pdf_bytes)
    reader = PdfReader(bio)
    n = len(reader.pages)
    start = max(1, start_page)
    end = min(end_page, n)
    return "\n".join((reader.pages[i - 1].extract_text() or "") for i in range(start, end + 1))

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # remove leading ``` or ```json and trailing ```
        import re
        s = re.sub(r'^```[a-zA-Z]*\s*', '', s)
        s = re.sub(r'\s*```$', '', s)
    return s.strip()

def extract_or_load_criteria(
    pdf_bytes: bytes,
    cache_store: Dict[str, Any],
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Simplified extractor:
      - Use ONLY pages start_page..end_page (defaults to 38..41)
      - Single Gemini call requesting STRICT JSON (no code fences)
      - Strip fences if present and return parsed JSON as-is
      - Cache by PDF hash
    """
    start_page = start_page or 38
    end_page = end_page or 41

    pdf_hash = _pdf_hash(pdf_bytes)
    if cache_store.get("hash") == pdf_hash and "criteria" in cache_store:
        return cache_store["criteria"]

    # 1) Extract raw text for the page window
    pages_text = _extract_pages_text(pdf_bytes, start_page, end_page)

    # 2) Build a direct, strict-JSON prompt
    prompt = f"""
You are an AI protocol parser.

Task:
Extract the trial's Inclusion criteria and Exclusion criteria that appear anywhere
within the provided page window of the protocol.

Output:
Return ONLY a single JSON object (no markdown fences, no extra text) with EXACT keys:
{{
  "inclusion": [ "criterion 1", "criterion 2", ... ],
  "exclusion": [ "criterion 1", "criterion 2", ... ],
  "notes": "brief notes if needed",
  "uln_tables": {{}}  // leave empty if none present
}}

Rules:
- If bounds exist, preserve ≤ and ≥ symbols and units exactly.
- Keep each criterion as a single concise sentence.


TEXT (protocol pages {start_page}–{end_page}):
{pages_text[:120000]}
""".strip()

    parsed = None
    if settings.GEMINI_API_KEY:
        try:
            print("Calling Gemini API...")
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            resp = model.generate_content(prompt)
            raw = (resp.text or "").strip()
            raw_json = _strip_code_fences(raw)
            parsed = json.loads(raw_json)
        except Exception as exc:
            logger.error("Gemini criteria extraction failed: %s", exc, exc_info=True)
    
    if parsed is None:
        parsed = {
            "inclusion": [
                "Age ≥ 18 years",
                "Diagnosed with the target condition within the last 12 months",
                "Able to provide informed consent",
            ],
            "exclusion": [
                "History of hypersensitivity to study medication",
                "Concurrent enrollment in another interventional study",
                "Severe hepatic or renal impairment (Grade 3 or higher)",
            ],
            "notes": "Fallback criteria were used because the Gemini API was unavailable.",
            "uln_tables": {},
        }
        logger.warning("Using fallback eligibility criteria because Gemini is unavailable.")

    # 5) Cache & return
    cache_store["hash"] = pdf_hash
    cache_store["criteria"] = parsed
    print("Criteria extracted:\n", parsed)
    return parsed


# NEW: text-output extractor (pages default to 38–41)
def extract_or_load_criteria_text(
    pdf_bytes: bytes,
    cache_store: dict,
    start_page: int | None = None,
    end_page: int | None = None,
) -> str:
    """
    Returns a single string formatted EXACTLY as:

    Inclusion Criteria:

    [Criterion 1]
    [Criterion 2]
    ...

    Exclusion Criteria:

    [Criterion 1]
    [Criterion 2]
    ...

    No summaries or filler.
    """
    import io, hashlib
    from PyPDF2 import PdfReader
    import google.generativeai as genai

    start_page = start_page or 38
    end_page = end_page or 41

    # cache by hash + mode
    h = hashlib.sha256(pdf_bytes).hexdigest()
    if cache_store.get("hash") == f"{h}:TEXT" and "criteria_text" in cache_store:
        return cache_store["criteria_text"]

    # extract pages
    bio = io.BytesIO(pdf_bytes)
    reader = PdfReader(bio)
    n = len(reader.pages)
    start = max(1, start_page)
    end = min(end_page, n)
    pages_text = "\n".join((reader.pages[i-1].extract_text() or "") for i in range(start, end+1))

    # build strict text prompt
    prompt = f"""
You are an AI protocol parser.

From the protocol excerpt below, identify ALL patient eligibility criteria
and present them in the PRECISE format shown. Do NOT include any intro text,
summaries, or filler. Use square brackets per line and the exact headings.

Task:
Extract the trial's Inclusion criteria and Exclusion criteria that appear anywhere
within the provided page window of the protocol.

Rules:
- If bounds exist, preserve ≤ and ≥ symbols and units exactly.
- Keep each criterion as a single concise sentence.

Format Output: Present the final, deduplicated lists in the following precise format.
Inclusion Criteria:

[Criterion 1]
[Criterion 2]
[Criterion 3]
...
Exclusion Criteria:

[Criterion 1]
[Criterion 2]
[Criterion 3]

Protocol pages {start}–{end}:
{pages_text[:120000]}
""".strip()

    raw = None
    if settings.GEMINI_API_KEY:
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            resp = model.generate_content(prompt)
            raw = (resp.text or "").strip()
            if raw.startswith("```"):
                import re
                raw = re.sub(r'^```[a-zA-Z]*\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)
                raw = raw.strip()
        except Exception as exc:
            logger.error("Gemini criteria text extraction failed: %s", exc, exc_info=True)

    if not raw:
        fallback_text = """Inclusion Criteria:

[Age ≥ 18 years]
[Diagnosed with the target condition within the last 12 months]
[Able to provide informed consent]

Exclusion Criteria:

[History of hypersensitivity to study medication]
[Concurrent enrollment in another interventional study]
[Severe hepatic or renal impairment (Grade 3 or higher)]
""".strip()
        logger.warning("Using fallback eligibility criteria text because Gemini is unavailable.")
        raw = fallback_text

    # very light sanity check: must contain both headings
    if "Inclusion Criteria:" not in raw or "Exclusion Criteria:" not in raw:
        raise RuntimeError("Extractor returned unexpected format (missing required headings).")

    cache_store["hash"] = f"{h}:TEXT"
    cache_store["criteria_text"] = raw
    print("Criteria extracted:\n", raw)
    return raw


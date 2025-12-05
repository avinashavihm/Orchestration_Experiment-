import json
import google.generativeai as genai
from ..config import settings

try:
    import agentops
    _AGENTOPS = True
except Exception:
    _AGENTOPS = False

class CriteriaExtractionAgent:
#     _SYS_PROMPT = """You are a clinical trial protocol analyst.
# Extract inclusion and exclusion criteria as a STRICT JSON with this schema:

# {
#   "inclusion": [
#     {"field": "<csv_column_name>", "op": "<one of: eq, neq, gt, gte, lt, lte, in, contains, regex, between, exists, true, false>", "value": <number|string|array|{min,max}>, "comment": "<optional>"}
#   ],
#   "exclusion": [
#     {"field": "...", "op": "...", "value": ..., "comment": "..."}
#   ]
# }

# Rules:
# - Use ONLY fields present in the patient CSV header.
# - For ranges, use op "between" with {"min": x, "max": y}.
# - For booleans, use op "true"/"false".
# - Output ONLY JSON. No prose, no markdown fences.
# """

    _SYS_PROMPT = """You are an AI-powered clinical data extraction specialist. Your sole function is to read a clinical trial protocol document provided by the user and accurately extract the participant eligibility criteria.
Your Task:

Identify Sections: Meticulously scan the document to locate the "Inclusion Criteria" and "Exclusion Criteria" sections. These may have slightly different headings, such as "Eligibility Criteria," "Participant Selection," or similar.
Extract Criteria: Carefully extract every single condition listed under both inclusion and exclusion categories.
Deduplicate and Consolidate: This is the most critical step. After extraction, you must analyze the list of conditions for semantic duplicates.
A duplicate is any condition that expresses the same requirement or restriction, even if worded differently.
For example, "Must be 18 years of age or older" is a duplicate of "Participants must be aged ≥ 18 years."
Consolidate these duplicates into a single, representative statement.
Format Output: Present the final, deduplicated lists in the following precise format. Do not include any introductory text, summaries, or conversational filler.
Inclusion Criteria:

[Criterion 1]
[Criterion 2]
[Criterion 3]
...
Exclusion Criteria:

[Criterion 1]
[Criterion 2]
[Criterion 3]
"""



    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        print(f"[AGENT] Using GEMINI")

    def extract(self, raw_protocol_text: str, csv_header: str) -> dict:
        prompt = f"""{self._SYS_PROMPT}

Protocol excerpt (pp. 37–41):
\"\"\"{raw_protocol_text[:100000]}\"\"\"

Patient CSV header (tab-delimited):
{csv_header}

Return ONLY JSON, nothing else.
"""
        if _AGENTOPS and settings.AGENTOPS_API_KEY:
            try:
                agentops.init(api_key=settings.AGENTOPS_API_KEY)
            except Exception:
                pass

        resp = self.model.generate_content(prompt)
        text = resp.text.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.strip("`")
            # remove optional "json" header
            if text.lower().startswith("json"):
                text = text[4:].strip()

        # Keep only the outermost JSON object
        first = text.find("{")
        last = text.rfind("}")
        if first == -1 or last == -1:
            raise ValueError(f"Gemini did not return JSON. Got: {text[:200]}...")
        json_text = text[first:last+1]
        return json.loads(json_text)

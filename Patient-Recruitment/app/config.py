import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Environment / Paths ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    AGENTOPS_API_KEY: str = os.getenv("AGENTOPS_API_KEY", "")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./data/uploads")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./data/outputs")
        # NEW: generation controls
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    LLM_MAX_OUTPUT_TOKENS: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "8192"))
        # NEW (optional): enforce raw JSON responses from Gemini
    LLM_RESPONSE_MIME_TYPE: str = os.getenv("LLM_RESPONSE_MIME_TYPE", "application/json")

    # NEW (optional): a global system instruction to reduce safety triggers
    LLM_SYSTEM_INSTRUCTION: str = os.getenv("LLM_SYSTEM_INSTRUCTION",
        "This task is strictly non-diagnostic, non-therapeutic, and uses de-identified data. "
        "You are performing rules-based eligibility screening for research operations only. "
        "Do NOT provide medical advice, guidance, or risk assessments. "
        "Return only the requested JSON.")


    # --- Version 3 constants ---
    # Eligibility batching (reduced to prevent response truncation)
    BATCH_SIZE: int = 10
    LLM_TIMEOUT_SECS: int = 120
    LLM_MAX_RETRIES: int = 3
    ABORT_ON_CONTEXT_OVERFLOW: bool = True

    # Confidence rounding precision
    CONF_DECIMALS: int = 3

    # Default Site Performance Factor when site not in history
    DEFAULT_SITE_PERF_FACTOR: float = 0.50

    # Status multiplier map (per simplified Option A formula)
    STATUS_MULTIPLIER: dict[str, float] = {
        "ongoing": 1.0,
        "completed": 0.8,
        "closed": 0.0,
        "terminated": 0.0,
    }


settings = Settings()



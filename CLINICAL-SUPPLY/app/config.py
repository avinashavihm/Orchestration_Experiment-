import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""
    
    # Gemini API Configuration
    # Support multiple API keys for load balancing and rate limit avoidance
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_API_KEY_1: str = os.getenv("GEMINI_API_KEY_1", "")
    GEMINI_API_KEY_2: str = os.getenv("GEMINI_API_KEY_2", "")
    GEMINI_API_KEY_3: str = os.getenv("GEMINI_API_KEY_3", "")
    
    @classmethod
    def get_gemini_api_keys(cls) -> List[str]:
        """Get all available Gemini API keys."""
        keys = []
        # Add primary key if set
        if cls.GEMINI_API_KEY:
            keys.append(cls.GEMINI_API_KEY)
        # Add numbered keys if set
        if cls.GEMINI_API_KEY_1:
            keys.append(cls.GEMINI_API_KEY_1)
        if cls.GEMINI_API_KEY_2:
            keys.append(cls.GEMINI_API_KEY_2)
        if cls.GEMINI_API_KEY_3:
            keys.append(cls.GEMINI_API_KEY_3)
        return keys
    
    # Use latest available models (as of 2025)
    # Default: gemini-2.0-flash (Latest and fastest model)
    # Alternatives: gemini-1.5-flash-latest, gemini-1.5-pro-latest, gemini-pro
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_BASE_URL: str = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta"
    )
    
    # AgentOps Configuration
    AGENTOPS_API_KEY: str = os.getenv("AGENTOPS_API_KEY", "")
    AGENT_SERVICE_NAME: str = os.getenv("AGENT_SERVICE_NAME", "clin-supply-copilot")
    
    # Data Configuration
    # Default to data directory in project root if not specified
    # Calculate project root from this file's location
    try:
        _config_file = Path(__file__).resolve()
        _project_root = _config_file.parent.parent  # app/config.py -> project root
        _default_data_dir = _project_root / "data"
    except (NameError, AttributeError):
        # Fallback if __file__ not available
        _default_data_dir = Path.cwd() / "data"
    
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(_default_data_dir)))
    UPLOAD_BASE_DIR: Path = Path(os.getenv("UPLOAD_BASE_DIR", "/tmp/uploads"))
    
    # Environment
    ENV: str = os.getenv("ENV", "development")
    
    # Required CSV Files
    REQUIRED_CSV_FILES: dict[str, str] = {
        "sites": "sites.csv",
        "enrollment": "enrollment.csv",
        "dispense": "dispense.csv",
        "inventory": "inventory.csv",
        "shipment": "shipment_logs.csv",
        "waste": "waste.csv",
    }
    
    # Minimum order quantity
    MIN_ORDER_QUANTITY: int = 10
    
    # Safety stock multiplier
    SAFETY_STOCK_MULTIPLIER: float = 1.2
    
    # Expiry threshold (days)
    EXPIRY_THRESHOLD_DAYS: int = 30
    
    # Hybrid Optimization Configuration
    # Streaming CSV reading
    CSV_CHUNK_SIZE: int = int(os.getenv("CSV_CHUNK_SIZE", "10000"))  # Rows per chunk
    USE_STREAMING: bool = os.getenv("USE_STREAMING", "true").lower() == "true"
    
    # Batch API calls
    BATCH_API_SIZE: int = int(os.getenv("BATCH_API_SIZE", "5"))  # Sites per API call
    USE_BATCH_API: bool = os.getenv("USE_BATCH_API", "true").lower() == "true"
    
    # Parallel processing
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))
    USE_PARALLEL: bool = os.getenv("USE_PARALLEL", "true").lower() == "true"
    
    # Selective LLM usage
    LLM_PRIORITY_THRESHOLD: float = float(os.getenv("LLM_PRIORITY_THRESHOLD", "1.5"))  # Urgency score threshold
    LLM_EXPIRY_THRESHOLD: int = int(os.getenv("LLM_EXPIRY_THRESHOLD", "60"))  # Days to expiry threshold
    USE_SELECTIVE_LLM: bool = os.getenv("USE_SELECTIVE_LLM", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        # Check if at least one Gemini API key is configured
        api_keys = cls.get_gemini_api_keys()
        if not api_keys:
            raise ValueError("At least one GEMINI_API_KEY is required. Set GEMINI_API_KEY or GEMINI_API_KEY_1, GEMINI_API_KEY_2, GEMINI_API_KEY_3")
        if not cls.AGENTOPS_API_KEY:
            raise ValueError("AGENTOPS_API_KEY is required")
    
    @classmethod
    def get_upload_dir(cls, session_id: str) -> Path:
        """Get upload directory for a session."""
        upload_dir = cls.UPLOAD_BASE_DIR / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir


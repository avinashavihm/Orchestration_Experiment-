from pathlib import Path
from typing import Dict, Optional
import pandas as pd
from app.config import Config
from app.upload_handler import load_uploaded_csvs, UploadValidationError


def load_data(upload_dir: Optional[Path] = None) -> Dict[str, pd.DataFrame]:
    """
    Load CSV data from either upload directory or default data directory.
    
    Args:
        upload_dir: Optional directory containing uploaded CSV files.
                   If None, loads from default DATA_DIR.
        
    Returns:
        Dictionary mapping CSV key to DataFrame:
        {
            "sites": df,
            "enrollment": df,
            "dispense": df,
            "inventory": df,
            "shipment": df,
            "waste": df
        }
        
    Raises:
        UploadValidationError: If files are missing or invalid
        FileNotFoundError: If default data directory doesn't exist
    """
    if upload_dir is not None:
        # Load from upload directory
        return load_uploaded_csvs(upload_dir)
    else:
        # Load from default data directory
        data_dir = Config.DATA_DIR
        if not data_dir.exists():
            raise FileNotFoundError(
                f"Default data directory not found: {data_dir}. "
                f"Please create the directory and add your CSV files, or set DATA_DIR in your .env file."
            )
        return load_uploaded_csvs(data_dir)


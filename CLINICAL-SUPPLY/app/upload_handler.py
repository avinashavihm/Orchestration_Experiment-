import csv
import shutil
import inspect
import io
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from fastapi import UploadFile
from app.config import Config

# Try to import chardet for encoding detection
try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False


class UploadValidationError(Exception):
    """Raised when uploaded files fail validation."""
    pass


def detect_file_encoding(file_path: Path) -> Tuple[str, float]:
    """
    Detect file encoding using chardet.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Tuple of (encoding, confidence) where confidence is 0.0-1.0
    """
    if not CHARDET_AVAILABLE:
        return None, 0.0
    
    try:
        # Read a sample of the file for detection (first 10KB should be enough)
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
        
        if not raw_data:
            return None, 0.0
        
        result = chardet.detect(raw_data)
        encoding = result.get('encoding')
        confidence = result.get('confidence', 0.0)
        
        # Normalize encoding names
        if encoding:
            encoding = encoding.lower()
            # Map common variations
            encoding_map = {
                'utf-8': 'utf-8',
                'utf8': 'utf-8',
                'utf-16': 'utf-16',
                'utf-16le': 'utf-16-le',
                'utf-16be': 'utf-16-be',
                'utf-16-le': 'utf-16-le',
                'utf-16-be': 'utf-16-be',
                'windows-1252': 'cp1252',
                'iso-8859-1': 'iso-8859-1',
                'latin1': 'latin-1',
                'latin-1': 'latin-1',
            }
            encoding = encoding_map.get(encoding, encoding)
        
        return encoding, confidence
    except Exception:
        return None, 0.0


def detect_utf16_bom(file_path: Path) -> Optional[str]:
    """
    Detect UTF-16 BOM and return appropriate encoding.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Encoding string ('utf-16-le', 'utf-16-be', or None)
    """
    try:
        with open(file_path, 'rb') as f:
            bom = f.read(2)
        
        # UTF-16 LE BOM: FF FE
        if bom == b'\xff\xfe':
            return 'utf-16-le'
        # UTF-16 BE BOM: FE FF
        elif bom == b'\xfe\xff':
            return 'utf-16-be'
        else:
            return None
    except Exception:
        return None


def read_csv_with_encoding_cleanup(file_path: Path, encoding: str) -> Optional[pd.DataFrame]:
    """
    Read CSV file with encoding cleanup for problematic characters.
    
    Args:
        file_path: Path to the file
        encoding: Encoding to use
        
    Returns:
        DataFrame or None if reading fails
    """
    try:
        # Try reading with error handling
        df = pd.read_csv(
            file_path,
            encoding=encoding,
            encoding_errors='replace',  # Replace invalid characters
            engine='c',
            sep=',',
            quotechar='"',
            skipinitialspace=True,
            skip_blank_lines=True
        )
        return df if df is not None and not df.empty else None
    except Exception:
        return None


def validate_saved_file(file_path: Path) -> Tuple[bool, str]:
    """
    Validate that a saved file is readable and has valid content.
    
    Args:
        file_path: Path to the saved file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Check file exists
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"
        
        # Check file is not empty
        file_size = file_path.stat().st_size
        if file_size == 0:
            return False, f"File is empty: {file_path}"
        
        # Try to read first few bytes to ensure it's readable
        try:
            with open(file_path, 'rb') as f:
                first_bytes = f.read(min(1000, file_size))
            
            if not first_bytes:
                return False, f"File has no readable content: {file_path}"
            
            # Try to decode first line to check if it's valid text
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'utf-16-le', 'utf-16-be']:
                try:
                    sample = first_bytes.decode(encoding, errors='strict')
                    # Check if it looks like CSV
                    if '\n' in sample or ',' in sample or '\t' in sample:
                        logger.info(f"File {file_path.name} validated after save ({file_size} bytes, encoding: {encoding})")
                        return True, ""
                except UnicodeDecodeError:
                    continue
            
            # If we can't decode with common encodings, log warning but allow
            logger.warning(f"File {file_path.name} saved but encoding unclear ({file_size} bytes)")
            return True, ""  # Allow, upload handler will handle encoding
            
        except Exception as e:
            return False, f"Error reading file {file_path}: {e}"
        
    except Exception as e:
        logger.error(f"Error validating saved file {file_path}: {e}")
        return False, f"Validation error: {e}"


async def save_uploaded_files(
    uploaded_files: Dict[str, Any],
    upload_dir: Path
) -> Dict[str, Path]:
    """
    Save uploaded files to disk.
    
    Args:
        uploaded_files: Dictionary mapping filename to file object
        upload_dir: Directory to save files to
        
    Returns:
        Dictionary mapping CSV key to saved file path
    """
    import logging
    logger = logging.getLogger(__name__)
    
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = {}
    
    for key, filename in Config.REQUIRED_CSV_FILES.items():
        if filename in uploaded_files:
            file_obj = uploaded_files[filename]
            file_path = upload_dir / filename
            
            # Save file
            # Check if read() is a coroutine (async method)
            is_async_read = (
                hasattr(file_obj, 'read') and 
                inspect.iscoroutinefunction(getattr(file_obj, 'read', None))
            )
            
            if is_async_read or isinstance(file_obj, UploadFile):
                # FastAPI UploadFile object - async read
                content = await file_obj.read()
                
                # DEBUG: Log file info
                logger.info(f"Saving {filename}: {len(content)} bytes")
                if len(content) > 0:
                    # Check first 100 bytes
                    first_bytes = content[:min(100, len(content))]
                    logger.info(f"First 100 bytes (hex): {first_bytes.hex()[:200]}")
                    # Try to decode and show first line
                    for enc in ['utf-8', 'latin-1', 'utf-16-le']:
                        try:
                            sample = first_bytes.decode(enc, errors='strict')
                            logger.info(f"Decoded with {enc}: {sample[:50]}")
                            break
                        except:
                            continue
                
                # Try to detect and fix encoding issues before saving
                try:
                    # Try to detect if file is UTF-16 or other problematic encoding
                    is_utf16 = content.startswith(b'\xff\xfe') or content.startswith(b'\xfe\xff')
                    
                    if is_utf16 or len(content) > 50000:  # Suspiciously large for CSV
                        logger.warning(f"{filename} appears to be UTF-16 or oversized ({len(content)} bytes), attempting to fix...")
                        
                        # Try to decode and re-encode as UTF-8
                        decoded = None
                        for enc in ['utf-16-le', 'utf-16-be', 'utf-16', 'utf-8', 'latin-1']:
                            try:
                                decoded = content.decode(enc, errors='replace')
                                logger.info(f"Successfully decoded {filename} with {enc}")
                                break
                            except:
                                continue
                        
                        if decoded:
                            # Re-encode as UTF-8
                            content = decoded.encode('utf-8', errors='replace')
                            logger.info(f"Re-encoded {filename} to UTF-8, new size: {len(content)} bytes")
                except Exception as e:
                    logger.warning(f"Could not fix encoding for {filename}: {e}, saving as-is")
                
                with open(file_path, 'wb') as f:
                    f.write(content)
                # Reset file pointer if needed (check if seek is async)
                if hasattr(file_obj, 'seek'):
                    try:
                        # Try to check if seek is async
                        if inspect.iscoroutinefunction(getattr(file_obj, 'seek', None)):
                            await file_obj.seek(0)
                        else:
                            file_obj.seek(0)
                    except (AttributeError, TypeError):
                        # If seek doesn't exist or fails, just skip it
                        pass
            elif isinstance(file_obj, (str, Path)):
                # Path string or Path object
                shutil.copy(str(file_obj), str(file_path))
            else:
                # Generic file-like object (sync read)
                try:
                    if hasattr(file_obj, 'read'):
                        content = file_obj.read()
                        if isinstance(content, bytes):
                            with open(file_path, 'wb') as f:
                                f.write(content)
                        else:
                            with open(file_path, 'w') as f:
                                f.write(content)
                        if hasattr(file_obj, 'seek'):
                            file_obj.seek(0)
                    else:
                        # Fallback: try to copy if it's a path
                        shutil.copy(str(file_obj), str(file_path))
                except Exception as e:
                    # Fallback: try to copy if it's a path
                    shutil.copy(str(file_obj), str(file_path))
            
            # Validate file after save
            is_valid, error_msg = validate_saved_file(file_path)
            if not is_valid:
                raise UploadValidationError(f"File integrity check failed for {filename}: {error_msg}")
            
            saved_paths[key] = file_path
    
    return saved_paths


def load_uploaded_csvs(upload_dir: Path) -> Dict[str, pd.DataFrame]:
    """
    Load all required CSV files from upload directory.
    
    Args:
        upload_dir: Directory containing CSV files
        
    Returns:
        Dictionary mapping CSV key to DataFrame
        
    Raises:
        UploadValidationError: If files are missing or invalid
    """
    dataframes = {}
    missing_files = []
    
    # Check all required files exist
    for key, filename in Config.REQUIRED_CSV_FILES.items():
        file_path = upload_dir / filename
        if not file_path.exists():
            missing_files.append(filename)
        else:
            try:
                import logging
                logger = logging.getLogger(__name__)
                
                df = None
                last_error = None
                encoding_attempts = []
                
                # Step 1: Try automatic encoding detection with chardet
                detected_encoding = None
                detected_confidence = 0.0
                if CHARDET_AVAILABLE:
                    detected_encoding, detected_confidence = detect_file_encoding(file_path)
                    if detected_encoding:
                        logger.info(f"Chardet detected encoding for {filename}: {detected_encoding} (confidence: {detected_confidence:.2f})")
                        if detected_confidence > 0.7:
                            encoding_attempts.append(('detected', detected_encoding))
                
                # Step 2: Check for UTF-16 BOM
                utf16_bom_encoding = detect_utf16_bom(file_path)
                if utf16_bom_encoding:
                    logger.info(f"Detected UTF-16 BOM for {filename}: {utf16_bom_encoding}")
                    if ('bom', utf16_bom_encoding) not in encoding_attempts:
                        encoding_attempts.insert(0, ('bom', utf16_bom_encoding))
                
                # Step 3: Build comprehensive encoding list
                # Priority: UTF-8 first (most common), then detected > common encodings > UTF-16 variants (only if BOM detected or others fail)
                encodings_to_try = []
                
                # If chardet detected ASCII with high confidence, treat as UTF-8
                if detected_encoding and detected_encoding.lower() in ['ascii', 'utf-8'] and detected_confidence > 0.9:
                    logger.info(f"High confidence ASCII/UTF-8 detected for {filename}, using utf-8")
                    encodings_to_try = ['utf-8']  # Only try UTF-8 for high-confidence ASCII
                else:
                    # ALWAYS try UTF-8 first for standard CSV files (unless UTF-16 BOM detected)
                    if not utf16_bom_encoding:
                        encodings_to_try.append('utf-8')
                    
                    # Add UTF-16 BOM encoding right after UTF-8 if detected
                    if utf16_bom_encoding and utf16_bom_encoding not in encodings_to_try:
                        encodings_to_try.append(utf16_bom_encoding)
                    
                    # Add detected encoding if available and different from already added
                    if detected_encoding and detected_encoding not in encodings_to_try:
                        encodings_to_try.append(detected_encoding)
                    
                    # Add other common encodings
                    common_encodings = ['latin-1', 'iso-8859-1', 'cp1252', 'windows-1252']
                    for enc in common_encodings:
                        if enc not in encodings_to_try:
                            encodings_to_try.append(enc)
                    
                    # Add UTF-16 variants LAST (only try if file has BOM or common encodings fail)
                    # These should only be tried if there's evidence the file is actually UTF-16
                    utf16_variants = ['utf-16-le', 'utf-16-be', 'utf-16']
                    for variant in utf16_variants:
                        if variant not in encodings_to_try:
                            encodings_to_try.append(variant)
                    
                    # Remove duplicates while preserving order
                    seen = set()
                    encodings_to_try = [e for e in encodings_to_try if not (e in seen or seen.add(e))]
                
                logger.info(f"File size: {file_path.stat().st_size} bytes")
                logger.info(f"Encoding strategy for {filename}: {encodings_to_try[:5]}... (total: {len(encodings_to_try)})")
                
                for encoding in encodings_to_try:
                    try:
                        # For UTF-16 variants, handle BOM and encoding errors specially
                        encoding_kwargs = {'encoding': encoding}
                        
                        # Add encoding_errors for problematic files
                        if encoding.startswith('utf-16'):
                            # UTF-16 files may have BOM or encoding issues
                            encoding_kwargs['encoding_errors'] = 'replace'  # Replace invalid surrogates
                        else:
                            # For other encodings, try strict first, then replace
                            encoding_kwargs['encoding_errors'] = 'strict'
                        
                        # Try with C engine first (faster and more reliable)
                        try:
                            df = pd.read_csv(
                                file_path,
                                engine='c',
                                sep=',',
                                quotechar='"',
                                skipinitialspace=True,
                                skip_blank_lines=True,
                                **encoding_kwargs
                            )
                            if df is not None and not df.empty:
                                # CRITICAL: Validate that column names are not garbled
                                # Check if columns are readable (not encoding artifacts)
                                columns_valid = True
                                for col in df.columns:
                                    if isinstance(col, str):
                                        # Check if column name is garbled
                                        if detect_garbled_text(col):
                                            columns_valid = False
                                            logger.warning(f"Column name appears garbled with encoding {encoding}: {col}")
                                            break
                                
                                if columns_valid:
                                    logger.info(f"Successfully read {filename} with encoding: {encoding} - columns: {list(df.columns)[:3]}")
                                    break
                                else:
                                    logger.warning(f"Encoding {encoding} produced garbled columns, trying next encoding")
                                    df = None  # Reset and try next encoding
                                    continue
                        except (pd.errors.ParserError, UnicodeDecodeError) as e:
                            # If C engine fails, try with encoding error handling
                            if isinstance(e, UnicodeDecodeError):
                                # Try with replace/ignore for encoding errors
                                try:
                                    encoding_kwargs['encoding_errors'] = 'replace'
                                    df = pd.read_csv(
                                        file_path,
                                        engine='c',
                                        sep=',',
                                        quotechar='"',
                                        skipinitialspace=True,
                                        skip_blank_lines=True,
                                        **encoding_kwargs
                                    )
                                    if df is not None and not df.empty:
                                        # Validate column names are not garbled
                                        columns_valid = all(
                                            not detect_garbled_text(str(col)) for col in df.columns if isinstance(col, str)
                                        )
                                        if columns_valid:
                                            logger.info(f"Successfully read {filename} with encoding: {encoding} (using error replacement)")
                                            break
                                        else:
                                            df = None
                                            continue
                                except Exception:
                                    pass
                            
                            # If C engine fails due to bad lines, try with on_bad_lines='skip'
                            try:
                                try:
                                    encoding_kwargs['encoding_errors'] = 'replace'  # Use replace for problematic files
                                    df = pd.read_csv(
                                        file_path,
                                        engine='c',
                                        sep=',',
                                        quotechar='"',
                                        skipinitialspace=True,
                                        skip_blank_lines=True,
                                        on_bad_lines='skip',  # Pandas >= 2.0
                                        **encoding_kwargs
                                    )
                                except (TypeError, AttributeError):
                                    # Older pandas - try Python engine instead
                                    df = None
                                if df is not None and not df.empty:
                                    # Validate column names
                                    columns_valid = all(
                                        not detect_garbled_text(str(col)) for col in df.columns if isinstance(col, str)
                                    )
                                    if columns_valid:
                                        logger.info(f"Successfully read {filename} with encoding: {encoding} (skipping bad lines)")
                                        break
                                    else:
                                        df = None
                                        continue
                            except Exception:
                                pass  # Try Python engine next
                        except Exception as e1:
                            # C engine failed, try Python engine as fallback
                            # If that fails, try with auto-detection
                            try:
                                encoding_kwargs['encoding_errors'] = 'replace'
                                try:
                                    df = pd.read_csv(
                                        file_path,
                                        on_bad_lines='skip',
                                        engine='python',
                                        sep=None,  # Auto-detect separator
                                        quotechar='"',
                                        skipinitialspace=True,
                                        **encoding_kwargs
                                    )
                                except TypeError:
                                    df = pd.read_csv(
                                        file_path,
                                        error_bad_lines=False,
                                        warn_bad_lines=False,
                                        engine='python',
                                        sep=None,
                                        quotechar='"',
                                        skipinitialspace=True,
                                        **encoding_kwargs
                                    )
                                if df is not None and not df.empty:
                                    # Validate column names
                                    columns_valid = all(
                                        not detect_garbled_text(str(col)) for col in df.columns if isinstance(col, str)
                                    )
                                    if columns_valid:
                                        logger.info(f"Successfully read {filename} with encoding: {encoding} (Python engine, auto-sep)")
                                        break
                                    else:
                                        df = None
                                        continue
                            except Exception as e2:
                                # If auto-detect fails, try tab-separated
                                try:
                                    try:
                                        df = pd.read_csv(
                                            file_path,
                                            on_bad_lines='skip',
                                            engine='python',
                                            sep='\t',
                                            quotechar='"',
                                            skipinitialspace=True,
                                            **encoding_kwargs
                                        )
                                    except TypeError:
                                        df = pd.read_csv(
                                            file_path,
                                            error_bad_lines=False,
                                            warn_bad_lines=False,
                                            engine='python',
                                            sep='\t',
                                            quotechar='"',
                                            skipinitialspace=True,
                                            **encoding_kwargs
                                        )
                                    if df is not None and not df.empty:
                                        # Validate column names
                                        columns_valid = all(
                                            not detect_garbled_text(str(col)) for col in df.columns if isinstance(col, str)
                                        )
                                        if columns_valid:
                                            logger.info(f"Successfully read {filename} with encoding: {encoding} (Python engine, tab-sep)")
                                            break
                                        else:
                                            df = None
                                            continue
                                except UnicodeDecodeError:
                                    # Encoding error - try next encoding
                                    last_error = e2
                                    continue
                                except Exception:
                                    # Other parsing error - try next encoding
                                    last_error = e2
                                    continue
                    except UnicodeDecodeError as e:
                        last_error = e
                        encoding_attempts.append((encoding, str(e)))
                        continue
                    except Exception as e:
                        last_error = e
                        encoding_attempts.append((encoding, str(e)))
                        continue
                
                # If all encodings failed, try binary read + cleanup fallback
                if df is None or df.empty:
                    logger.warning(f"All encoding attempts failed for {filename}, trying binary cleanup fallback...")
                    try:
                        # Read file as binary and clean it
                        with open(file_path, 'rb') as f:
                            raw_data = f.read()
                        
                        # Try to decode with error handling
                        for fallback_encoding in ['utf-8', 'latin-1', 'cp1252']:
                            try:
                                # Decode with error replacement
                                cleaned_data = raw_data.decode(fallback_encoding, errors='replace')
                                # Write to temporary string and read with pandas
                                df = pd.read_csv(
                                    io.StringIO(cleaned_data),
                                    engine='python',
                                    sep=',',
                                    quotechar='"',
                                    skipinitialspace=True,
                                    on_bad_lines='skip'
                                )
                                if df is not None and not df.empty:
                                    # Validate column names
                                    columns_valid = all(
                                        not detect_garbled_text(str(col)) for col in df.columns if isinstance(col, str)
                                    )
                                    if columns_valid:
                                        logger.info(f"Successfully read {filename} using binary cleanup with {fallback_encoding}")
                                        break
                                    else:
                                        df = None
                                        continue
                            except Exception:
                                continue
                    except Exception as binary_error:
                        logger.error(f"Binary cleanup also failed: {binary_error}")
                
                if df is None or df.empty:
                    # Build detailed error message
                    error_details = []
                    if encoding_attempts:
                        error_details.append(f"Attempted {len(encoding_attempts)} encodings")
                        error_details.append(f"Last encoding tried: {encoding_attempts[-1][0] if encoding_attempts else 'unknown'}")
                    if last_error:
                        error_msg = str(last_error)
                        if 'utf-16' in error_msg.lower() or 'surrogate' in error_msg.lower():
                            error_details.append("UTF-16 encoding issue detected. The file may be corrupted or in an unexpected format.")
                            error_details.append("Suggestion: Try re-saving the file as UTF-8 CSV format.")
                        error_details.append(f"Last error: {error_msg}")
                    
                    raise UploadValidationError(
                        f"Error reading {filename}: Could not parse CSV file. {' '.join(error_details) if error_details else 'Unknown error'}"
                    )
                
                # Normalize column names: strip whitespace from column names
                df.columns = df.columns.str.strip()
                
                # Log columns for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Successfully loaded {filename} with columns: {list(df.columns)}")
                logger.info(f"DataFrame shape: {df.shape}, first row: {df.head(1).to_dict() if not df.empty else 'EMPTY'}")
                
                # Validate DataFrame has data and columns
                if df.empty:
                    raise UploadValidationError(
                        f"Error reading {filename}: CSV file is empty or contains no data rows"
                    )
                
                if len(df.columns) == 0:
                    raise UploadValidationError(
                        f"Error reading {filename}: CSV file has no columns (header row may have been skipped)"
                    )
                
                dataframes[key] = df
            except UploadValidationError:
                raise
            except Exception as e:
                raise UploadValidationError(
                    f"Error reading {filename}: {str(e)}"
                )
    
    if missing_files:
        raise UploadValidationError(
            f"Missing required files: {', '.join(missing_files)}"
        )
    
    # Validate required columns (basic check)
    validate_csv_columns(dataframes)
    
    return dataframes


def detect_garbled_text(text: str) -> bool:
    """
    Detect if text appears to be garbled due to encoding issues.
    Only detects OBVIOUS encoding problems to avoid false positives.
    
    Args:
        text: String to check
        
    Returns:
        True if text appears garbled, False otherwise
    """
    if not text or len(text) == 0:
        return False
    
    # Only check for OBVIOUS encoding issue patterns
    # Unicode replacement character (appears when decoding fails)
    if '\ufffd' in text:
        return True
    
    # Null bytes in text (shouldn't be in CSV headers)
    if '\x00' in text:
        return True
    
    # Check for excessive control characters (not newline/tab/carriage return)
    control_chars = [c for c in text if ord(c) < 32 and c not in ['\n', '\r', '\t', ' ']]
    if len(control_chars) > 3:  # Allow a few, but not many
        return True
    
    # Check if column name looks like gibberish (random high-byte characters with no ASCII)
    # Only flag if the ENTIRE text is weird, not just parts of it
    if len(text) > 0:
        ascii_count = sum(1 for c in text if 32 <= ord(c) <= 126)  # Printable ASCII
        ascii_ratio = ascii_count / len(text)
        # If less than 20% is normal ASCII, it's probably garbled
        # (allows for unicode in names but catches pure gibberish)
        if ascii_ratio < 0.2 and len(text) > 3:
            return True
    
    return False


def validate_csv_columns(dataframes: Dict[str, pd.DataFrame]) -> None:
    """
    Validate that required columns exist in CSV files and detect encoding issues.
    
    Args:
        dataframes: Dictionary of loaded DataFrames
        
    Raises:
        UploadValidationError: If required columns are missing or encoding issues detected
    """
    # Required columns for each CSV type (flexible to match actual data)
    required_columns = {
        "sites": ["site_id", "region"],  # site_name is optional
        "enrollment": ["site_id"],  # Flexible - accept any enrollment columns
        "dispense": ["site_id"],  # Flexible - accept weekly_dispense_kits or calculate
        "inventory": ["site_id", "current_inventory"],  # expiry_date can be batch_expiry_date
        "shipment": ["site_id"],  # Flexible - accept any shipment columns
        "waste": ["site_id"],  # Flexible - accept any waste columns
    }
    
    import logging
    logger = logging.getLogger(__name__)
    
    for key, df in dataframes.items():
        if key in required_columns:
            filename = Config.REQUIRED_CSV_FILES[key]
            actual_cols = list(df.columns)
            
            # Check for garbled column names (encoding issues)
            garbled_cols = [col for col in actual_cols if isinstance(col, str) and detect_garbled_text(col)]
            if garbled_cols:
                logger.error(f"Detected garbled column names in {filename}: {garbled_cols[:3]}")
                raise UploadValidationError(
                    f"File {filename} has encoding issues. Column names appear garbled: {', '.join(str(c)[:20] for c in garbled_cols[:3])}. "
                    f"This typically indicates the file was saved with incorrect encoding. "
                    f"Please re-save the file as UTF-8 CSV and try again."
                )
            
            # Log what we're checking
            logger.info(f"Validating {filename}: required={required_columns[key]}, found={actual_cols}")
            
            # Check for required columns (exact match first, then normalized)
            missing_cols = []
            
            for req_col in required_columns[key]:
                # Try exact match first (case-sensitive)
                if req_col not in actual_cols:
                    # Try case-insensitive match
                    found = False
                    for actual_col in actual_cols:
                        if isinstance(actual_col, str) and actual_col.strip().lower() == req_col.strip().lower():
                            found = True
                            break
                    if not found:
                        missing_cols.append(req_col)
            
            if missing_cols:
                # Enhanced error message with encoding suggestion
                error_msg = (
                    f"Missing required columns in {filename}: "
                    f"{', '.join(missing_cols)}. Found columns: {', '.join(str(c) for c in actual_cols) if actual_cols else 'NONE'}. "
                )
                
                # If no columns found or very strange column names, suggest encoding issue
                if not actual_cols or any(not isinstance(c, str) or len(str(c).strip()) == 0 for c in actual_cols):
                    error_msg += "This may indicate a file encoding or format issue. Please verify the file is a valid UTF-8 CSV."
                
                raise UploadValidationError(error_msg)


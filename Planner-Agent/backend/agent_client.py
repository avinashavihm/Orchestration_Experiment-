import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from websockets.client import connect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentClient:
    def __init__(self):
        self.recruitment_http_url = os.getenv("RECRUITMENT_AGENT_HTTP_URL", "http://patient-recruitment-backend:8000")
        self.supply_http_url = os.getenv("SUPPLY_AGENT_HTTP_URL", "http://clin-supply-backend:8000")
        
    async def forward_to_recruitment(self, file_map: Dict[str, tuple]) -> Dict[str, Any]:
        """
        Forward multiple files to recruitment agent.
        file_map: Dict mapping file_type (protocol_pdf, patients_xlsx, etc.) to (filename, content) tuple
        """
        import requests
        url = f"{self.recruitment_http_url}/run"
        
        files = {}
        for file_type, (filename, content) in file_map.items():
            # Map file_type to field name expected by recruitment agent
            field_name = file_type  # Already in correct format
            
            # Determine content type
            if filename.endswith('.pdf'):
                content_type = 'application/pdf'
            elif filename.endswith(('.xlsx', '.xls')):
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                content_type = 'application/octet-stream'
            
            files[field_name] = (filename, content, content_type)
        
        try:
            logger.info(f"Forwarding {len(files)} files to recruitment agent at {url}")
            logger.info(f"File types: {list(files.keys())}")
            
            # Use requests.post with files parameter
            # Note: FastAPI expects multipart/form-data with specific field names
            # Recruitment agent can take a long time (LLM processing), so increase timeout
            response = requests.post(url, files=files, timeout=900)  # 15 min timeout for LLM processing
            response.raise_for_status()
            
            # Check content type - recruitment agent returns Excel file by default
            content_type = response.headers.get('content-type', '')
            
            if 'application/json' in content_type:
                # JSON response (if return_json=true)
                return response.json()
            elif 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in content_type or 'application/octet-stream' in content_type:
                # Excel file response - extract metadata from headers
                metadata_header = response.headers.get('X-Metadata', '{}')
                try:
                    import json
                    metadata = json.loads(metadata_header) if metadata_header else {}
                    return {
                        "status": "success",
                        "file_response": True,
                        "metadata": metadata,
                        "message": "Recruitment analysis completed. Excel file returned.",
                        "filename": response.headers.get('Content-Disposition', '').split('filename=')[-1].strip('"') if 'Content-Disposition' in response.headers else "results.xlsx"
                    }
                except:
                    return {
                        "status": "success",
                        "file_response": True,
                        "message": "Recruitment analysis completed. Excel file returned."
                    }
            else:
                # Fallback: return text response
                return {"response": response.text[:1000], "status_code": response.status_code}
        except requests.exceptions.Timeout:
            logger.error(f"Recruitment agent request timed out after 15 minutes")
            return {"error": "Recruitment agent request timed out. The analysis is taking longer than expected. Please try again or check the agent logs."}
        except Exception as e:
            logger.error(f"Failed to forward to recruitment: {e}", exc_info=True)
            return {"error": str(e)}

    def _prepare_csv_content(self, content: bytes, filename: str) -> tuple[bytes | None, str | None]:
        """
        Validate and normalize CSV content before forwarding.
        - Reject empty files
        - Transparently convert Excel (XLSX) files into CSV
        - Reject obviously invalid formats (PDF, etc.)
        """
        if not content or len(content) == 0:
            error_msg = f"File {filename} has no content"
            logger.error(error_msg)
            return None, error_msg
        
        # Detect Excel (XLSX) files that were mislabeled as CSV and convert them automatically
        if content[:2] == b'PK':
            logger.warning(f"File {filename} appears to be an Excel workbook. Attempting conversion to CSV...")
            try:
                import pandas as pd
                import io
                
                excel_buffer = io.BytesIO(content)
                df = pd.read_excel(excel_buffer)
                
                if df is None or df.empty:
                    raise ValueError("Excel file contained no data")
                
                csv_text = df.to_csv(index=False)
                converted = csv_text.encode("utf-8")
                logger.info(f"Successfully converted Excel file {filename} to CSV ({len(converted)} bytes)")
                return converted, None
            except Exception as exc:
                error_msg = f"File {filename} looks like Excel but could not be converted to CSV: {exc}"
                logger.error(error_msg, exc_info=True)
                return None, error_msg
        
        # PDF or other binary formats are invalid
        if content[:4] == b'%PDF':
            error_msg = f"File {filename} appears to be a PDF document, not CSV"
            logger.error(error_msg)
            return None, error_msg
        
        # Perform a lightweight sanity check on textual data
        try:
            sample = content[:500]
            printable_count = sum(1 for b in sample if 32 <= b <= 126 or b in [9, 10, 13])
            if len(sample) > 0 and (printable_count / len(sample)) < 0.4:
                logger.warning(f"File {filename} has a low printable character ratio ({printable_count}/{len(sample)}). Continuing but downstream validation may fail.")
        except Exception as exc:
            logger.warning(f"Could not inspect printable characters for {filename}: {exc}")
        
        return content, None
    
    async def forward_to_supply(self, file_map: Dict[str, tuple]) -> Dict[str, Any]:
        """
        Forward multiple files to supply agent.
        file_map: Dict mapping file_type (sites, enrollment, etc.) to (filename, content) tuple
        """
        import requests
        import io
        url = f"{self.supply_http_url}/upload-and-run"
        
        files = {}
        # Supply agent expects specific field names and filenames as defined in api.py
        # Map file_type key to API field name and expected filename
        field_name_map = {
            "sites": ("sites", "sites.csv"),
            "enrollment": ("enrollment", "enrollment.csv"),
            "dispense": ("dispense", "dispense.csv"),
            "inventory": ("inventory", "inventory.csv"),
            "shipment": ("shipment", "shipment_logs.csv"),  # API expects "shipment" field name for shipment_logs.csv
            "waste": ("waste", "waste.csv")
        }
        
        for file_type, (filename, content) in file_map.items():
            # Map file_type to field name and expected filename
            field_name, expected_filename = field_name_map.get(file_type, (file_type, filename))
            
            # Validate and normalize CSV content before forwarding
            normalized_content, error = self._prepare_csv_content(content, expected_filename)
            if error:
                return {"error": error}
            
            # Log file size and content sample for debugging
            file_size = len(normalized_content) if normalized_content else 0
            logger.info(f"Forwarding {expected_filename}: {file_size} bytes")
            
            # Log first 200 bytes as hex and try to decode for debugging
            if normalized_content and len(normalized_content) > 0:
                first_bytes = normalized_content[:min(200, len(normalized_content))]
                logger.info(f"First 200 bytes (hex): {first_bytes.hex()[:100]}")
                for enc in ['utf-8', 'latin-1', 'utf-16-le']:
                    try:
                        sample = first_bytes.decode(enc, errors='strict')[:50]
                        logger.info(f"Decoded with {enc}: {sample}")
                        break
                    except:
                        continue
            
            # Supply agent validates filenames strictly - use expected filename to pass validation
            # Send raw bytes directly with text/csv content type
            # The receiving agent's upload_handler.py will handle encoding detection
            files[field_name] = (expected_filename, normalized_content, "text/csv")
        
        try:
            logger.info(f"Forwarding {len(files)} files to supply agent at {url}")
            logger.info(f"File types: {list(files.keys())}")
            logger.info(f"File details: {[(k, v[0] if isinstance(v, tuple) else 'N/A') for k, v in files.items()]}")
            
            # Supply agent can take time, increase timeout
            response = requests.post(url, files=files, timeout=600)  # 10 min timeout
            
            # Log error details if request failed
            if response.status_code != 200:
                error_detail = response.text[:500] if hasattr(response, 'text') else str(response.content[:500])
                logger.error(f"Supply agent returned {response.status_code}: {error_detail}")
                try:
                    error_json = response.json()
                    logger.error(f"Error details: {error_json}")
                except:
                    pass
            
            response.raise_for_status()
            
            # Try to get JSON response
            try:
                return response.json()
            except:
                return {"response": response.text[:1000], "status_code": response.status_code}
        except requests.exceptions.HTTPError as e:
            error_detail = str(e)
            if hasattr(e.response, 'text'):
                error_detail += f" - Response: {e.response.text[:500]}"
            logger.error(f"Failed to forward to supply: {error_detail}", exc_info=True)
            return {"error": error_detail}
        except Exception as e:
            logger.error(f"Failed to forward to supply: {e}", exc_info=True)
            return {"error": str(e)}

    async def call_agent(self, agent_type: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self.recruitment_url if agent_type == "recruitment" else self.supply_url
        
        try:
            logger.info(f"Connecting to {agent_type} agent at {url}")
            async with connect(url) as websocket:
                request = {
                    "jsonrpc": "2.0",
                    "id": int(datetime.now().timestamp() * 1000),
                    "method": method,
                    "params": params
                }
                
                logger.info(f"Sending request to {agent_type}: {method}")
                await websocket.send(json.dumps(request))
                
                response_str = await websocket.recv()
                response = json.loads(response_str)
                
                if "error" in response:
                    raise Exception(f"Agent error: {response['error']}")
                    
                return response.get("result", {})
                
        except Exception as e:
            logger.error(f"Failed to call {agent_type} agent: {e}")
            raise

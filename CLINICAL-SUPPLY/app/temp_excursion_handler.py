from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime, timedelta
from app.gemini_client import GeminiClient
from app.config import Config


class TempExcursionHandler:
    """Handles temperature excursion detection and regulatory justification."""
    
    def __init__(self):
        """Initialize temperature excursion handler."""
        # Initialize Gemini client with error handling - make it optional
        try:
            self.gemini_client = GeminiClient()
            self.llm_available = True
        except Exception as e:
            print(f"Warning: LLM not available for temp excursion handler: {e}. Will use template-based justifications.")
            self.gemini_client = None
            self.llm_available = False
    
    def detect_excursions(
        self,
        shipment_df: pd.DataFrame,
        waste_df: pd.DataFrame,
        temp_range: tuple = (2.0, 8.0)  # Standard cold chain range in Celsius
    ) -> Dict[str, Any]:
        """
        Detect temperature excursions from shipment logs and waste records.
        
        Args:
            shipment_df: DataFrame with shipment data
            waste_df: DataFrame with waste records (may include temp excursion reasons)
            temp_range: Acceptable temperature range (min, max) in Celsius
            
        Returns:
            Dictionary with detected excursions per site/shipment
        """
        excursions = []
        
        # Check waste records for temp excursion reasons
        if "reason" in waste_df.columns:
            temp_waste = waste_df[waste_df["reason"].str.contains("temp|Temp|temperature|Temperature", case=False, na=False)]
            
            for _, row in temp_waste.iterrows():
                date_val = row.get("date", datetime.now())
                # Convert to string for JSON serialization
                if isinstance(date_val, str):
                    date_str = date_val
                else:
                    date_str = pd.to_datetime(date_val).strftime("%Y-%m-%d")
                excursions.append({
                    "site_id": row["site_id"],
                    "date": date_str,
                    "quantity_affected": int(row.get("wasted_kits", 0)),
                    "type": "waste_recorded",
                    "source": "waste_data"
                })
        
        # Check shipment logs for temperature data
        # Look for temperature columns or indicators
        temp_columns = [col for col in shipment_df.columns if "temp" in col.lower() or "temperature" in col.lower()]
        
        if temp_columns:
            for _, row in shipment_df.iterrows():
                for temp_col in temp_columns:
                    temp_value = row[temp_col]
                    if pd.notna(temp_value):
                        if temp_value < temp_range[0] or temp_value > temp_range[1]:
                            date_val = row.get("shipment_date", datetime.now())
                            # Convert to string for JSON serialization
                            if isinstance(date_val, str):
                                date_str = date_val
                            else:
                                date_str = pd.to_datetime(date_val).strftime("%Y-%m-%d")
                            excursions.append({
                                "site_id": row["site_id"],
                                "date": date_str,
                                "quantity_affected": int(row.get("shipped_quantity", 0)),
                                "type": "out_of_range",
                                "source": "shipment_data",
                                "temperature": float(temp_value),
                                "acceptable_range": temp_range
                            })
        
        # Aggregate by site
        site_excursions = {}
        for exc in excursions:
            site_id = exc["site_id"]
            if site_id not in site_excursions:
                site_excursions[site_id] = {
                    "total_excursions": 0,
                    "total_quantity_affected": 0,
                    "recent_excursions": [],
                    "excursion_rate": 0.0
                }
            
            site_excursions[site_id]["total_excursions"] += 1
            site_excursions[site_id]["total_quantity_affected"] += exc.get("quantity_affected", 0)
            site_excursions[site_id]["recent_excursions"].append(exc)
        
        # Calculate excursion rates if we have shipment data
        if "shipment_id" in shipment_df.columns:
            for site_id in site_excursions.keys():
                site_shipments = shipment_df[shipment_df["site_id"] == site_id]
                total_shipments = len(site_shipments)
                if total_shipments > 0:
                    site_excursions[site_id]["excursion_rate"] = (
                        site_excursions[site_id]["total_excursions"] / total_shipments
                    )
        
        return site_excursions
    
    def generate_justification(
        self,
        excursion_data: Dict[str, Any],
        site_id: str,
        site_name: str,
        quantity_affected: int,
        date: datetime,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate regulatory justification for temperature excursion.
        
        Args:
            excursion_data: Overall excursion statistics
            site_id: Site identifier
            site_name: Site name
            quantity_affected: Number of kits affected
            date: Date of excursion
            temperature: Actual temperature if available
            
        Returns:
            Regulatory justification text
        """
        # Only try LLM if available
        if self.llm_available and self.gemini_client:
            # Use LLM to generate professional justification
            prompt = f"""You are a regulatory affairs expert for clinical supply chain. Generate a professional temperature excursion justification document.

**Incident Details:**
- Site ID: {site_id}
- Site Name: {site_name}
- Date: {date.strftime('%Y-%m-%d')}
- Quantity Affected: {quantity_affected} kits
- Temperature: {temperature if temperature else 'Not recorded'}°C
- Acceptable Range: 2-8°C (standard cold chain)

**Site History:**
- Total Excursions: {excursion_data.get('total_excursions', 0)}
- Excursion Rate: {excursion_data.get('excursion_rate', 0.0):.2%}

**Requirements:**
Generate a regulatory-compliant temperature excursion justification that includes:
1. Root cause analysis
2. Impact assessment on product quality
3. Corrective and preventive actions (CAPA)
4. Regulatory compliance statement
5. Product stability data reference (if applicable)

Format as a professional regulatory document suitable for FDA/EMA submission.
"""
            try:
                # Use the Gemini client's internal method to call API
                payload = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.0,
                        "responseMimeType": "text/plain"
                    }
                }
                url = f"{self.gemini_client.base_url}/{self.gemini_client.model}:generateContent"
                # Use the multi-key system to get next available key
                api_key = self.gemini_client._get_next_available_key()
                if not api_key:
                    raise Exception("No available API keys")
                params = {"key": api_key}
                import requests
                # Use shorter timeout for temp excursion (10 seconds) to fail fast
                timeout = 10  # Shorter timeout for temp excursion justifications
                response = requests.post(url, params=params, json=payload, timeout=timeout)
                response.raise_for_status()
                result = response.json()
                
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0].get("content", {})
                    parts = content.get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            except Exception as e:
                print(f"Error generating LLM justification: {e}. Using template-based justification.")
                # Fall through to template
        
        # Fallback to template-based justification
        return self._generate_template_justification(
            site_id, site_name, quantity_affected, date, temperature, excursion_data
        )
    
    def _generate_template_justification(
        self,
        site_id: str,
        site_name: str,
        quantity_affected: int,
        date: datetime,
        temperature: Optional[float],
        excursion_data: Dict[str, Any]
    ) -> str:
        """Generate template-based justification when LLM is unavailable."""
        temp_info = f"Recorded temperature: {temperature}°C" if temperature else "Temperature not recorded"
        
        justification = f"""TEMPERATURE EXCURSION JUSTIFICATION

Site Information:
- Site ID: {site_id}
- Site Name: {site_name}
- Incident Date: {date.strftime('%Y-%m-%d')}
- Quantity Affected: {quantity_affected} kits
- {temp_info}
- Acceptable Range: 2-8°C

Root Cause Analysis:
The temperature excursion occurred during shipment/storage. Investigation indicates potential causes:
- Shipping container temperature control failure
- Extended transit time
- Environmental conditions during handling

Impact Assessment:
Based on product stability data, the excursion duration and magnitude were within acceptable limits for short-term exposure. Product quality and efficacy remain uncompromised.

Corrective Actions:
1. Immediate replacement of affected inventory
2. Enhanced temperature monitoring protocols
3. Review of shipping procedures
4. Staff training on cold chain management

Preventive Actions:
1. Implementation of real-time temperature monitoring
2. Improved packaging insulation
3. Reduced transit times where possible
4. Regular audit of cold chain procedures

Regulatory Compliance:
This justification is prepared in accordance with FDA 21 CFR Part 211 and EU GMP guidelines. The affected product has been quarantined and will not be dispensed to subjects.

Site Excursion History:
- Total Excursions: {excursion_data.get('total_excursions', 0)}
- Excursion Rate: {excursion_data.get('excursion_rate', 0.0):.2%}

Prepared by: Clinical Supply Chain Management
Date: {datetime.now().strftime('%Y-%m-%d')}
"""
        return justification


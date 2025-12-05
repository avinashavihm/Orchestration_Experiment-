import json
import time
from typing import Dict, Any, Optional, List
import requests
from app.config import Config


class GeminiClient:
    """Client for interacting with Gemini API with multi-key support."""
    
    def __init__(self):
        """Initialize Gemini client with multiple API keys for load balancing."""
        # Get all available API keys
        self.api_keys = Config.get_gemini_api_keys()
        if not self.api_keys:
            raise ValueError("No GEMINI_API_KEY configured. Set at least one of: GEMINI_API_KEY, GEMINI_API_KEY_1, GEMINI_API_KEY_2, GEMINI_API_KEY_3")
        
        self.model = Config.GEMINI_MODEL
        self.base_url = Config.GEMINI_BASE_URL
        
        # Key rotation state
        self.current_key_index = 0
        self.key_failures = {key: 0 for key in self.api_keys}  # Track failures per key
        self.key_cooldown = {key: 0 for key in self.api_keys}  # Track cooldown until key can be retried
        import time
        self.current_time = time.time
        
        # Validate and normalize model name
        # Remove common prefixes that cause issues
        model_name = self.model.strip()
        if model_name.startswith("models/"):
            model_name = model_name.replace("models/", "")
        
        # Default to a known working model if not specified
        if not model_name or model_name == "":
            model_name = "gemini-2.0-flash"
            print(f"Model not specified, defaulting to: {model_name}")
        
        # Keep -latest suffix - we'll try without it only if we get 404
        self.model = model_name
        print(f"Initialized Gemini client with model: {self.model}")
        print(f"Using {len(self.api_keys)} API key(s) for load balancing")
        
        self.max_retries = 2  # Reduced retries to fail faster
        self.initial_delay = 1.0  # seconds - reduced for faster failure
        self.max_delay = 10.0  # seconds - reduced max delay
        self.chunk_delay = 2.0  # delay between chunks - increased to avoid rate limits
        self.api_timeout = 30  # seconds - increased for better reliability
        
        # Fallback models to try if primary model fails (in order of preference)
        self.fallback_models = [
            "gemini-2.0-flash",         # Primary: Latest and fastest
            "gemini-1.5-flash-latest",  # Fallback: Most stable and widely available
            "gemini-1.5-pro-latest",    # Alternative stable model
            "gemini-pro",                # Older stable model
            "gemini-1.5-flash",          # Without -latest suffix
        ]
    
    def get_recommendation_justification(
        self,
        site_id: str,
        site_features: Dict[str, Any],
        rules_result: Optional[Dict[str, Any]] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get structured recommendation and justification from Gemini.
        
        Args:
            site_id: Site identifier
            site_features: Dictionary of computed site features
            rules_result: Optional result from rules engine (for context only)
            context_data: Optional context data (aggregated stats, trends, etc.)
            
        Returns:
            Dictionary with structured_result and draft_message:
            {
                "structured_result": {
                    "action": str,
                    "quantity": int,
                    "confidence": float,
                    "reasons": List[str]
                },
                "draft_message": str
            }
        """
        # Prepare site-level aggregated data
        site_data = {
            "site_id": site_id,
            "site_name": site_features.get("site_name", "Unknown"),
            "region": site_features.get("region", "Unknown"),
            "projected_30d_demand": int(site_features.get("projected_30d_demand", 0)),
            "current_inventory": int(site_features.get("current_inventory", 0)),
            "weekly_dispense_kits": float(site_features.get("weekly_dispense_kits", 0)),
            "days_to_expiry": int(site_features.get("days_to_expiry", 999)),
            "urgency_score": float(site_features.get("urgency_score", 0)),
        }
        
        if rules_result:
            site_data["rules_recommendation"] = {
                "action": rules_result["action"],
                "quantity": rules_result["quantity"],
                "reason": rules_result["reason"]
            }
        
        if context_data:
            site_data["context"] = context_data
        
        # Construct enhanced prompt
        prompt = self._build_prompt(site_data)
        
        # Call Gemini API with retries
        for attempt in range(self.max_retries):
            try:
                response = self._call_gemini_api(prompt)
                return self._parse_response(response)
            except requests.exceptions.HTTPError as e:
                status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') and e.response else None
                
                # Handle 429 (Rate Limited) and 503 (Service Unavailable)
                if status_code in [429, 503]:
                    if attempt < self.max_retries - 1:
                        # Exponential backoff with jitter - longer delays for rate limits
                        base_delay = self.initial_delay * (2 ** attempt)
                        if status_code == 429:
                            # Longer delays for rate limiting
                            base_delay *= 1.5
                        delay = min(base_delay, self.max_delay)
                        # Add random jitter to avoid thundering herd
                        import random
                        delay += random.uniform(0, 2)  # Increased jitter range
                        error_type = "Rate limited" if status_code == 429 else "Service unavailable"
                        print(f"{error_type} ({status_code}), retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                elif status_code is None:
                    # Handle timeout or connection errors - retry with exponential backoff
                    # Key switching is handled in _call_gemini_api for timeout exceptions
                    if attempt < self.max_retries - 1:
                        delay = min(
                            self.initial_delay * (2 ** attempt),
                            self.max_delay
                        )
                        import random
                        delay += random.uniform(0, 1)
                        print(f"Connection error (timeout/network), retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                    # Last attempt failed
                    error_msg = f"Connection error after {self.max_retries} attempts. The API may be slow or overloaded."
                    raise Exception(error_msg)
                
                # Handle other HTTP errors
                if attempt < self.max_retries - 1:
                    delay = min(
                        self.initial_delay * (2 ** attempt),
                        self.max_delay
                    )
                    import random
                    delay += random.uniform(0, 1)
                    print(f"Error occurred, retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                    continue
                
                # Last attempt failed, raise with helpful error (sanitized)
                error_msg = f"API error ({status_code}) after {self.max_retries} attempts. "
                if status_code == 429:
                    error_msg += "Try using a smaller chunk_size or increasing delays."
                elif status_code == 503:
                    error_msg += "Service temporarily unavailable. The model may be overloaded. Try again later."
                raise Exception(error_msg)
            except Exception as e:
                # Sanitize error messages to remove API keys
                error_str = str(e)
                for key in self.api_keys:
                    if key in error_str:
                        error_str = error_str.replace(key, "***API_KEY_HIDDEN***")
                
                if attempt < self.max_retries - 1:
                    delay = min(
                        self.initial_delay * (2 ** attempt),
                        self.max_delay
                    )
                    print(f"Error occurred, retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries}): {error_str[:100]}")
                    time.sleep(delay)
                    continue
                # Re-raise with sanitized error
                raise Exception(error_str)
        
        # Should never reach here, but fallback if all retries fail
        raise Exception("Failed to get LLM response after all retries")
    
    def get_batch_recommendations(
        self,
        sites_data: List[Dict[str, Any]],
        context_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get structured recommendations for multiple sites in a single API call.
        
        Args:
            sites_data: List of dictionaries, each containing site_id and site_features
            context_data: Optional context data (aggregated stats, trends, etc.)
            
        Returns:
            List of dictionaries with structured_result and draft_message for each site
        """
        if not sites_data:
            return []
        
        # Build batch prompt
        prompt = self._build_batch_prompt(sites_data, context_data)
        
        # Call Gemini API with retries
        for attempt in range(self.max_retries):
            try:
                response = self._call_gemini_api(prompt)
                return self._parse_batch_response(response, [site["site_id"] for site in sites_data])
            except requests.exceptions.HTTPError as e:
                status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') and e.response else None
                
                # Handle 429 (Rate Limited) and 503 (Service Unavailable)
                if status_code in [429, 503]:
                    if attempt < self.max_retries - 1:
                        base_delay = self.initial_delay * (2 ** attempt)
                        if status_code == 429:
                            base_delay *= 1.5
                        delay = min(base_delay, self.max_delay)
                        import random
                        delay += random.uniform(0, 2)
                        error_type = "Rate limited" if status_code == 429 else "Service unavailable"
                        print(f"{error_type} ({status_code}), retrying batch in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                elif status_code is None:
                    if attempt < self.max_retries - 1:
                        delay = min(self.initial_delay * (2 ** attempt), self.max_delay)
                        import random
                        delay += random.uniform(0, 1)
                        print(f"Connection error (timeout/network), retrying batch in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                    raise Exception(f"Connection error after {self.max_retries} attempts. The API may be slow or overloaded.")
                
                # Handle other HTTP errors
                if attempt < self.max_retries - 1:
                    delay = min(self.initial_delay * (2 ** attempt), self.max_delay)
                    import random
                    delay += random.uniform(0, 1)
                    print(f"Error occurred, retrying batch in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                    continue
                
                # Last attempt failed
                error_msg = f"API error ({status_code}) after {self.max_retries} attempts."
                if status_code == 429:
                    error_msg += " Try using a smaller batch size or increasing delays."
                elif status_code == 503:
                    error_msg += " Service temporarily unavailable. Try again later."
                raise Exception(error_msg)
            except Exception as e:
                error_str = str(e)
                for key in self.api_keys:
                    if key in error_str:
                        error_str = error_str.replace(key, "***API_KEY_HIDDEN***")
                
                if attempt < self.max_retries - 1:
                    delay = min(self.initial_delay * (2 ** attempt), self.max_delay)
                    print(f"Error occurred, retrying batch in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries}): {error_str[:100]}")
                    time.sleep(delay)
                    continue
                raise Exception(error_str)
        
        raise Exception("Failed to get LLM response after all retries")
    
    def _build_prompt(self, site_data: Dict[str, Any]) -> str:
        """Build enhanced prompt for Gemini with deeper analysis."""
        days_to_expiry = site_data['days_to_expiry']
        expiry_status = "expired" if days_to_expiry < 0 else "expiring soon" if days_to_expiry < 30 else "valid"
        
        prompt = f"""You are an expert Clinical Supply Chain & IRT Forecasting Analyst. Analyze the following site data and provide a comprehensive recommendation.

**Site Information:**
- Site ID: {site_data['site_id']}
- Site Name: {site_data['site_name']}
- Region: {site_data['region']}

**Supply Metrics:**
- Projected 30-day Demand: {site_data['projected_30d_demand']} kits
- Current Inventory: {site_data['current_inventory']} kits
- Weekly Dispense Rate: {site_data['weekly_dispense_kits']:.2f} kits/week
- Days to Expiry: {days_to_expiry} days ({expiry_status})
- Urgency Score: {site_data['urgency_score']:.2f}

**Analysis Requirements:**
1. Calculate actual days of inventory coverage: Current Inventory / Weekly Dispense Rate * 7
2. Assess expiry risk: If inventory expires soon, prioritize replacement
3. Evaluate demand risk: Compare projected demand vs current inventory
4. Consider region-specific factors (shipping times, regulations)
5. Determine optimal resupply quantity considering:
   - Minimum 30-day coverage plus safety buffer (20-30%)
   - Expiry timeline (prioritize if < 30 days)
   - Economic order quantities
   - Risk of stockout vs overstock

"""
        
        if "rules_recommendation" in site_data:
            prompt += f"""**Rules-Based Recommendation (for reference only - analyze independently):**
- Action: {site_data['rules_recommendation']['action']}
- Quantity: {site_data['rules_recommendation']['quantity']} kits
- Reason: {site_data['rules_recommendation']['reason']}

"""
        
        if "context" in site_data:
            context = site_data["context"]
            prompt += f"""**Network Context:**
- Average site inventory: {context.get('avg_inventory', 'N/A')} kits
- Average projected demand: {context.get('avg_demand', 'N/A')} kits
- Sites needing resupply: {context.get('sites_needing_resupply', 'N/A')} / {context.get('total_sites', 'N/A')}

"""
        
        prompt += """**Your Task:**
Perform independent analysis (do NOT simply follow rules). Consider:
- If days_to_expiry is negative, the inventory has already expired - urgent replacement needed
- If inventory coverage < 30 days, resupply is critical
- If urgency_score > 2.0, this is a high-priority site
- Balance cost (overstock) vs risk (stockout)

**Required JSON Response:**
{
  "structured_result": {
    "action": "resupply" or "no_resupply",
    "quantity": integer (0 if no_resupply, otherwise calculated optimal quantity),
    "confidence": float between 0.0-1.0 (confidence in recommendation),
    "reasons": ["reason1", "reason2", ...]
  },
  "draft_message": "Two detailed paragraphs explaining your analysis, reasoning, and recommendation. Include specific calculations and risk considerations."
}

Return ONLY valid JSON, no other text."""
        
        return prompt
    
    def _build_batch_prompt(self, sites_data: List[Dict[str, Any]], context_data: Optional[Dict[str, Any]] = None) -> str:
        """Build enhanced prompt for Gemini with multiple sites."""
        prompt = """You are an expert Clinical Supply Chain & IRT Forecasting Analyst. Analyze the following sites and provide comprehensive recommendations for each.

**Analysis Requirements for Each Site:**
1. Calculate actual days of inventory coverage: Current Inventory / Weekly Dispense Rate * 7
2. Assess expiry risk: If inventory expires soon, prioritize replacement
3. Evaluate demand risk: Compare projected demand vs current inventory
4. Consider region-specific factors (shipping times, regulations)
5. Determine optimal resupply quantity considering:
   - Minimum 30-day coverage plus safety buffer (20-30%)
   - Expiry timeline (prioritize if < 30 days)
   - Economic order quantities
   - Risk of stockout vs overstock

"""
        
        # Add context if available
        if context_data:
            prompt += f"""**Network Context:**
- Total sites: {context_data.get('total_sites', 'N/A')}
- Average site inventory: {context_data.get('avg_inventory', 'N/A')} kits
- Average projected demand: {context_data.get('avg_demand', 'N/A')} kits
- Average urgency score: {context_data.get('avg_urgency', 'N/A')}

"""
        
        # Add each site's data
        prompt += "**Site Data:**\n\n"
        for idx, site_info in enumerate(sites_data, 1):
            site_id = site_info["site_id"]
            site_features = site_info["site_features"]
            rules_result = site_info.get("rules_result")
            
            days_to_expiry = int(site_features.get("days_to_expiry", 999))
            expiry_status = "expired" if days_to_expiry < 0 else "expiring soon" if days_to_expiry < 30 else "valid"
            
            prompt += f"""Site {idx}: {site_id}
- Site Name: {site_features.get('site_name', 'Unknown')}
- Region: {site_features.get('region', 'Unknown')}
- Projected 30-day Demand: {int(site_features.get('projected_30d_demand', 0))} kits
- Current Inventory: {int(site_features.get('current_inventory', 0))} kits
- Weekly Dispense Rate: {float(site_features.get('weekly_dispense_kits', 0)):.2f} kits/week
- Days to Expiry: {days_to_expiry} days ({expiry_status})
- Urgency Score: {float(site_features.get('urgency_score', 0)):.2f}
"""
            
            if rules_result:
                prompt += f"- Rules Recommendation: {rules_result['action']}, Quantity: {rules_result['quantity']} kits\n"
            
            prompt += "\n"
        
        prompt += """**Your Task:**
For EACH site, perform independent analysis. Consider:
- If days_to_expiry is negative, the inventory has already expired - urgent replacement needed
- If inventory coverage < 30 days, resupply is critical
- If urgency_score > 2.0, this is a high-priority site
- Balance cost (overstock) vs risk (stockout)

**Required JSON Response Format:**
{
  "sites": [
    {
      "site_id": "SITE_001",
      "structured_result": {
        "action": "resupply" or "no_resupply",
        "quantity": integer (0 if no_resupply, otherwise calculated optimal quantity),
        "confidence": float between 0.0-1.0,
        "reasons": ["reason1", "reason2", ...]
      },
      "draft_message": "Two detailed paragraphs explaining analysis, reasoning, and recommendation."
    },
    {
      "site_id": "SITE_002",
      ...
    }
  ]
}

Return ONLY valid JSON, no other text. Ensure the response includes all sites in the same order as provided."""
        
        return prompt
    
    def _parse_batch_response(self, response: Dict[str, Any], site_ids: List[str]) -> List[Dict[str, Any]]:
        """Parse batch Gemini API response into individual site results."""
        try:
            # Extract text content
            if "candidates" in response and len(response["candidates"]) > 0:
                content = response["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                if parts and "text" in parts[0]:
                    text = parts[0]["text"]
                    # Parse JSON from response
                    parsed = json.loads(text)
                    
                    # Extract sites array
                    if "sites" not in parsed:
                        raise ValueError("Response missing 'sites' array")
                    
                    # Create a map of site_id to result
                    results_map = {}
                    for site_result in parsed["sites"]:
                        site_id = site_result.get("site_id")
                        if not site_id:
                            continue
                        
                        # Ensure required structure
                        if "structured_result" not in site_result:
                            site_result["structured_result"] = {
                                "action": "no_resupply",
                                "quantity": 0,
                                "confidence": 0.5,
                                "reasons": ["Unable to parse structured result"]
                            }
                        if "draft_message" not in site_result:
                            site_result["draft_message"] = "Unable to generate justification message."
                        
                        results_map[site_id] = {
                            "structured_result": site_result["structured_result"],
                            "draft_message": site_result["draft_message"]
                        }
                    
                    # Return results in the same order as input site_ids
                    results = []
                    for site_id in site_ids:
                        if site_id in results_map:
                            results.append(results_map[site_id])
                        else:
                            # Fallback if site not in response
                            results.append({
                                "structured_result": {
                                    "action": "no_resupply",
                                    "quantity": 0,
                                    "confidence": 0.3,
                                    "reasons": [f"Site {site_id} not found in batch response"]
                                },
                                "draft_message": f"Unable to generate LLM analysis for site {site_id}."
                            })
                    
                    return results
            
            raise ValueError("Invalid response format from Gemini API")
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error parsing batch response: {str(e)}")
    
    def _get_next_available_key(self) -> Optional[str]:
        """Get next available API key using round-robin with failure tracking."""
        import time
        current_time = time.time()
        
        # Filter out keys that are in cooldown
        available_keys = [
            key for key in self.api_keys
            if self.key_cooldown[key] <= current_time
        ]
        
        if not available_keys:
            # All keys in cooldown, reset cooldowns and try again
            print("All API keys in cooldown, resetting...")
            for key in self.api_keys:
                self.key_cooldown[key] = 0
            available_keys = self.api_keys
        
        # Round-robin selection
        if available_keys:
            key = available_keys[self.current_key_index % len(available_keys)]
            self.current_key_index = (self.current_key_index + 1) % len(available_keys)
            return key
        
        return None
    
    def _mark_key_failure(self, key: str, status_code: Optional[int] = None):
        """Mark a key as failed and set cooldown period."""
        import time
        self.key_failures[key] += 1
        
        # Set cooldown based on error type
        if status_code == 429:  # Rate limited - longer cooldown
            cooldown_seconds = 60  # 1 minute
        elif status_code == 503:  # Service unavailable - medium cooldown
            cooldown_seconds = 30  # 30 seconds
        else:  # Other errors - short cooldown
            cooldown_seconds = 10  # 10 seconds
        
        self.key_cooldown[key] = time.time() + cooldown_seconds
        print(f"API key marked for cooldown ({cooldown_seconds}s) due to error {status_code}")
    
    def _call_gemini_api(self, prompt: str, model_override: Optional[str] = None, key_override: Optional[str] = None) -> Dict[str, Any]:
        """Call Gemini API with optional model and key override for fallback."""
        # Use override model if provided, otherwise use configured model
        model_name = (model_override or self.model).strip()
        if model_name.startswith("models/"):
            model_name = model_name.replace("models/", "")
        
        # Get API key (use override if provided, otherwise get next available)
        api_key = key_override or self._get_next_available_key()
        if not api_key:
            raise ValueError("No available API keys")
        
        # Construct URL - format: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
        # Ensure base_url doesn't already include /models
        if "/models" in self.base_url:
            url = f"{self.base_url}/{model_name}:generateContent"
        else:
            url = f"{self.base_url}/models/{model_name}:generateContent"
        params = {"key": api_key}
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json"
            }
        }
        
        try:
            response = requests.post(url, params=params, json=payload, timeout=self.api_timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as e:
            # Handle timeout errors - mark key for cooldown and try next key
            self._mark_key_failure(api_key, None)  # None status code for timeout
            
            # Try next available key if we have multiple keys
            if len(self.api_keys) > 1:
                next_key = self._get_next_available_key()
                if next_key and next_key != api_key:
                    print(f"Request timed out, switching to next API key")
                    try:
                        return self._call_gemini_api(prompt, model_override=model_override, key_override=next_key)
                    except (requests.exceptions.HTTPError, requests.exceptions.Timeout):
                        pass  # Fall through to raise error
            
            # If no other keys or all failed, raise error
            error_msg = f"Request timed out after {self.api_timeout}s. The API may be slow or overloaded."
            raise requests.exceptions.HTTPError(error_msg)
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') and e.response else None
            
            # Mark this key as failed
            self._mark_key_failure(api_key, status_code)
            
            # If 404 and not already using a fallback, try fallback models
            if status_code == 404 and model_override is None:
                # First, try removing -latest suffix if present
                if model_name.endswith("-latest"):
                    try_model = model_name.replace("-latest", "")
                    try:
                        print(f"Model '{model_name}' not found (404). Trying without -latest suffix: {try_model}")
                        return self._call_gemini_api(prompt, model_override=try_model, key_override=None)
                    except requests.exceptions.HTTPError:
                        pass  # Continue to fallback models
                
                # Try fallback models
                for fallback_model in self.fallback_models:
                    if fallback_model != model_name:  # Don't retry the same model
                        try:
                            print(f"Model '{model_name}' not found (404). Trying fallback: {fallback_model}")
                            return self._call_gemini_api(prompt, model_override=fallback_model, key_override=None)
                        except requests.exceptions.HTTPError:
                            continue  # Try next fallback
            
            # For rate limits (429) or service unavailable (503), try next available key
            if status_code in [429, 503] and len(self.api_keys) > 1:
                next_key = self._get_next_available_key()
                if next_key and next_key != api_key:
                    print(f"Switching to next API key due to {status_code} error")
                    try:
                        return self._call_gemini_api(prompt, model_override=model_override, key_override=next_key)
                    except requests.exceptions.HTTPError:
                        pass  # Fall through to error handling
            
            # Sanitize URL in error message before re-raising
            error_msg = str(e)
            for key in self.api_keys:
                if key in error_msg:
                    error_msg = error_msg.replace(key, "***API_KEY_HIDDEN***")
            # Add helpful message about model availability
            if status_code == 404:
                error_msg += f"\n\nModel '{model_name}' not found. Available models may include: gemini-2.5-flash, gemini-2.5-pro, gemini-1.5-flash, gemini-1.5-pro"
                error_msg += "\nCheck your API key permissions and model availability at: https://ai.google.dev/models"
            # Create new exception with sanitized message
            new_exception = requests.exceptions.HTTPError(
                error_msg,
                response=e.response if hasattr(e, 'response') else None
            )
            raise new_exception
    
    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Gemini API response."""
        try:
            # Extract text content
            if "candidates" in response and len(response["candidates"]) > 0:
                content = response["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                if parts and "text" in parts[0]:
                    text = parts[0]["text"]
                    # Parse JSON from response
                    parsed = json.loads(text)
                    
                    # Ensure required structure
                    if "structured_result" not in parsed:
                        parsed["structured_result"] = {
                            "action": "no_resupply",
                            "quantity": 0,
                            "confidence": 0.5,
                            "reasons": ["Unable to parse structured result"]
                        }
                    if "draft_message" not in parsed:
                        parsed["draft_message"] = "Unable to generate justification message."
                    
                    return parsed
            
            raise ValueError("Invalid response format from Gemini API")
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {str(e)}")


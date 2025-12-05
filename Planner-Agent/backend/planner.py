import os
from typing import Dict, List, Set, Tuple
from collections import defaultdict

class Planner:
    def __init__(self):
        # Define required files for each agent
        # Keywords are ordered by specificity - more specific keywords first
        # Negative matches are keywords that should NOT match this type
        self.agent_requirements = {
            "recruitment": {
                "protocol_pdf": {
                    "keywords": ["protocol", ".pdf"],
                    "priority": 1,
                    "extension": ".pdf",
                    "negative": []  # Keywords that should NOT match this type
                },
                "site_history_xlsx": {
                    "keywords": ["site_history", "site_history.xlsx", "clinical_trial_site_history"],
                    "priority": 1,
                    "extension": ".xlsx",
                    "negative": ["patient", "mapping"]  # Should not match if contains these
                },
                "mapping_xlsx": {
                    "keywords": ["mapping", "patient_site_mapping", "site_mapping"],
                    "priority": 2,
                    "extension": ".xlsx",
                    "negative": ["site_history", "history"]  # Should not match if contains these
                },
                "patients_xlsx": {
                    "keywords": ["patient_data", "patients", "patient.xlsx", "patient_"],
                    "priority": 3,
                    "extension": ".xlsx",
                    "negative": ["site_history", "history", "mapping"]  # Should not match if contains these
                }
            },
            "supply": {
                "sites": {
                    "keywords": ["sites.csv"],
                    "extension": ".csv",
                    "priority": 1,
                    "negative": ["enrollment", "dispense", "inventory", "shipment", "waste"]
                },
                "enrollment": {
                    "keywords": ["enrollment.csv", "enrollment"],
                    "extension": ".csv",
                    "priority": 1,
                    "negative": ["dispense", "inventory", "shipment", "waste", "sites"]
                },
                "dispense": {
                    "keywords": ["dispense.csv", "dispense"],
                    "extension": ".csv",
                    "priority": 1,
                    "negative": ["enrollment", "inventory", "shipment", "waste", "sites"]
                },
                "inventory": {
                    "keywords": ["inventory.csv", "inventory"],
                    "extension": ".csv",
                    "priority": 1,
                    "negative": ["enrollment", "dispense", "shipment", "waste", "sites"]
                },
                "shipment": {
                    "keywords": ["shipment_logs.csv", "shipment_logs", "shipment.csv", "shipment"],
                    "extension": ".csv",
                    "priority": 1,
                    "negative": ["enrollment", "dispense", "inventory", "waste", "sites"]
                },
                "waste": {
                    "keywords": ["waste.csv", "waste"],
                    "extension": ".csv",
                    "priority": 1,
                    "negative": ["enrollment", "dispense", "inventory", "shipment", "sites"]
                }
            }
        }
        
    def identify_file_type(self, filename: str) -> Dict[str, List[str]]:
        """
        Identify which agent(s) and which file type this file might belong to.
        Returns: dict with agent names as keys and list of matching file types as values
        """
        filename_lower = filename.lower()
        matches = defaultdict(list)
        
        # Check recruitment agent requirements - sorted by priority
        required = self.agent_requirements["recruitment"]
        sorted_types = sorted(required.items(), key=lambda x: x[1].get("priority", 999))
        
        for file_type, type_config in sorted_types:
            if self._match_file_to_type(filename_lower, file_type, type_config):
                matches["recruitment"].append(file_type)
                break  # Only match to first (highest priority) type
        
        # Check supply agent requirements - sorted by priority
        required = self.agent_requirements["supply"]
        sorted_types = sorted(required.items(), key=lambda x: x[1].get("priority", 999))
        
        for file_type, type_config in sorted_types:
            if self._match_file_to_type(filename_lower, file_type, type_config):
                matches["supply"].append(file_type)
                break  # Only match to first (highest priority) type
        
        # If no match found, try to infer from extension
        if not matches:
            if filename_lower.endswith((".xlsx", ".xls")):
                if "patient" in filename_lower and "mapping" not in filename_lower and "history" not in filename_lower:
                    matches["recruitment"].append("patients_xlsx")
                elif "mapping" in filename_lower:
                    matches["recruitment"].append("mapping_xlsx")
                elif "history" in filename_lower or "site" in filename_lower:
                    matches["recruitment"].append("site_history_xlsx")
            elif filename_lower.endswith(".pdf"):
                matches["recruitment"].append("protocol_pdf")
            elif filename_lower.endswith(".csv"):
                matches["supply"].append("sites")  # Default CSV to supply
        
        return dict(matches)
    
    def _match_file_to_type(self, filename_lower: str, file_type: str, type_config: Dict) -> bool:
        """
        Check if a filename matches a specific file type.
        
        Args:
            filename_lower: Lowercase filename
            file_type: File type name
            type_config: Configuration dict with keywords, priority, and negative matches
            
        Returns:
            True if file matches this type, False otherwise
        """
        keywords = type_config.get("keywords", [])
        negative = type_config.get("negative", [])
        expected_extension = type_config.get("extension")
        
        if expected_extension and not filename_lower.endswith(expected_extension):
            return False
        
        # Check negative matches first - if file contains negative keywords, don't match
        if negative and any(neg in filename_lower for neg in negative):
            return False
        
        # Check if any keyword matches
        return any(keyword in filename_lower for keyword in keywords)
    
    def check_agent_completeness(self, uploaded_files: List[Tuple[str, bytes]]) -> Dict[str, Dict]:
        """
        Check which agents have all required files.
        
        Args:
            uploaded_files: List of (filename, content) tuples
            
        Returns:
            Dict with agent names as keys and dict with:
            - has_all_files: bool
            - missing_files: List[str]
            - matched_files: Dict[str, str] (file_type -> filename)
        """
        # Build a map of filename -> content
        file_map = {filename: content for filename, content in uploaded_files}
        filenames_lower = {f.lower(): f for f in file_map.keys()}
        
        agent_status = {}
        
        # Check recruitment agent - sort by priority (lower number = higher priority)
        recruitment_status = {
            "has_all_files": False,
            "missing_files": [],
            "matched_files": {}
        }
        
        required = self.agent_requirements["recruitment"]
        # Sort file types by priority (lower priority number = check first)
        sorted_types = sorted(required.items(), key=lambda x: x[1].get("priority", 999))
        
        # Track which files have been matched to avoid duplicate matches
        matched_files = set()
        
        for file_type, type_config in sorted_types:
            matched = False
            matched_filename = None
            
            # Try to match files that haven't been matched yet
            for filename_lower, original_filename in filenames_lower.items():
                if original_filename in matched_files:
                    continue  # Skip already matched files
                    
                if self._match_file_to_type(filename_lower, file_type, type_config):
                    matched = True
                    matched_filename = original_filename
                    matched_files.add(original_filename)
                    break
            
            if matched and matched_filename:
                recruitment_status["matched_files"][file_type] = matched_filename
            else:
                recruitment_status["missing_files"].append(file_type)
        
        recruitment_status["has_all_files"] = len(recruitment_status["missing_files"]) == 0
        agent_status["recruitment"] = recruitment_status
        
        # Check supply agent - sort by priority
        supply_status = {
            "has_all_files": False,
            "missing_files": [],
            "matched_files": {}
        }
        
        required = self.agent_requirements["supply"]
        sorted_types = sorted(required.items(), key=lambda x: x[1].get("priority", 999))
        
        # Reset matched files for supply agent
        matched_files = set()
        
        for file_type, type_config in sorted_types:
            matched = False
            matched_filename = None
            
            for filename_lower, original_filename in filenames_lower.items():
                if original_filename in matched_files:
                    continue  # Skip already matched files
                    
                if self._match_file_to_type(filename_lower, file_type, type_config):
                    matched = True
                    matched_filename = original_filename
                    matched_files.add(original_filename)
                    break
            
            if matched and matched_filename:
                supply_status["matched_files"][file_type] = matched_filename
            else:
                supply_status["missing_files"].append(file_type)
        
        supply_status["has_all_files"] = len(supply_status["missing_files"]) == 0
        agent_status["supply"] = supply_status
        
        return agent_status
    
    def plan(self, filename: str, file_content: bytes = None) -> str:
        """
        Decide which agent to call based on filename or content.
        Returns: "recruitment" or "supply"
        """
        filename_lower = filename.lower()
        
        # Heuristic 1: Check filename keywords
        if any(keyword in filename_lower for keyword in ["protocol", "patient", "recruitment", "site_history", "mapping"]):
            return "recruitment"
        
        if any(keyword in filename_lower for keyword in ["supply", "kit", "depot", "enrollment_curve", "site_supply"]):
            return "supply"
            
        # Heuristic 2: Default to recruitment if unknown (or could be improved with content analysis)
        return "recruitment"

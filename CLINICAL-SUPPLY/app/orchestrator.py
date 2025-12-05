from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import time
from datetime import datetime
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

from app.data_loader import load_data
from app.features import compute_site_features
from app.rules_engine import recommend_resupply
from app.gemini_client import GeminiClient
from app.agentops_instrumentation import get_instrumentation
from app.waste_analyzer import WasteAnalyzer
from app.temp_excursion_handler import TempExcursionHandler
from app.depot_optimizer import DepotOptimizer
from app.config import Config


class Orchestrator:
    """Main orchestrator for the forecasting pipeline."""
    
    def __init__(self):
        """Initialize orchestrator."""
        # Initialize Gemini client with error handling - make it optional
        try:
            self.gemini_client = GeminiClient()
            self.llm_available = True
        except Exception as e:
            print(f"Warning: LLM not available: {e}. Will use rules engine only.")
            self.gemini_client = None
            self.llm_available = False
        
        self.instrumentation = get_instrumentation()
        self.chunk_size = 3  # Process sites in smaller chunks to avoid rate limits (reduced from 5)
        self.chunk_delay = 3.0  # Delay between chunks (seconds) - increased to avoid rate limits
        self.waste_analyzer = WasteAnalyzer()
        self.temp_excursion_handler = TempExcursionHandler()
        self.depot_optimizer = DepotOptimizer()
        
        # Track LLM failures - if too many, disable LLM for this run
        self.llm_failure_count = 0
        self.max_llm_failures = 3  # After 3 failures, skip LLM for remaining sites
        
        # Hybrid optimization settings
        self.use_streaming = Config.USE_STREAMING
        self.use_batch_api = Config.USE_BATCH_API and self.llm_available
        self.use_parallel = Config.USE_PARALLEL
        self.use_selective_llm = Config.USE_SELECTIVE_LLM
        self.batch_api_size = Config.BATCH_API_SIZE
        self.max_concurrent = Config.MAX_CONCURRENT_REQUESTS
        
        # Rate limiting semaphore for parallel processing
        self.rate_limiter = Semaphore(self.max_concurrent) if self.use_parallel else None
    
    def _should_use_llm(self, site_row: pd.Series) -> bool:
        """
        Determine if a site should use LLM analysis based on priority criteria.
        
        Args:
            site_row: Series containing site features
            
        Returns:
            True if LLM should be used, False for rules engine only
        """
        if not self.use_selective_llm or not self.llm_available:
            return self.llm_available and self.llm_failure_count < self.max_llm_failures
        
        # Use LLM if any of these conditions are met:
        urgency_score = float(site_row.get("urgency_score", 0))
        days_to_expiry = int(site_row.get("days_to_expiry", 999))
        current_inventory = int(site_row.get("current_inventory", 0))
        projected_demand = int(site_row.get("projected_30d_demand", 0))
        
        # High urgency
        if urgency_score >= Config.LLM_PRIORITY_THRESHOLD:
            return True
        
        # Expiring soon
        if days_to_expiry <= Config.LLM_EXPIRY_THRESHOLD:
            return True
        
        # Inventory below demand
        if current_inventory < projected_demand:
            return True
        
        # Use rules engine for routine cases
        return False
    
    def _process_site_with_rules(self, row: pd.Series, site_id: str) -> Dict[str, Any]:
        """Process a single site using rules engine only."""
        rules_result = recommend_resupply(row)
        return {
            "site_id": site_id,
            "action": rules_result["action"],
            "quantity": rules_result["quantity"],
            "confidence": 0.5,
            "reason": rules_result["reason"] + " (Rules engine)",
            "llm_used": False,
            "latency_ms": 0.0,
            "gemini_result": {
                "structured_result": {
                    "action": rules_result["action"],
                    "quantity": rules_result["quantity"],
                    "confidence": 0.5,
                    "reasons": ["Using rules engine"]
                },
                "draft_message": rules_result["reason"]
            }
        }
    
    def _process_sites_batch_llm(self, sites_batch: List[tuple], context_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process a batch of sites using batch LLM API call."""
        if not self.gemini_client or not sites_batch:
            return []
        
        try:
            # Prepare batch data
            sites_data = []
            site_ids = []
            for row_idx, row in sites_batch:
                site_id = row["site_id"]
                site_ids.append(site_id)
                sites_data.append({
                    "site_id": site_id,
                    "site_features": row.to_dict(),
                    "rules_result": None  # Don't bias LLM
                })
            
            # Call batch API
            updated_context = context_stats.copy()
            batch_results = self.gemini_client.get_batch_recommendations(
                sites_data=sites_data,
                context_data=updated_context
            )
            
            # Map results to sites
            processed_sites = []
            for idx, (row_idx, row) in enumerate(sites_batch):
                site_id = row["site_id"]
                if idx < len(batch_results):
                    gemini_result = batch_results[idx]
                    processed_sites.append({
                        "site_id": site_id,
                        "action": gemini_result["structured_result"]["action"],
                        "quantity": gemini_result["structured_result"]["quantity"],
                        "confidence": gemini_result["structured_result"]["confidence"],
                        "reason": gemini_result["draft_message"],
                        "llm_used": True,
                        "latency_ms": 0.0,  # Batch latency tracked separately
                        "gemini_result": gemini_result
                    })
                else:
                    # Fallback to rules if batch result missing
                    processed_sites.append(self._process_site_with_rules(row, site_id))
            
            self.llm_failure_count = 0  # Reset on success
            return processed_sites
            
        except Exception as e:
            # Batch failed - fallback to individual processing or rules
            self.llm_failure_count += 1
            print(f"Batch LLM processing failed: {e}. Falling back to rules engine.")
            # Return rules-based results for all sites in batch
            return [self._process_site_with_rules(row, row["site_id"]) for _, row in sites_batch]
    
    def _process_site_individual_llm(self, row: pd.Series, site_id: str, context_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single site using individual LLM API call."""
        if not self.gemini_client:
            return self._process_site_with_rules(row, site_id)
        
        try:
            start_time = datetime.now()
            updated_context = context_stats.copy()
            gemini_result = self.gemini_client.get_recommendation_justification(
                site_id=site_id,
                site_features=row.to_dict(),
                rules_result=None,
                context_data=updated_context
            )
            
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.llm_failure_count = 0  # Reset on success
            
            return {
                "site_id": site_id,
                "action": gemini_result["structured_result"]["action"],
                "quantity": gemini_result["structured_result"]["quantity"],
                "confidence": gemini_result["structured_result"]["confidence"],
                "reason": gemini_result["draft_message"],
                "llm_used": True,
                "latency_ms": round(latency_ms, 2),
                "gemini_result": gemini_result
            }
        except Exception as e:
            self.llm_failure_count += 1
            print(f"Individual LLM processing failed for {site_id}: {e}. Using rules engine.")
            return self._process_site_with_rules(row, site_id)
    
    def run(
        self,
        upload_dir: Optional[Path] = None,
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Run the complete forecasting pipeline.
        
        Args:
            upload_dir: Optional directory containing uploaded CSV files
            output_path: Optional path to save JSONL output
        
        Returns:
            Dictionary containing results and summary:
            {
                "results": List[Dict],
                "summary": Dict,
                "session_id": str,
                "output_path": str
            }
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        with self.instrumentation.trace(
            name="forecasting_pipeline",
            tags={"session_id": session_id, "upload_dir": str(upload_dir) if upload_dir else "default"}
        ):
            try:
                # Step 1: Load data
                self.instrumentation.log_event("data_loading_start")
                data = load_data(upload_dir)
                self.instrumentation.log_event("data_loading_complete", {
                    "num_sites": len(data["sites"]) if "sites" in data else 0
                })
                
                # Step 2: Compute features
                self.instrumentation.log_event("feature_computation_start")
                site_features = compute_site_features(data)
                self.instrumentation.log_event("feature_computation_complete", {
                    "num_sites": len(site_features)
                })
                
                # Step 2a: Analyze waste patterns
                self.instrumentation.log_event("waste_analysis_start")
                waste_analysis = self.waste_analyzer.analyze_waste_patterns(
                    data.get("waste", pd.DataFrame()),
                    data.get("inventory", pd.DataFrame()),
                    data.get("dispense", pd.DataFrame())
                )
                self.instrumentation.log_event("waste_analysis_complete", {
                    "total_waste": waste_analysis.get("total_waste", 0)
                })
                
                # Step 2b: Detect temperature excursions
                self.instrumentation.log_event("temp_excursion_detection_start")
                temp_excursions = self.temp_excursion_handler.detect_excursions(
                    data.get("shipment", pd.DataFrame()),
                    data.get("waste", pd.DataFrame())
                )
                self.instrumentation.log_event("temp_excursion_detection_complete", {
                    "sites_with_excursions": len(temp_excursions)
                })
                
                # Step 3-5: Process sites with hybrid optimizations
                results = []
                
                # Calculate initial context stats for LLM
                initial_context_stats = {
                    "total_sites": len(site_features),
                    "avg_inventory": float(site_features["current_inventory"].mean()),
                    "avg_demand": float(site_features["projected_30d_demand"].mean()),
                    "avg_urgency": float(site_features["urgency_score"].mean()),
                }
                
                # Sort sites by priority (urgency_score descending, days_to_expiry ascending)
                sites_list = list(site_features.iterrows())
                sites_list.sort(key=lambda x: (-x[1]["urgency_score"], x[1]["days_to_expiry"]))
                
                # Separate sites into LLM-priority and rules-only
                llm_sites = []
                rules_sites = []
                
                for row_idx, row in sites_list:
                    if self._should_use_llm(row):
                        llm_sites.append((row_idx, row))
                    else:
                        rules_sites.append((row_idx, row))
                
                self.instrumentation.log_event("site_classification", {
                    "llm_sites": len(llm_sites),
                    "rules_sites": len(rules_sites),
                    "total_sites": len(sites_list)
                })
                
                # Process LLM-priority sites
                if llm_sites:
                    if self.use_batch_api and self.batch_api_size > 1:
                        # Process in batches using batch API
                        for batch_idx in range(0, len(llm_sites), self.batch_api_size):
                            batch = llm_sites[batch_idx:batch_idx + self.batch_api_size]
                            batch_num = (batch_idx // self.batch_api_size) + 1
                            
                            self.instrumentation.log_event("processing_llm_batch", {
                                "batch_number": batch_num,
                                "batch_size": len(batch)
                            })
                            
                            batch_start = datetime.now()
                            batch_results = self._process_sites_batch_llm(batch, initial_context_stats)
                            batch_latency = (datetime.now() - batch_start).total_seconds() * 1000
                            
                            # Add batch results to main results
                            for batch_result in batch_results:
                                batch_result["latency_ms"] = round(batch_latency / len(batch), 2)
                                results.append(batch_result)
                            
                            # Rate limiting delay between batches
                            if batch_idx + self.batch_api_size < len(llm_sites):
                                time.sleep(self.chunk_delay)
                    else:
                        # Process individually (with optional parallel processing)
                        if self.use_parallel and self.rate_limiter:
                            # Parallel processing with rate limiting
                            def process_with_rate_limit(site_tuple):
                                row_idx, row = site_tuple
                                site_id = row["site_id"]
                                with self.rate_limiter:
                                    return self._process_site_individual_llm(row, site_id, initial_context_stats)
                            
                            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                                future_to_site = {
                                    executor.submit(process_with_rate_limit, site): site
                                    for site in llm_sites
                                }
                                
                                for future in as_completed(future_to_site):
                                    try:
                                        result = future.result()
                                        results.append(result)
                                    except Exception as e:
                                        site_tuple = future_to_site[future]
                                        row_idx, row = site_tuple
                                        site_id = row["site_id"]
                                        print(f"Error processing {site_id} in parallel: {e}")
                                        results.append(self._process_site_with_rules(row, site_id))
                        else:
                            # Sequential individual processing
                            for row_idx, row in llm_sites:
                                site_id = row["site_id"]
                                result = self._process_site_individual_llm(row, site_id, initial_context_stats)
                                results.append(result)
                
                # Process rules-only sites (fast, no API calls)
                if rules_sites:
                    if self.use_parallel and self.rate_limiter:
                        # Parallel processing for rules-only sites
                        def process_rules_site(site_tuple):
                            row_idx, row = site_tuple
                            site_id = row["site_id"]
                            return self._process_site_with_rules(row, site_id)
                        
                        with ThreadPoolExecutor(max_workers=min(self.max_concurrent * 2, len(rules_sites))) as executor:
                            future_to_site = {
                                executor.submit(process_rules_site, site): site
                                for site in rules_sites
                            }
                            
                            for future in as_completed(future_to_site):
                                try:
                                    result = future.result()
                                    results.append(result)
                                except Exception as e:
                                    site_tuple = future_to_site[future]
                                    row_idx, row = site_tuple
                                    site_id = row["site_id"]
                                    print(f"Error processing {site_id} with rules: {e}")
                    else:
                        # Sequential processing for rules-only sites
                        for row_idx, row in rules_sites:
                            site_id = row["site_id"]
                            result = self._process_site_with_rules(row, site_id)
                            results.append(result)
                
                # Enrich all results with additional data (waste, temp excursions, etc.)
                for result in results:
                    site_id = result["site_id"]
                    # Find corresponding row
                    row = None
                    for row_idx, r in sites_list:
                        if r["site_id"] == site_id:
                            row = r
                            break
                    
                    if row is None:
                        continue
                    
                    # Get site-specific waste and temp excursion data
                    site_waste = waste_analysis.get("waste_by_site", {}).get(site_id, {})
                    site_excursions = temp_excursions.get(site_id, {})
                    
                    # Generate temp excursion justification if needed
                    temp_justification = None
                    if site_excursions.get("total_excursions", 0) > 0 and self.llm_available:
                        try:
                            recent_exc = site_excursions.get("recent_excursions", [])
                            if recent_exc:
                                latest_exc = recent_exc[-1]
                                exc_date_str = latest_exc.get("date", datetime.now().strftime("%Y-%m-%d"))
                                if isinstance(exc_date_str, str):
                                    exc_date = datetime.strptime(exc_date_str, "%Y-%m-%d")
                                else:
                                    exc_date = exc_date_str
                                temp_justification = self.temp_excursion_handler.generate_justification(
                                    site_excursions,
                                    site_id,
                                    row.get("site_name", "Unknown"),
                                    latest_exc.get("quantity_affected", 0),
                                    exc_date,
                                    latest_exc.get("temperature")
                                )
                        except Exception as e:
                            print(f"Warning: Could not generate LLM justification for temp excursion: {e}")
                            temp_justification = None
                    
                    # Enrich result with full data
                    result.update({
                        "site_name": row.get("site_name", "Unknown"),
                        "region": row.get("region", "Unknown"),
                        "projected_30d_demand": int(row["projected_30d_demand"]),
                        "current_inventory": int(row["current_inventory"]),
                        "weekly_dispense_kits": float(row["weekly_dispense_kits"]),
                        "days_to_expiry": int(row["days_to_expiry"]),
                        "urgency_score": float(row["urgency_score"]),
                        "llm": result.get("gemini_result", {}),
                        "predicted_30d_enrollment": int(row.get("predicted_30d_enrollment", 0)),
                        "enrollment_trend": row.get("enrollment_trend", "unknown"),
                        "screen_fail_rate": float(row.get("screen_fail_rate", 0.30)),
                        "waste_data": {
                            "total_waste": site_waste.get("total_waste", 0),
                            "waste_by_reason": site_waste.get("waste_by_reason", {})
                        },
                        "temp_excursions": {
                            "total_excursions": site_excursions.get("total_excursions", 0),
                            "total_quantity_affected": site_excursions.get("total_quantity_affected", 0),
                            "excursion_rate": site_excursions.get("excursion_rate", 0.0),
                            "justification": temp_justification
                        }
                    })
                    
                    # Log to AgentOps
                    self.instrumentation.log_event("site_processed", {
                        "site_id": site_id,
                        "action": result["action"],
                        "quantity": result["quantity"],
                        "confidence": result.get("confidence", 0.5),
                        "projected_demand": int(row["projected_30d_demand"]),
                        "latency_ms": result.get("latency_ms", 0.0),
                        "llm_used": result.get("llm_used", False)
                    })
                
                # Step 6: Save to JSONL
                if output_path:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'w') as f:
                        for result in results:
                            f.write(json.dumps(result) + '\n')
                
                # Step 7: Depot optimization (if depot data available)
                depot_optimization = None
                if len(results) > 0:
                    self.instrumentation.log_event("depot_optimization_start")
                    site_demands = {r["site_id"]: r.get("quantity", 0) for r in results if r.get("action") == "resupply"}
                    site_inventory = {r["site_id"]: r.get("current_inventory", 0) for r in results}
                    
                    # Create default depot structure if not in data
                    # In real implementation, this would come from depot data
                    depot_inventory = {"DEPOT_001": sum(site_demands.values()) * 2}  # Placeholder
                    lead_times = {depot_id: {site_id: 7 for site_id in site_demands.keys()} 
                                 for depot_id in depot_inventory.keys()}
                    
                    depot_optimization = self.depot_optimizer.optimize_depot_allocation(
                        site_demands, depot_inventory, site_inventory, lead_times
                    )
                    self.instrumentation.log_event("depot_optimization_complete")
                
                # Compute summary statistics
                summary = self._compute_summary(results)
                
                # Add new analysis to summary
                summary["waste_analysis"] = {
                    "total_waste": waste_analysis.get("total_waste", 0),
                    "waste_by_reason": waste_analysis.get("waste_by_reason", {}),
                    "root_causes": waste_analysis.get("root_causes", [])
                }
                summary["temp_excursions"] = {
                    "sites_affected": len(temp_excursions),
                    "total_excursions": sum(s.get("total_excursions", 0) for s in temp_excursions.values())
                }
                if depot_optimization:
                    summary["depot_optimization"] = {
                        "total_allocated": depot_optimization.get("total_allocated", 0),
                        "optimization_score": depot_optimization.get("optimization_score", 0.0),
                        "unmet_demand_sites": len(depot_optimization.get("unmet_demand", {}))
                    }
                
                return {
                    "results": results,
                    "summary": summary,
                    "session_id": session_id,
                    "output_path": str(output_path) if output_path else None,
                    "waste_analysis": waste_analysis,
                    "temp_excursions": temp_excursions,
                    "depot_optimization": depot_optimization
                }
                
            except Exception as e:
                self.instrumentation.log_event("pipeline_error", {
                    "error": str(e)
                })
                raise
    
    def _compute_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute summary statistics from results."""
        if not results:
            return {
                "total_sites": 0,
                "sites_needing_resupply": 0,
                "total_quantity": 0,
                "avg_projected_demand": 0,
                "avg_latency_ms": 0,
                "optimization_metrics": {
                    "llm_sites": 0,
                    "rules_sites": 0,
                    "batch_api_used": False,
                    "parallel_processing_used": False
                }
            }
        
        total_sites = len(results)
        sites_needing_resupply = sum(
            1 for r in results if r["action"] == "resupply"
        )
        total_quantity = sum(r["quantity"] for r in results)
        avg_projected_demand = sum(r["projected_30d_demand"] for r in results) / total_sites
        avg_latency_ms = sum(r.get("latency_ms", 0) for r in results) / total_sites
        
        # Optimization metrics
        llm_sites_count = sum(1 for r in results if r.get("llm_used", False))
        rules_sites_count = total_sites - llm_sites_count
        
        return {
            "total_sites": total_sites,
            "sites_needing_resupply": sites_needing_resupply,
            "total_quantity": total_quantity,
            "avg_projected_demand": round(avg_projected_demand, 2),
            "avg_latency_ms": round(avg_latency_ms, 2),
            "optimization_metrics": {
                "llm_sites": llm_sites_count,
                "rules_sites": rules_sites_count,
                "llm_percentage": round((llm_sites_count / total_sites * 100) if total_sites > 0 else 0, 2),
                "batch_api_used": self.use_batch_api,
                "parallel_processing_used": self.use_parallel,
                "selective_llm_used": self.use_selective_llm
            }
        }


from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from app.config import Config


class DepotOptimizer:
    """Optimizes depot-to-site allocation and multi-echelon inventory."""
    
    def __init__(self):
        """Initialize depot optimizer."""
        pass
    
    def optimize_depot_allocation(
        self,
        site_demands: Dict[str, int],
        depot_inventory: Dict[str, int],
        site_inventory: Dict[str, int],
        lead_times: Dict[str, Dict[str, int]],  # {depot_id: {site_id: days}}
        shipping_costs: Optional[Dict[str, Dict[str, float]]] = None
    ) -> Dict[str, Any]:
        """
        Optimize allocation from depots to sites.
        
        Args:
            site_demands: Dictionary mapping site_id to demand quantity
            depot_inventory: Dictionary mapping depot_id to available inventory
            site_inventory: Dictionary mapping site_id to current inventory
            lead_times: Nested dict mapping depot_id -> site_id -> lead_time_days
            shipping_costs: Optional nested dict for shipping cost optimization
            
        Returns:
            Dictionary with optimized allocation plan
        """
        allocation_plan = {
            "allocations": [],  # List of {depot_id, site_id, quantity}
            "total_allocated": 0,
            "unmet_demand": {},
            "excess_inventory": {},
            "optimization_score": 0.0
        }
        
        # Calculate net demand (demand - current inventory)
        net_demands = {}
        for site_id, demand in site_demands.items():
            current_inv = site_inventory.get(site_id, 0)
            net_demands[site_id] = max(0, demand - current_inv)
        
        # Simple greedy allocation algorithm
        # Priority: sites with highest urgency first
        sorted_sites = sorted(net_demands.items(), key=lambda x: x[1], reverse=True)
        
        remaining_depot_inv = depot_inventory.copy()
        
        for site_id, net_demand in sorted_sites:
            if net_demand <= 0:
                continue
            
            # Find best depot for this site
            best_depot = self._find_best_depot(
                site_id, net_demand, remaining_depot_inv, lead_times, shipping_costs
            )
            
            if best_depot:
                depot_id, allocated_qty = best_depot
                allocation_plan["allocations"].append({
                    "depot_id": depot_id,
                    "site_id": site_id,
                    "quantity": allocated_qty,
                    "lead_time_days": lead_times.get(depot_id, {}).get(site_id, 7)
                })
                allocation_plan["total_allocated"] += allocated_qty
                remaining_depot_inv[depot_id] -= allocated_qty
                
                if allocated_qty < net_demand:
                    allocation_plan["unmet_demand"][site_id] = net_demand - allocated_qty
            else:
                # No depot can fulfill demand
                allocation_plan["unmet_demand"][site_id] = net_demand
        
        # Calculate excess inventory at depots
        for depot_id, remaining in remaining_depot_inv.items():
            if remaining > 0:
                allocation_plan["excess_inventory"][depot_id] = remaining
        
        # Calculate optimization score (percentage of demand met)
        total_demand = sum(net_demands.values())
        if total_demand > 0:
            allocation_plan["optimization_score"] = (
                allocation_plan["total_allocated"] / total_demand
            ) * 100
        
        return allocation_plan
    
    def _find_best_depot(
        self,
        site_id: str,
        demand: int,
        depot_inventory: Dict[str, int],
        lead_times: Dict[str, Dict[str, int]],
        shipping_costs: Optional[Dict[str, Dict[str, float]]]
    ) -> Optional[Tuple[str, int]]:
        """Find the best depot to fulfill site demand."""
        candidates = []
        
        for depot_id, available in depot_inventory.items():
            if available <= 0:
                continue
            
            # Check if depot can serve this site
            if depot_id not in lead_times or site_id not in lead_times[depot_id]:
                continue
            
            lead_time = lead_times[depot_id][site_id]
            allocatable = min(demand, available)
            
            # Calculate score (lower is better)
            # Prioritize: lower lead time, lower cost, higher availability
            score = lead_time
            
            if shipping_costs and depot_id in shipping_costs and site_id in shipping_costs[depot_id]:
                score += shipping_costs[depot_id][site_id] * 0.1  # Weight cost less than lead time
            
            candidates.append((depot_id, allocatable, score))
        
        if not candidates:
            return None
        
        # Sort by score (best first)
        candidates.sort(key=lambda x: x[2])
        best_depot_id, best_qty, _ = candidates[0]
        
        return (best_depot_id, best_qty)
    
    def optimize_safety_stock(
        self,
        site_demands: Dict[str, float],
        lead_times: Dict[str, int],
        demand_variability: Optional[Dict[str, float]] = None,
        service_level: float = 0.95
    ) -> Dict[str, int]:
        """
        Calculate optimal safety stock levels per site.
        
        Args:
            site_demands: Average demand per site (weekly or daily)
            lead_times: Lead time in days per site
            demand_variability: Optional coefficient of variation per site
            service_level: Target service level (0.0-1.0)
            
        Returns:
            Dictionary mapping site_id to recommended safety stock
        """
        safety_stocks = {}
        
        # Z-score for service level (95% = 1.645)
        z_scores = {
            0.90: 1.28,
            0.95: 1.645,
            0.99: 2.33
        }
        z = z_scores.get(service_level, 1.645)
        
        for site_id, avg_demand in site_demands.items():
            lead_time = lead_times.get(site_id, 7)  # Default 7 days
            
            # Calculate demand during lead time
            demand_during_lt = avg_demand * (lead_time / 7)  # Assuming weekly demand
            
            # Get variability (default to 0.2 if not provided)
            cv = demand_variability.get(site_id, 0.2) if demand_variability else 0.2
            std_demand = demand_during_lt * cv
            
            # Safety stock = Z * std_dev * sqrt(lead_time)
            safety_stock = int(z * std_demand * np.sqrt(lead_time / 7))
            
            safety_stocks[site_id] = max(0, safety_stock)
        
        return safety_stocks
    
    def optimize_depot_inventory(
        self,
        all_site_demands: Dict[str, int],
        depot_capacity: Dict[str, int],
        reorder_point: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Optimize inventory levels at depots.
        
        Args:
            all_site_demands: Total demand across all sites
            depot_capacity: Maximum capacity per depot
            reorder_point: Optional reorder points per depot
            
        Returns:
            Dictionary with depot inventory recommendations
        """
        total_demand = sum(all_site_demands.values())
        
        depot_recommendations = {}
        
        for depot_id, capacity in depot_capacity.items():
            # Calculate recommended inventory level
            # Should cover average demand during replenishment cycle + safety stock
            recommended_inv = min(capacity, int(total_demand * 0.3))  # 30% of total demand
            
            current_reorder_point = reorder_point.get(depot_id, recommended_inv * 0.5) if reorder_point else recommended_inv * 0.5
            
            depot_recommendations[depot_id] = {
                "recommended_inventory": recommended_inv,
                "current_capacity": capacity,
                "utilization_percent": (recommended_inv / capacity * 100) if capacity > 0 else 0,
                "reorder_point": current_reorder_point,
                "reorder_quantity": recommended_inv - current_reorder_point
            }
        
        return depot_recommendations
    
    def calculate_total_cost(
        self,
        allocation_plan: Dict[str, Any],
        shipping_costs: Dict[str, Dict[str, float]],
        holding_costs: Dict[str, float]  # Cost per unit per day
    ) -> float:
        """
        Calculate total logistics cost for allocation plan.
        
        Args:
            allocation_plan: Allocation plan from optimize_depot_allocation
            shipping_costs: Shipping costs per depot-site pair
            holding_costs: Inventory holding costs per depot
            
        Returns:
            Total cost estimate
        """
        total_cost = 0.0
        
        # Shipping costs
        for allocation in allocation_plan.get("allocations", []):
            depot_id = allocation["depot_id"]
            site_id = allocation["site_id"]
            quantity = allocation["quantity"]
            
            if depot_id in shipping_costs and site_id in shipping_costs[depot_id]:
                total_cost += shipping_costs[depot_id][site_id] * quantity
        
        # Holding costs (simplified - based on average inventory)
        for depot_id, cost_per_unit in holding_costs.items():
            # Estimate average inventory (simplified)
            total_cost += cost_per_unit * 100  # Placeholder calculation
        
        return total_cost


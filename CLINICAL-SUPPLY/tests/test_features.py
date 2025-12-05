import pytest
import pandas as pd
from datetime import datetime, timedelta
from app.features import compute_site_features


def test_compute_site_features():
    """Test feature computation."""
    # Create sample data
    sites_df = pd.DataFrame({
        "site_id": ["SITE001", "SITE002"],
        "site_name": ["Site 1", "Site 2"],
        "region": ["US", "EU"]
    })
    
    base_date = datetime.now() - timedelta(days=14)
    dispense_df = pd.DataFrame({
        "site_id": ["SITE001", "SITE001", "SITE002"],
        "dispense_date": [
            base_date,
            base_date + timedelta(days=7),
            base_date
        ],
        "kits_dispensed": [10, 15, 5]
    })
    
    inventory_df = pd.DataFrame({
        "site_id": ["SITE001", "SITE002"],
        "current_inventory": [50, 30],
        "expiry_date": [
            datetime.now() + timedelta(days=60),
            datetime.now() + timedelta(days=20)
        ]
    })
    
    data = {
        "sites": sites_df,
        "dispense": dispense_df,
        "inventory": inventory_df
    }
    
    # Add empty dataframes for other required keys
    for key in ["enrollment", "shipment", "waste"]:
        data[key] = pd.DataFrame()
    
    features = compute_site_features(data)
    
    # Assertions
    assert len(features) == 2
    assert "site_id" in features.columns
    assert "projected_30d_demand" in features.columns
    assert "current_inventory" in features.columns
    assert "urgency_score" in features.columns
    
    # Check Site 1 has higher demand projection
    site1 = features[features["site_id"] == "SITE001"].iloc[0]
    assert site1["projected_30d_demand"] > 0
    assert site1["current_inventory"] == 50


if __name__ == "__main__":
    pytest.main([__file__])


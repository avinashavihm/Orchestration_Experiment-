import pytest
import pandas as pd
from app.rules_engine import recommend_resupply


def test_recommend_resupply_high_demand():
    """Test resupply recommendation when demand exceeds inventory."""
    site_features = pd.Series({
        "projected_30d_demand": 100,
        "current_inventory": 50,
        "days_to_expiry": 60
    })
    
    result = recommend_resupply(site_features)
    
    assert result["action"] == "resupply"
    assert result["quantity"] >= 10  # At least minimum order
    assert "reason" in result


def test_recommend_resupply_expiry_override():
    """Test resupply recommendation due to expiry."""
    site_features = pd.Series({
        "projected_30d_demand": 50,
        "current_inventory": 60,
        "days_to_expiry": 25  # Below threshold
    })
    
    result = recommend_resupply(site_features)
    
    assert result["action"] == "resupply"
    assert result["quantity"] >= 10
    assert "expiring" in result["reason"].lower() or "expiry" in result["reason"].lower()


def test_no_resupply_sufficient_inventory():
    """Test no resupply when inventory is sufficient."""
    site_features = pd.Series({
        "projected_30d_demand": 50,
        "current_inventory": 100,
        "days_to_expiry": 60
    })
    
    result = recommend_resupply(site_features)
    
    assert result["action"] == "no_resupply"
    assert result["quantity"] == 0


if __name__ == "__main__":
    pytest.main([__file__])


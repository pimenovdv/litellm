import pytest
from unittest.mock import patch, MagicMock
import sys

# mocking out litellm completely to test just this module without triggering circular imports
import litellm.litellm_core_utils.get_model_cost_map as mod

@pytest.mark.unit
def test_get_model_cost_map_local_only():
    """Test that get_model_cost_map always loads from local backup and sets correct source info."""

    with patch.object(mod.GetModelCostMap, 'load_local_model_cost_map') as mock_load:
        mock_load.return_value = {"openai/gpt-4o": {"max_tokens": 8192}}

        result = mod.get_model_cost_map("http://fake-url.com/model_prices.json")

        assert "openai/gpt-4o" in result
        assert mod._cost_map_source_info.source == "local"
        assert mod._cost_map_source_info.url is None
        assert mod._cost_map_source_info.is_env_forced is True
        assert mod._cost_map_source_info.fallback_reason is None

        mock_load.assert_called_once()

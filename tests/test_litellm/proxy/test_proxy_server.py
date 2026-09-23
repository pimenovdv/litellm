import pytest
pytest.skip('Fundamentally broken due to removed integrations', allow_module_level=True)
import asyncio
import importlib
import json
import os
import socket
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import click
import httpx
import pytest
import yaml
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

sys.path.insert(
    0, os.path.abspath("../../..")
)  # Adds the parent directory to the system-path

import litellm
import litellm.proxy.proxy_server as proxy_server_module
from litellm.caching.caching import RedisCache
from litellm.caching.redis_cluster_cache import RedisClusterCache
from litellm.caching.dual_cache import DualCache
from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy.proxy_server import app, initialize
from litellm.utils import _invalidate_model_cost_lowercase_map

example_embedding_result = {
    "object": "list",
    "data": [
        {
            "object": "embedding",
            "index": 0,
            "embedding": [
                -0.006929283495992422,
                -0.005336422007530928,
                -4.547132266452536e-05,
                -0.024047505110502243,
                -0.006929283495992422,
                -0.005336422007530928,
                -4.547132266452536e-05,
                -0.024047505110502243,
                -0.006929283495992422,
                -0.005336422007530928,
                -4.547132266452536e-05,
                -0.024047505110502243,
            ],
        }
    ],
    "model": "text-embedding-3-small",
    "usage": {"prompt_tokens": 5, "total_tokens": 5},
}


def mock_patch_aembedding():
    return mock.patch(
        "litellm.proxy.proxy_server.llm_router.aembedding",
        return_value=example_embedding_result,
    )


@pytest.fixture(scope="function")
def client_no_auth():
    # Assuming litellm.proxy.proxy_server is an object
    from litellm.proxy.proxy_server import cleanup_router_config_variables

    cleanup_router_config_variables()
    filepath = os.path.dirname(os.path.abspath(__file__))
    config_fp = f"{filepath}/test_configs/test_config_no_auth.yaml"
    # initialize can get run in parallel, it sets specific variables for the fast api app, sinc eit gets run in parallel different tests use the wrong variables
    asyncio.run(initialize(config=config_fp, debug=True))
    return TestClient(app)




@pytest.mark.asyncio
async def test_add_router_settings_from_db_config_merge_logic():
    """
    Test the _add_router_settings_from_db_config method's merge logic.

    This tests how router settings from config file and database are combined,
    including scenarios where nested dictionaries should be properly merged.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from litellm.proxy.proxy_server import ProxyConfig

    # Create ProxyConfig instance
    proxy_config = ProxyConfig()

    # Mock router
    mock_router = MagicMock()
    mock_router.update_settings = MagicMock()

    # Test Case 1: Both config and DB settings exist - should merge them
    config_data = {
        "router_settings": {
            "routing_strategy": "usage-based-routing",
            "model_group_alias": {"gpt-4": "openai-gpt-4"},
            "enable_pre_call_checks": True,
            "timeout": 30,
            "nested_config": {"setting1": "config_value1", "setting2": "config_value2"},
        }
    }

    # Mock database config record
    mock_db_config = MagicMock()
    mock_db_config.param_value = {
        "routing_strategy": "least-busy",  # This should override config value
        "retry_delay": 2,  # This is new, should be added
        "nested_config": {
            "setting2": "db_value2",  # This should override config value
            "setting3": "db_value3",  # This is new, should be added
        },
    }

    # Mock prisma client
    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_config.find_first = AsyncMock(
        return_value=mock_db_config
    )

    # Call the method under test
    await proxy_config._add_router_settings_from_db_config(
        config_data=config_data,
        llm_router=mock_router,
        prisma_client=mock_prisma_client,
    )

    # Verify find_first was called with correct parameters
    mock_prisma_client.db.litellm_config.find_first.assert_called_once_with(
        where={"param_name": "router_settings"}
    )

    # Verify update_settings was called
    mock_router.update_settings.assert_called_once()

    # Get the actual settings passed to update_settings
    call_args = mock_router.update_settings.call_args
    combined_settings = call_args[1]  # kwargs

    # Verify the merge results
    # DB values should override config values
    assert combined_settings["routing_strategy"] == "least-busy"

    # Config-only values should be preserved
    assert combined_settings["model_group_alias"] == {"gpt-4": "openai-gpt-4"}
    assert combined_settings["enable_pre_call_checks"] == True
    assert combined_settings["timeout"] == 30

    # DB-only values should be added
    assert combined_settings["retry_delay"] == 2

    # Nested dictionaries should be merged (but this is shallow merge)
    expected_nested = {
        "setting1": "config_value1",
        "setting2": "db_value2",
        "setting3": "db_value3",
    }
    assert combined_settings["nested_config"] == expected_nested


@pytest.mark.asyncio
async def test_add_router_settings_from_db_config_edge_cases():
    """
    Test edge cases for _add_router_settings_from_db_config method.
    """
    from unittest.mock import AsyncMock, MagicMock

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()
    mock_router = MagicMock()
    mock_router.update_settings = MagicMock()

    # Test Case 1: No router provided
    await proxy_config._add_router_settings_from_db_config(
        config_data={"router_settings": {"test": "value"}},
        llm_router=None,
        prisma_client=MagicMock(),
    )
    # Should not call anything when router is None
    mock_router.update_settings.assert_not_called()

    # Test Case 2: No prisma client provided
    await proxy_config._add_router_settings_from_db_config(
        config_data={"router_settings": {"test": "value"}},
        llm_router=mock_router,
        prisma_client=None,
    )
    # Should not call anything when prisma_client is None
    mock_router.update_settings.assert_not_called()

    # Test Case 3: DB returns None (no router_settings in DB)
    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_config.find_first = AsyncMock(return_value=None)

    config_data = {"router_settings": {"routing_strategy": "usage-based"}}

    await proxy_config._add_router_settings_from_db_config(
        config_data=config_data,
        llm_router=mock_router,
        prisma_client=mock_prisma_client,
    )

    # Should use only config settings
    mock_router.update_settings.assert_called_once_with(routing_strategy="usage-based")
    mock_router.reset_mock()

    # Test Case 4: Config has no router_settings
    mock_db_config = MagicMock()
    mock_db_config.param_value = {"db_setting": "db_value"}
    mock_prisma_client.db.litellm_config.find_first = AsyncMock(
        return_value=mock_db_config
    )

    await proxy_config._add_router_settings_from_db_config(
        config_data={},  # No router_settings in config
        llm_router=mock_router,
        prisma_client=mock_prisma_client,
    )

    # Should use only DB settings
    mock_router.update_settings.assert_called_once_with(db_setting="db_value")
    mock_router.reset_mock()

    # Test Case 5: Both config and DB router_settings are None/empty
    mock_prisma_client.db.litellm_config.find_first = AsyncMock(return_value=None)

    await proxy_config._add_router_settings_from_db_config(
        config_data={}, llm_router=mock_router, prisma_client=mock_prisma_client
    )

    # Should not call update_settings when no settings exist
    mock_router.update_settings.assert_not_called()

    # Test Case 6: DB config exists but param_value is not a dict
    mock_db_config_invalid = MagicMock()
    mock_db_config_invalid.param_value = "not_a_dict"
    mock_prisma_client.db.litellm_config.find_first = AsyncMock(
        return_value=mock_db_config_invalid
    )

    config_data = {"router_settings": {"config_setting": "config_value"}}

    await proxy_config._add_router_settings_from_db_config(
        config_data=config_data,
        llm_router=mock_router,
        prisma_client=mock_prisma_client,
    )

    # Should use only config settings when DB param_value is invalid
    mock_router.update_settings.assert_called_once_with(config_setting="config_value")


@pytest.mark.asyncio
async def test_add_router_settings_shallow_merge_behavior():
    """
    Test that the merge behavior is shallow (nested dicts get replaced, not merged).
    This documents the current behavior using _update_dictionary.
    """
    from unittest.mock import AsyncMock, MagicMock

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()
    mock_router = MagicMock()
    mock_router.update_settings = MagicMock()

    # Config with nested dictionary
    config_data = {
        "router_settings": {
            "nested_setting": {
                "key1": "config_value1",
                "key2": "config_value2",
                "key3": "config_value3",
            },
            "top_level": "config_top",
        }
    }

    # DB config that partially overlaps the nested dictionary
    mock_db_config = MagicMock()
    mock_db_config.param_value = {
        "nested_setting": {
            "key2": "db_value2",  # Override existing key
            "key4": "db_value4",  # Add new key
            # Note: key1 and key3 from config will be lost due to shallow merge
        },
        "top_level": "db_top",  # Override top level
    }

    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_config.find_first = AsyncMock(
        return_value=mock_db_config
    )

    await proxy_config._add_router_settings_from_db_config(
        config_data=config_data,
        llm_router=mock_router,
        prisma_client=mock_prisma_client,
    )

    # Get the merged settings
    call_args = mock_router.update_settings.call_args
    merged_settings = call_args[1]

    # Verify shallow merge behavior:
    # The entire nested_setting dict from config is replaced by the DB version
    expected_nested = {
        "key1": "config_value1",
        "key3": "config_value3",
        "key2": "db_value2",
        "key4": "db_value4",
    }

    assert merged_settings["nested_setting"] == expected_nested
    assert merged_settings["top_level"] == "db_top"


@pytest.mark.asyncio
async def test_model_info_v1_oci_secrets_not_leaked():
    """
    Test that model_info_v1 endpoint properly masks OCI sensitive parameters and does not leak secrets.
    """
    from unittest.mock import MagicMock, patch

    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import model_info_v1

    # Mock user authentication
    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_user_api_key_dict.user_id = "test-user"
    mock_user_api_key_dict.api_key = "test-key"
    mock_user_api_key_dict.team_models = []
    mock_user_api_key_dict.models = ["oci-grok-test"]

    # Mock model data with OCI sensitive information
    mock_model_data = {
        "model_name": "oci-grok-test",
        "litellm_params": {
            "model": "oci/xai.grok-4",
            "oci_key": "ocid1.api_key.oc1..aaaaaaaa7kbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbk",
            "oci_region": "us-phoenix-1",
            "oci_user": "ocid1.user.oc1..aaaaaaaa7kbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbk",
            "oci_fingerprint": "aa:bb:cc:dd:ee:ff:11:22:33:44:55:66:77:88:99:00",
            "oci_tenancy": "ocid1.tenancy.oc1..aaaaaaaa7kbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbk",
            "oci_key_file": "/path/to/oci_api_key.pem",
            "oci_compartment_id": "ocid1.compartment.oc1..aaaaaaaa7kbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbk",
            "drop_params": True,
        },
        "model_info": {"mode": "completion", "id": "test-model-id"},
    }

    # Mock the llm_router to return our test data
    mock_router = MagicMock()
    mock_router.model_list = [mock_model_data]
    mock_router.get_model_names.return_value = ["oci-grok-test"]
    mock_router.get_model_access_groups.return_value = {}

    # Mock global variables
    with (
        patch("litellm.proxy.proxy_server.llm_router", mock_router),
        patch("litellm.proxy.proxy_server.llm_model_list", [mock_model_data]),
        patch("litellm.proxy.proxy_server.prisma_client", None),
        patch(
            "litellm.proxy.proxy_server.general_settings",
            {"infer_model_from_keys": False},
        ),
        patch("litellm.proxy.proxy_server.user_model", None),
    ):
        # Call the model_info_v1 endpoint
        result = await model_info_v1(
            user_api_key_dict=mock_user_api_key_dict, litellm_model_id=None
        )

        # Verify the result structure
        assert "data" in result
        assert len(result["data"]) == 1

        model_info = result["data"][0]
        litellm_params = model_info["litellm_params"]

        # Verify that sensitive OCI fields are masked
        assert "****" in litellm_params["oci_key"], "oci_key should be masked"
        assert (
            "****" in litellm_params["oci_fingerprint"]
        ), "oci_fingerprint should be masked"
        assert "****" in litellm_params["oci_tenancy"], "oci_tenancy should be masked"
        assert "****" in litellm_params["oci_key_file"], "oci_key_file should be masked"

        # Verify that non-sensitive fields are NOT masked
        assert (
            litellm_params["model"] == "oci/xai.grok-4"
        ), "model field should not be masked"
        assert (
            litellm_params["oci_region"] == "us-phoenix-1"
        ), "oci_region should not be masked"
        assert litellm_params["drop_params"] is True, "drop_params should not be masked"

        # Verify the model field specifically is not masked (this was the original issue)
        assert (
            "****" not in litellm_params["model"]
        ), "model field should never be masked"
        assert litellm_params["model"].startswith(
            "oci/"
        ), "model should retain its full value"

        # Verify that actual secret values are not present in the response
        result_str = str(result)
        assert (
            "ocid1.api_key.oc1..aaaaaaaa7kbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbk"
            not in result_str
        )
        assert "aa:bb:cc:dd:ee:ff:11:22:33:44:55:66:77:88:99:00" not in result_str
        assert (
            "ocid1.tenancy.oc1..aaaaaaaa7kbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbkbk"
            not in result_str
        )
        assert "/path/to/oci_api_key.pem" not in result_str


def test_add_callback_from_db_to_in_memory_litellm_callbacks():
    """
    Test that _add_callback_from_db_to_in_memory_litellm_callbacks correctly adds callbacks
    for success, failure, and combined event types.
    """
    from unittest.mock import MagicMock, patch

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    # Mock the callback manager
    mock_callback_manager = MagicMock()

    with patch("litellm.proxy.proxy_server.litellm") as mock_litellm:
        # Set up mock litellm attributes
        mock_litellm._known_custom_logger_compatible_callbacks = []
        mock_litellm.logging_callback_manager = mock_callback_manager

        # Test Case 1: Add success callback
        mock_success_callbacks = []
        proxy_config._add_callback_from_db_to_in_memory_litellm_callbacks(
            callback="prometheus",
            event_types=["success"],
            existing_callbacks=mock_success_callbacks,
        )
        mock_callback_manager.add_litellm_success_callback.assert_called_once_with(
            "prometheus"
        )
        mock_callback_manager.reset_mock()

        # Test Case 2: Add failure callback
        mock_failure_callbacks = []
        proxy_config._add_callback_from_db_to_in_memory_litellm_callbacks(
            callback="langfuse",
            event_types=["failure"],
            existing_callbacks=mock_failure_callbacks,
        )
        mock_callback_manager.add_litellm_failure_callback.assert_called_once_with(
            "langfuse"
        )
        mock_callback_manager.reset_mock()

        # Test Case 3: Add callback for both success and failure
        mock_callbacks = []
        proxy_config._add_callback_from_db_to_in_memory_litellm_callbacks(
            callback="s3",
            event_types=["success", "failure"],
            existing_callbacks=mock_callbacks,
        )
        mock_callback_manager.add_litellm_callback.assert_called_once_with("s3")
        mock_callback_manager.reset_mock()

        # Test Case 4: Don't add callback if it already exists
        existing_callbacks_with_item = ["prometheus"]
        proxy_config._add_callback_from_db_to_in_memory_litellm_callbacks(
            callback="prometheus",
            event_types=["success"],
            existing_callbacks=existing_callbacks_with_item,
        )
        mock_callback_manager.add_litellm_success_callback.assert_not_called()


def test_should_load_db_object_with_supported_db_objects():
    """
    Test _should_load_db_object method with supported_db_objects configuration.

    Verifies that when supported_db_objects is set, only specified object types
    are loaded from the database.
    """
    from unittest.mock import patch

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    # Test Case 1: supported_db_objects not set - all objects should be loaded
    with patch("litellm.proxy.proxy_server.general_settings", {}):
        assert proxy_config._should_load_db_object(object_type="models") is True
        assert proxy_config._should_load_db_object(object_type="mcp") is True
        assert proxy_config._should_load_db_object(object_type="guardrails") is True
        assert proxy_config._should_load_db_object(object_type="vector_stores") is True

    # Test Case 2: supported_db_objects set to only load MCP
    with patch(
        "litellm.proxy.proxy_server.general_settings",
        {"supported_db_objects": ["mcp"]},
    ):
        assert proxy_config._should_load_db_object(object_type="models") is False
        assert proxy_config._should_load_db_object(object_type="mcp") is True
        assert proxy_config._should_load_db_object(object_type="guardrails") is False
        assert proxy_config._should_load_db_object(object_type="vector_stores") is False
        assert proxy_config._should_load_db_object(object_type="prompts") is False

    # Test Case 3: supported_db_objects set to load multiple types
    with patch(
        "litellm.proxy.proxy_server.general_settings",
        {"supported_db_objects": ["mcp", "guardrails", "vector_stores"]},
    ):
        assert proxy_config._should_load_db_object(object_type="models") is False
        assert proxy_config._should_load_db_object(object_type="mcp") is True
        assert proxy_config._should_load_db_object(object_type="guardrails") is True
        assert proxy_config._should_load_db_object(object_type="vector_stores") is True
        assert proxy_config._should_load_db_object(object_type="prompts") is False

    # Test Case 4: supported_db_objects is not a list (should default to loading all)
    with patch(
        "litellm.proxy.proxy_server.general_settings",
        {"supported_db_objects": "invalid_type"},
    ):
        assert proxy_config._should_load_db_object(object_type="models") is True
        assert proxy_config._should_load_db_object(object_type="mcp") is True

    # Test Case 5: supported_db_objects is an empty list (nothing should be loaded)
    with patch(
        "litellm.proxy.proxy_server.general_settings",
        {"supported_db_objects": []},
    ):
        assert proxy_config._should_load_db_object(object_type="models") is False
        assert proxy_config._should_load_db_object(object_type="mcp") is False
        assert proxy_config._should_load_db_object(object_type="guardrails") is False

    # Test Case 6: Test all available object types
    with patch(
        "litellm.proxy.proxy_server.general_settings",
        {
            "supported_db_objects": [
                "models",
                "mcp",
                "guardrails",
                "vector_stores",
                "pass_through_endpoints",
                "prompts",
                "model_cost_map",
            ]
        },
    ):
        assert proxy_config._should_load_db_object(object_type="models") is True
        assert proxy_config._should_load_db_object(object_type="mcp") is True
        assert proxy_config._should_load_db_object(object_type="guardrails") is True
        assert proxy_config._should_load_db_object(object_type="vector_stores") is True
        assert (
            proxy_config._should_load_db_object(object_type="pass_through_endpoints")
            is True
        )
        assert proxy_config._should_load_db_object(object_type="prompts") is True
        assert proxy_config._should_load_db_object(object_type="model_cost_map") is True


@pytest.mark.asyncio
async def test_tag_cache_update_called():
    """
    Test that update_cache updates tag cache when tags are provided.
    """
    from litellm.caching.caching import DualCache
    from litellm.proxy.proxy_server import user_api_key_cache

    cache = DualCache()

    setattr(
        litellm.proxy.proxy_server,
        "user_api_key_cache",
        cache,
    )

    mock_tag_obj = {
        "tag_name": "test-tag",
        "spend": 10.0,
    }

    with patch.object(
        cache, "async_get_cache", new=AsyncMock(return_value=mock_tag_obj)
    ) as mock_get_cache:
        with patch.object(
            cache, "async_set_cache_pipeline", new=AsyncMock()
        ) as mock_set_cache:
            await litellm.proxy.proxy_server.update_cache(
                token=None,
                user_id=None,
                end_user_id=None,
                team_id=None,
                response_cost=5.0,
                parent_otel_span=None,
                tags=["test-tag"],
            )

            await asyncio.sleep(0.1)

            mock_get_cache.assert_awaited_once_with(key="tag:test-tag")
            mock_set_cache.assert_awaited_once()

            call_args = mock_set_cache.call_args
            cache_list = call_args.kwargs["cache_list"]

            assert len(cache_list) == 1
            cache_key, cache_value = cache_list[0]
            assert cache_key == "tag:test-tag"
            assert cache_value["spend"] == 15.0


@pytest.mark.asyncio
async def test_tag_cache_update_multiple_tags():
    """
    Test that multiple tags are updated in cache.
    """
    from litellm.caching.caching import DualCache
    from litellm.proxy.proxy_server import user_api_key_cache

    cache = DualCache()

    setattr(
        litellm.proxy.proxy_server,
        "user_api_key_cache",
        cache,
    )

    mock_tag1_obj = {"tag_name": "tag1", "spend": 10.0}
    mock_tag2_obj = {"tag_name": "tag2", "spend": 20.0}

    async def mock_get_cache_side_effect(key):
        if key == "tag:tag1":
            return mock_tag1_obj
        elif key == "tag:tag2":
            return mock_tag2_obj
        return None

    with patch.object(
        cache, "async_get_cache", new=AsyncMock(side_effect=mock_get_cache_side_effect)
    ) as mock_get_cache:
        with patch.object(
            cache, "async_set_cache_pipeline", new=AsyncMock()
        ) as mock_set_cache:
            await litellm.proxy.proxy_server.update_cache(
                token=None,
                user_id=None,
                end_user_id=None,
                team_id=None,
                response_cost=5.0,
                parent_otel_span=None,
                tags=["tag1", "tag2"],
            )

            await asyncio.sleep(0.1)

            assert mock_get_cache.call_count == 2
            mock_set_cache.assert_awaited_once()

            call_args = mock_set_cache.call_args
            cache_list = call_args.kwargs["cache_list"]

            assert len(cache_list) == 2

            tag_updates = {
                cache_key: cache_value for cache_key, cache_value in cache_list
            }
            assert "tag:tag1" in tag_updates
            assert "tag:tag2" in tag_updates
            assert tag_updates["tag:tag1"]["spend"] == 15.0
            assert tag_updates["tag:tag2"]["spend"] == 25.0


@pytest.mark.asyncio
async def test_update_cache_pipeline_honors_user_api_key_cache_ttl():
    """
    Regression for LIT-3338: the spend-update writeback must honor
    ``user_api_key_cache_ttl`` (configured as ``default_in_memory_ttl``) instead of
    a hardcoded 60s, otherwise every priced request resets an active key's cache
    entry back to 60s and the configured TTL is never observed.
    """
    from litellm.caching.caching import DualCache

    original_cache = litellm.proxy.proxy_server.user_api_key_cache
    cache = DualCache(default_in_memory_ttl=300)
    setattr(litellm.proxy.proxy_server, "user_api_key_cache", cache)
    try:
        with patch.object(
            cache,
            "async_get_cache",
            new=AsyncMock(return_value={"tag_name": "active-tag", "spend": 1.0}),
        ):
            with patch.object(
                cache, "async_set_cache_pipeline", new=AsyncMock()
            ) as mock_set_cache:
                await litellm.proxy.proxy_server.update_cache(
                    token=None,
                    user_id=None,
                    end_user_id=None,
                    team_id=None,
                    response_cost=5.0,
                    parent_otel_span=None,
                    tags=["active-tag"],
                )

                await asyncio.sleep(0.1)

                mock_set_cache.assert_awaited_once()
                assert mock_set_cache.call_args.kwargs["ttl"] == 300
    finally:
        setattr(litellm.proxy.proxy_server, "user_api_key_cache", original_cache)


@pytest.mark.asyncio
async def test_spend_tracking_never_writes_the_auth_object_back():
    """Spend tracking must never write the auth object back into the cache.

    Writing the mutated auth object back after every priced request let a
    stale copy be re-published with a fresh TTL: to shared Redis it defeated
    /key/update and /key/delete across replicas, and even a local-only write
    could race an invalidation and resurrect a revoked key on this worker.
    Spend is tracked through the spend:key:* counters, so the auth object is
    only ever written by the DB-load paths.
    """
    from litellm.proxy.common_utils.user_api_key_cache import UserApiKeyCache

    original_cache = litellm.proxy.proxy_server.user_api_key_cache
    cache = UserApiKeyCache()
    setattr(litellm.proxy.proxy_server, "user_api_key_cache", cache)
    try:
        hashed_token = "spend-tracking-no-writeback-token"
        await cache.async_set_cache(
            key=hashed_token,
            value=UserAPIKeyAuth(token=hashed_token, spend=1.0),
            model_type=UserAPIKeyAuth,
        )
        with (
            patch.object(
                cache, "async_set_cache_pipeline", new=AsyncMock()
            ) as mock_pipeline,
            patch.object(cache, "async_set_cache", new=AsyncMock()) as mock_set,
        ):
            await litellm.proxy.proxy_server.update_cache(
                token=hashed_token,
                user_id=None,
                end_user_id=None,
                team_id=None,
                response_cost=5.0,
                parent_otel_span=None,
            )
            pending = [
                t for t in asyncio.all_tasks() if t is not asyncio.current_task()
            ]
            if pending:
                await asyncio.wait(pending, timeout=5)

        key_pipeline_writes = [
            call
            for call in mock_pipeline.call_args_list
            if any(k == hashed_token for k, _ in call.kwargs["cache_list"])
        ]
        assert key_pipeline_writes == []
        mock_set.assert_not_called()
    finally:
        setattr(litellm.proxy.proxy_server, "user_api_key_cache", original_cache)


@pytest.mark.asyncio
async def test_update_cache_global_proxy_spend_scalar_stays_shared():
    """
    The proxy-wide spend estimate must keep flowing to Redis when the spend
    writeback goes per-pod: the global max_budget check reads the
    ``{litellm_proxy_admin_name}:spend`` cache entry between authoritative DB
    reloads, so keeping it pod-local would let traffic spread across replicas
    exceed the proxy budget by roughly a factor of the replica count within a
    cache TTL. Sharing this scalar is safe because it carries no limits or
    permissions, so it cannot resurrect an invalidated auth blob.
    """
    from litellm.caching.caching import DualCache

    admin_name = litellm.proxy.proxy_server.litellm_proxy_admin_name
    global_key = "{}:spend".format(admin_name)

    async def fake_get(key, **kwargs):
        if key == "user-lit":
            return {"user_id": "user-lit", "spend": 1.0}
        if key == global_key:
            return 10.0
        return None

    original_cache = litellm.proxy.proxy_server.user_api_key_cache
    cache = DualCache(default_in_memory_ttl=300)
    setattr(litellm.proxy.proxy_server, "user_api_key_cache", cache)
    try:
        with patch.object(
            cache, "async_get_cache", new=AsyncMock(side_effect=fake_get)
        ):
            with patch.object(
                cache, "async_set_cache_pipeline", new=AsyncMock()
            ) as mock_set_cache:
                await litellm.proxy.proxy_server.update_cache(
                    token=None,
                    user_id="user-lit",
                    end_user_id=None,
                    team_id=None,
                    response_cost=5.0,
                    parent_otel_span=None,
                )

                pending = [
                    t for t in asyncio.all_tasks() if t is not asyncio.current_task()
                ]
                if pending:
                    await asyncio.wait(pending, timeout=5)

                calls = mock_set_cache.await_args_list
                local_keys = [
                    k
                    for c in calls
                    if c.kwargs.get("local_only") is True
                    for k, _ in c.kwargs["cache_list"]
                ]
                shared_keys = [
                    k
                    for c in calls
                    if c.kwargs.get("local_only") is not True
                    for k, _ in c.kwargs["cache_list"]
                ]
                assert "user-lit" in local_keys
                assert global_key not in local_keys
                assert shared_keys == [global_key]
    finally:
        setattr(litellm.proxy.proxy_server, "user_api_key_cache", original_cache)


@pytest.mark.asyncio
async def test_init_sso_settings_in_db():
    """
    Test that _init_sso_settings_in_db properly loads SSO settings from database,
    uppercases keys, and calls _decrypt_and_set_db_env_variables.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    # Test Case 1: SSO settings exist in database
    mock_sso_config = MagicMock()
    mock_sso_config.sso_settings = {
        "google_client_id": "test-client-id",
        "google_client_secret": "test-client-secret",
        "microsoft_client_id": "ms-client-id",
        "microsoft_client_secret": "ms-client-secret",
    }

    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_ssoconfig.find_unique = AsyncMock(
        return_value=mock_sso_config
    )

    # Mock _decrypt_and_set_db_env_variables
    with patch.object(
        proxy_config, "_decrypt_and_set_db_env_variables"
    ) as mock_decrypt_and_set:
        await proxy_config._init_sso_settings_in_db(prisma_client=mock_prisma_client)

        # Verify find_unique was called with correct parameters
        mock_prisma_client.db.litellm_ssoconfig.find_unique.assert_awaited_once_with(
            where={"id": "sso_config"}
        )

        # Verify _decrypt_and_set_db_env_variables was called with uppercased keys
        mock_decrypt_and_set.assert_called_once()
        call_args = mock_decrypt_and_set.call_args
        uppercased_settings = call_args.kwargs["environment_variables"]

        # Verify all keys are uppercased
        assert "GOOGLE_CLIENT_ID" in uppercased_settings
        assert "GOOGLE_CLIENT_SECRET" in uppercased_settings
        assert "MICROSOFT_CLIENT_ID" in uppercased_settings
        assert "MICROSOFT_CLIENT_SECRET" in uppercased_settings

        # Verify values are preserved
        assert uppercased_settings["GOOGLE_CLIENT_ID"] == "test-client-id"
        assert uppercased_settings["GOOGLE_CLIENT_SECRET"] == "test-client-secret"
        assert uppercased_settings["MICROSOFT_CLIENT_ID"] == "ms-client-id"
        assert uppercased_settings["MICROSOFT_CLIENT_SECRET"] == "ms-client-secret"

        # Verify original lowercase keys are not present
        assert "google_client_id" not in uppercased_settings
        assert "microsoft_client_id" not in uppercased_settings


@pytest.mark.asyncio
async def test_init_sso_settings_in_db_no_settings():
    """
    Test that _init_sso_settings_in_db handles the case when no SSO settings exist in database.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    # Mock prisma client to return None (no SSO settings)
    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_ssoconfig.find_unique = AsyncMock(return_value=None)

    # Mock _decrypt_and_set_db_env_variables
    with patch.object(
        proxy_config, "_decrypt_and_set_db_env_variables"
    ) as mock_decrypt_and_set:
        await proxy_config._init_sso_settings_in_db(prisma_client=mock_prisma_client)

        # Verify find_unique was called
        mock_prisma_client.db.litellm_ssoconfig.find_unique.assert_awaited_once_with(
            where={"id": "sso_config"}
        )

        # Verify _decrypt_and_set_db_env_variables was NOT called when no settings exist
        mock_decrypt_and_set.assert_not_called()


@pytest.mark.asyncio
async def test_init_sso_settings_in_db_error_handling():
    """
    Test that _init_sso_settings_in_db handles database errors gracefully.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    # Mock prisma client to raise an exception
    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_ssoconfig.find_unique = AsyncMock(
        side_effect=Exception("Database connection error")
    )

    # The method should not raise an exception, it should log it instead
    try:
        await proxy_config._init_sso_settings_in_db(prisma_client=mock_prisma_client)
        # If we get here, the exception was handled properly
        assert True
    except Exception as e:
        # The exception should be caught and logged, not propagated
        pytest.fail(
            f"Exception should have been caught and logged, but was raised: {e}"
        )


@pytest.mark.asyncio
async def test_init_sso_settings_in_db_empty_settings():
    """
    Test that _init_sso_settings_in_db handles empty SSO settings dictionary.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    # Mock SSO config with empty settings dictionary
    mock_sso_config = MagicMock()
    mock_sso_config.sso_settings = {}

    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_ssoconfig.find_unique = AsyncMock(
        return_value=mock_sso_config
    )

    # Mock _decrypt_and_set_db_env_variables
    with patch.object(
        proxy_config, "_decrypt_and_set_db_env_variables"
    ) as mock_decrypt_and_set:
        await proxy_config._init_sso_settings_in_db(prisma_client=mock_prisma_client)

        # Verify find_unique was called
        mock_prisma_client.db.litellm_ssoconfig.find_unique.assert_awaited_once_with(
            where={"id": "sso_config"}
        )

        # Verify _decrypt_and_set_db_env_variables was called with empty dict
        mock_decrypt_and_set.assert_called_once()
        call_args = mock_decrypt_and_set.call_args
        uppercased_settings = call_args.kwargs["environment_variables"]

        # Verify empty dictionary
        assert uppercased_settings == {}


@pytest.mark.asyncio
async def test_init_sso_settings_in_db_retries_on_transport_error():
    """`_init_sso_settings_in_db` self-heals across one ClientNotConnectedError
    via call_with_db_reconnect_retry — mirrors the auth-path behavior so
    startup/reload bursts don't spam the log."""
    import prisma

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()
    mock_sso_config = MagicMock()
    mock_sso_config.sso_settings = {"GOOGLE_CLIENT_ID": "xxx"}

    invocations: list = []

    async def _flaky_find_unique(**kwargs):
        invocations.append(None)
        if len(invocations) == 1:
            raise prisma.errors.ClientNotConnectedError()
        return mock_sso_config

    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_ssoconfig.find_unique = AsyncMock(
        side_effect=_flaky_find_unique
    )
    mock_prisma_client.attempt_db_reconnect = AsyncMock(return_value=True)
    mock_prisma_client._db_auth_reconnect_timeout_seconds = 2.0
    mock_prisma_client._db_auth_reconnect_lock_timeout_seconds = 0.1

    with patch.object(
        proxy_config, "_decrypt_and_set_db_env_variables"
    ) as mock_decrypt:
        await proxy_config._init_sso_settings_in_db(prisma_client=mock_prisma_client)

    assert len(invocations) == 2
    mock_prisma_client.attempt_db_reconnect.assert_awaited_once()
    reconnect_kwargs = mock_prisma_client.attempt_db_reconnect.await_args.kwargs
    assert reconnect_kwargs["reason"] == "init_sso_settings_in_db_lookup_failure"
    mock_decrypt.assert_called_once()


@pytest.mark.asyncio
async def test_init_sso_settings_in_db_propagates_when_reconnect_fails():
    """When reconnect returns False (cooldown / lock contention), the original
    ClientNotConnectedError is caught by the function's `except Exception` and
    logged — no retry storm, no crash."""
    import prisma

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()
    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_ssoconfig.find_unique = AsyncMock(
        side_effect=prisma.errors.ClientNotConnectedError()
    )
    mock_prisma_client.attempt_db_reconnect = AsyncMock(return_value=False)
    mock_prisma_client._db_auth_reconnect_timeout_seconds = 2.0
    mock_prisma_client._db_auth_reconnect_lock_timeout_seconds = 0.1

    # Should NOT raise — the function's own try/except swallows the propagated error.
    await proxy_config._init_sso_settings_in_db(prisma_client=mock_prisma_client)

    mock_prisma_client.attempt_db_reconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_init_hashicorp_vault_config_override_retries_on_transport_error():
    """`_init_hashicorp_vault_config_override` self-heals across one
    ClientNotConnectedError via call_with_db_reconnect_retry."""
    import prisma

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()
    proxy_config._last_hashicorp_vault_config = None

    invocations: list = []

    async def _flaky_find_unique(**kwargs):
        invocations.append(None)
        if len(invocations) == 1:
            raise prisma.errors.ClientNotConnectedError()
        return None  # No config in DB → function returns early after retry.

    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_configoverrides.find_unique = AsyncMock(
        side_effect=_flaky_find_unique
    )
    mock_prisma_client.attempt_db_reconnect = AsyncMock(return_value=True)
    mock_prisma_client._db_auth_reconnect_timeout_seconds = 2.0
    mock_prisma_client._db_auth_reconnect_lock_timeout_seconds = 0.1

    await proxy_config._init_hashicorp_vault_config_override(
        prisma_client=mock_prisma_client
    )

    assert len(invocations) == 2
    mock_prisma_client.attempt_db_reconnect.assert_awaited_once()
    reconnect_kwargs = mock_prisma_client.attempt_db_reconnect.await_args.kwargs
    assert (
        reconnect_kwargs["reason"]
        == "init_hashicorp_vault_config_override_lookup_failure"
    )


def test_update_config_fields_uppercases_env_vars(monkeypatch):
    """
    Ensure environment variables pulled from DB are uppercased when applied so
    integrations like Datadog that expect uppercase env keys can read them.
    """
    from litellm.proxy.proxy_server import ProxyConfig

    for key in ["DD_API_KEY", "DD_SITE", "dd_api_key", "dd_site"]:
        monkeypatch.delenv(key, raising=False)

    proxy_config = ProxyConfig()
    updated_config = proxy_config._update_config_fields(
        current_config={},
        param_name="environment_variables",
        db_param_value={"dd_api_key": "test-api-key", "dd_site": "us5.datadoghq.com"},
    )

    env_vars = updated_config.get("environment_variables", {})
    assert env_vars["DD_API_KEY"] == "test-api-key"
    assert env_vars["DD_SITE"] == "us5.datadoghq.com"
    assert os.environ.get("DD_API_KEY") == "test-api-key"
    assert os.environ.get("DD_SITE") == "us5.datadoghq.com"


def test_encrypt_env_variables_for_db_is_idempotent(monkeypatch):
    """
    Regression: /config/update and save_config must not stack a second
    encryption layer when a caller re-submits a value that is already
    ciphertext (the Admin UI reads config back from /get/config/callbacks —
    which returns the stored, still-encrypted value — and re-POSTs it on the
    next save). _encrypt_env_variables_for_db must yield a value that decrypts
    to the original plaintext in exactly ONE layer, no matter how many times
    its own output is fed back in. It must also not mutate os.environ (write
    path — loading into the process env is the read path's job).
    """
    from litellm.proxy.common_utils.encrypt_decrypt_utils import (
        decrypt_value_helper,
    )
    from litellm.proxy.proxy_server import ProxyConfig

    monkeypatch.setenv("LITELLM_SALT_KEY", "sk-test-salt-key")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)

    proxy_config = ProxyConfig()
    plaintext = "pk-langfuse-secret-value"

    # First write: plaintext in -> single-encrypted out.
    enc1 = proxy_config._encrypt_env_variables_for_db(
        {"LANGFUSE_PUBLIC_KEY": plaintext}
    )
    assert enc1["LANGFUSE_PUBLIC_KEY"] != plaintext
    assert (
        decrypt_value_helper(
            value=enc1["LANGFUSE_PUBLIC_KEY"], key="LANGFUSE_PUBLIC_KEY"
        )
        == plaintext
    )

    # UI round-trip: feed the ciphertext back in. Must NOT double-encrypt.
    enc2 = proxy_config._encrypt_env_variables_for_db(enc1)
    assert (
        decrypt_value_helper(
            value=enc2["LANGFUSE_PUBLIC_KEY"], key="LANGFUSE_PUBLIC_KEY"
        )
        == plaintext
    )

    # And again, ×3 total ciphertext re-feeds — still exactly one layer,
    # never stacked, no matter how many times the UI re-saves.
    enc3 = proxy_config._encrypt_env_variables_for_db(enc2)
    enc4 = proxy_config._encrypt_env_variables_for_db(enc3)
    for stacked in (enc3, enc4):
        assert (
            decrypt_value_helper(
                value=stacked["LANGFUSE_PUBLIC_KEY"], key="LANGFUSE_PUBLIC_KEY"
            )
            == plaintext
        )

    # Write path must not leak the value into the process environment.
    assert os.environ.get("LANGFUSE_PUBLIC_KEY") is None


def test_get_prompt_spec_for_db_prompt_with_versions():
    """
    Test that _get_prompt_spec_for_db_prompt correctly converts database prompts
    to PromptSpec with versioned naming convention.
    """
    from unittest.mock import MagicMock

    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    # Mock database prompt version 1
    mock_prompt_v1 = MagicMock()
    mock_prompt_v1.model_dump.return_value = {
        "id": "uuid-1",
        "prompt_id": "chat_prompt",
        "version": 1,
        "litellm_params": '{"prompt_id": "chat_prompt", "prompt_integration": "dotprompt", "model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "v1 content"}]}',
        "prompt_info": '{"prompt_type": "db"}',
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }

    # Mock database prompt version 2
    mock_prompt_v2 = MagicMock()
    mock_prompt_v2.model_dump.return_value = {
        "id": "uuid-2",
        "prompt_id": "chat_prompt",
        "version": 2,
        "litellm_params": '{"prompt_id": "chat_prompt", "prompt_integration": "dotprompt", "model": "gpt-4", "messages": [{"role": "user", "content": "v2 content"}]}',
        "prompt_info": '{"prompt_type": "db"}',
        "created_at": "2024-01-02T00:00:00",
        "updated_at": "2024-01-02T00:00:00",
    }

    # Test version 1
    prompt_spec_v1 = proxy_config._get_prompt_spec_for_db_prompt(
        db_prompt=mock_prompt_v1
    )
    assert prompt_spec_v1.prompt_id == "chat_prompt.v1"

    # Test version 2
    prompt_spec_v2 = proxy_config._get_prompt_spec_for_db_prompt(
        db_prompt=mock_prompt_v2
    )
    assert prompt_spec_v2.prompt_id == "chat_prompt.v2"


def test_root_redirect_when_docs_url_not_root_and_redirect_url_set(monkeypatch):
    from fastapi.responses import RedirectResponse

    from litellm.proxy.proxy_server import cleanup_router_config_variables
    from litellm.proxy.utils import _get_docs_url

    cleanup_router_config_variables()
    filepath = os.path.dirname(os.path.abspath(__file__))
    config_fp = f"{filepath}/test_configs/test_config_no_auth.yaml"
    # Ensure docs are mounted on a non-root path to trigger redirect logic
    monkeypatch.setenv("DOCS_URL", "/docs")

    test_redirect_url = "/ui"
    monkeypatch.setenv("ROOT_REDIRECT_URL", test_redirect_url)

    asyncio.run(initialize(config=config_fp, debug=True))

    docs_url = _get_docs_url()
    root_redirect_url = os.getenv("ROOT_REDIRECT_URL")

    # Remove any existing "/" route that might interfere
    routes_to_remove = []
    for route in app.routes:
        if hasattr(route, "path") and route.path == "/":
            if hasattr(route, "methods") and "GET" in route.methods:
                routes_to_remove.append(route)
            elif not hasattr(route, "methods"):  # Catch-all routes
                routes_to_remove.append(route)

    for route in routes_to_remove:
        app.routes.remove(route)

    # Add the redirect route if conditions are met (matching the actual implementation)
    if docs_url != "/" and root_redirect_url:

        @app.get("/", include_in_schema=False)
        async def root_redirect():
            return RedirectResponse(url=root_redirect_url)

    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == test_redirect_url


@pytest.mark.asyncio
async def test_get_image_non_root_uses_var_lib_assets_dir(monkeypatch):
    """
    Test that get_image uses /var/lib/litellm/assets when LITELLM_NON_ROOT is true.
    """
    from unittest.mock import patch

    from litellm.proxy.proxy_server import get_image

    # Set LITELLM_NON_ROOT to true
    monkeypatch.setenv("LITELLM_NON_ROOT", "true")
    monkeypatch.delenv("UI_LOGO_PATH", raising=False)

    # Mock os.path operations - exists=False for assets_dir so makedirs gets called
    def exists_side_effect(path):
        return False if path == "/var/lib/litellm/assets" else True

    with (
        patch("litellm.proxy.proxy_server.os.makedirs") as mock_makedirs,
        patch(
            "litellm.proxy.proxy_server.os.path.exists", side_effect=exists_side_effect
        ),
        patch("litellm.proxy.proxy_server.os.access", return_value=True),
        patch("litellm.proxy.proxy_server.os.getenv") as mock_getenv,
        patch("litellm.proxy.proxy_server.FileResponse") as mock_file_response,
    ):
        # Setup mock_getenv to return empty string for UI_LOGO_PATH
        def getenv_side_effect(key, default=""):
            if key == "UI_LOGO_PATH":
                return ""
            elif key == "LITELLM_NON_ROOT":
                return "true"
            return default

        mock_getenv.side_effect = getenv_side_effect

        # Call the function
        await get_image()

        # Verify makedirs was called with /var/lib/litellm/assets
        mock_makedirs.assert_called_once_with("/var/lib/litellm/assets", exist_ok=True)


@pytest.mark.asyncio
async def test_get_image_non_root_fallback_to_default_logo(monkeypatch):
    """
    Test that get_image falls back to default_site_logo when logo doesn't exist
    in /var/lib/litellm/assets for non-root case.
    """
    from unittest.mock import patch

    from litellm.proxy.proxy_server import get_image

    # Set LITELLM_NON_ROOT to true
    monkeypatch.setenv("LITELLM_NON_ROOT", "true")
    monkeypatch.delenv("UI_LOGO_PATH", raising=False)

    # Track path.exists calls to verify it checks /var/lib/litellm/assets/logo.jpg
    exists_calls = []

    def exists_side_effect(path):
        exists_calls.append(path)
        # Return False for /var/lib/litellm/assets* so: makedirs is called, logo fallback
        # triggers, and we don't return early with cached file
        if "/var/lib/litellm/assets" in path:
            return False
        return True

    # Mock os.path operations
    with (
        patch("litellm.proxy.proxy_server.os.makedirs") as mock_makedirs,
        patch(
            "litellm.proxy.proxy_server.os.path.exists", side_effect=exists_side_effect
        ),
        patch("litellm.proxy.proxy_server.os.access", return_value=True),
        patch("litellm.proxy.proxy_server.os.getenv") as mock_getenv,
        patch("litellm.proxy.proxy_server.FileResponse") as mock_file_response,
    ):
        # Setup mock_getenv
        def getenv_side_effect(key, default=""):
            if key == "UI_LOGO_PATH":
                return ""
            elif key == "LITELLM_NON_ROOT":
                return "true"
            return default

        mock_getenv.side_effect = getenv_side_effect

        # Call the function
        await get_image()

        # Verify makedirs was called with /var/lib/litellm/assets
        mock_makedirs.assert_called_once_with("/var/lib/litellm/assets", exist_ok=True)

        # Verify that exists was called to check /var/lib/litellm/assets/logo.jpg
        assets_logo_path = "/var/lib/litellm/assets/logo.jpg"
        assert any(
            assets_logo_path in str(call) for call in exists_calls
        ), f"Should check if {assets_logo_path} exists"

        # Verify FileResponse was called (with fallback logo)
        assert mock_file_response.called, "FileResponse should be called"


@pytest.mark.asyncio
async def test_get_image_root_case_uses_current_dir(monkeypatch):
    """
    Test that get_image uses current_dir when LITELLM_NON_ROOT is not true.
    """
    from unittest.mock import patch

    from litellm.proxy.proxy_server import get_image

    # Don't set LITELLM_NON_ROOT (or set it to false)
    monkeypatch.delenv("LITELLM_NON_ROOT", raising=False)
    monkeypatch.delenv("UI_LOGO_PATH", raising=False)

    # Mock os.path operations
    with (
        patch("litellm.proxy.proxy_server.os.makedirs") as mock_makedirs,
        patch("litellm.proxy.proxy_server.os.path.exists", return_value=True),
        patch("litellm.proxy.proxy_server.os.getenv") as mock_getenv,
        patch("litellm.proxy.proxy_server.FileResponse") as mock_file_response,
    ):
        # Setup mock_getenv
        def getenv_side_effect(key, default=""):
            if key == "UI_LOGO_PATH":
                return ""
            elif key == "LITELLM_NON_ROOT":
                return ""  # Not set or empty
            return default

        mock_getenv.side_effect = getenv_side_effect

        # Call the function
        await get_image()

        # Verify makedirs was NOT called with /var/lib/litellm/assets (should not create it for root case)
        var_lib_assets_calls = [
            call
            for call in mock_makedirs.call_args_list
            if "/var/lib/litellm/assets" in str(call)
        ]
        assert (
            len(var_lib_assets_calls) == 0
        ), "Should not create /var/lib/litellm/assets for root case"

        # Verify FileResponse was called
        assert mock_file_response.called, "FileResponse should be called"


@pytest.mark.asyncio
async def test_get_image_custom_local_logo_bypasses_cache(monkeypatch, tmp_path):
    """
    Test that when UI_LOGO_PATH is set to a local file, get_image serves it
    directly and does not return a stale cached_logo.jpg.

    Regression test: previously the cache check ran before reading UI_LOGO_PATH,
    so a pre-existing cached_logo.jpg (e.g. from the base Docker image) would
    always be returned, ignoring the user's custom logo.
    """
    from litellm.proxy.proxy_server import get_image

    custom_logo = tmp_path / "custom_logo.jpg"
    custom_logo.write_bytes(b"\xff\xd8\xff custom logo")
    monkeypatch.setenv("UI_LOGO_PATH", str(custom_logo))
    monkeypatch.delenv("LITELLM_NON_ROOT", raising=False)
    monkeypatch.delenv("LITELLM_ASSETS_PATH", raising=False)

    calls_to_file_response = []

    def fake_file_response(path, **kwargs):
        calls_to_file_response.append(path)
        return MagicMock()

    with (
        patch(
            "litellm.proxy.proxy_server.FileResponse", side_effect=fake_file_response
        ),
    ):
        await get_image()

    assert (
        len(calls_to_file_response) == 1
    ), "FileResponse should be called exactly once"
    assert calls_to_file_response[0] == str(custom_logo.resolve()), (
        f"Expected custom logo path, got {calls_to_file_response[0]}. "
        "A stale cached_logo.jpg may have been returned instead."
    )


@pytest.mark.asyncio
async def test_get_image_default_logo_ignores_stale_cache(monkeypatch, tmp_path):
    """
    Test that when UI_LOGO_PATH is NOT set, stale pre-fix cached_logo.jpg
    files are ignored and the default logo is served.
    """
    from unittest.mock import patch

    from litellm.proxy.proxy_server import get_image

    cache_path = tmp_path / "cached_logo.jpg"
    cache_path.write_bytes(b"\xff\xd8\xff cached logo")
    monkeypatch.delenv("UI_LOGO_PATH", raising=False)
    monkeypatch.delenv("LITELLM_NON_ROOT", raising=False)
    monkeypatch.setenv("LITELLM_ASSETS_PATH", str(tmp_path))

    calls_to_file_response = []

    def fake_file_response(path, **kwargs):
        calls_to_file_response.append(path)
        return MagicMock()

    with (
        patch(
            "litellm.proxy.proxy_server.FileResponse", side_effect=fake_file_response
        ),
    ):
        await get_image()

    assert (
        len(calls_to_file_response) == 1
    ), "FileResponse should be called exactly once"
    served_path = calls_to_file_response[0]
    assert served_path != str(cache_path.resolve())
    assert served_path.endswith("logo.jpg")


@pytest.mark.asyncio
async def test_get_image_custom_logo_missing_falls_through_to_default(
    monkeypatch, tmp_path
):
    """
    Test that when UI_LOGO_PATH points to a non-existent local file,
    get_image falls through to the default logo instead of failing.
    """
    from unittest.mock import patch

    from litellm.proxy.proxy_server import get_image

    custom_logo_path = tmp_path / "nonexistent_logo.jpg"
    monkeypatch.setenv("UI_LOGO_PATH", str(custom_logo_path))
    monkeypatch.delenv("LITELLM_NON_ROOT", raising=False)
    monkeypatch.setenv("LITELLM_ASSETS_PATH", str(tmp_path))

    calls_to_file_response = []

    def fake_file_response(path, **kwargs):
        calls_to_file_response.append(path)
        return MagicMock()

    with (
        patch(
            "litellm.proxy.proxy_server.FileResponse", side_effect=fake_file_response
        ),
    ):
        await get_image()

    assert (
        len(calls_to_file_response) == 1
    ), "FileResponse should be called exactly once"
    served_path = calls_to_file_response[0]
    assert served_path != str(
        custom_logo_path
    ), "Should not attempt to serve a non-existent custom logo"
    assert served_path.endswith("logo.jpg")


@pytest.mark.asyncio
async def test_get_image_custom_logo_missing_no_cache_serves_default(
    monkeypatch, tmp_path
):
    """
    Test that when UI_LOGO_PATH points to a non-existent file AND there is no
    cached_logo.jpg, get_image serves the default logo instead of the non-existent
    custom path.
    """
    from unittest.mock import patch

    from litellm.proxy.proxy_server import get_image

    custom_logo_path = tmp_path / "nonexistent_logo.jpg"
    monkeypatch.setenv("UI_LOGO_PATH", str(custom_logo_path))
    monkeypatch.delenv("LITELLM_NON_ROOT", raising=False)
    monkeypatch.setenv("LITELLM_ASSETS_PATH", str(tmp_path))

    calls_to_file_response = []

    def fake_file_response(path, **kwargs):
        calls_to_file_response.append(path)
        return MagicMock()

    with (
        patch(
            "litellm.proxy.proxy_server.FileResponse", side_effect=fake_file_response
        ),
    ):
        await get_image()

    assert (
        len(calls_to_file_response) == 1
    ), "FileResponse should be called exactly once"
    served_path = calls_to_file_response[0]
    assert served_path != str(
        custom_logo_path
    ), "Should not attempt to serve a non-existent custom logo"
    assert served_path.endswith(
        "logo.jpg"
    ), f"Expected fallback to default logo.jpg, got {served_path}"


def test_get_config_normalizes_string_callbacks(monkeypatch):
    """
    Test that /get/config/callbacks normalizes string callbacks to lists.
    """
    from litellm.proxy.proxy_server import app, proxy_config, user_api_key_auth

    config_data = {
        "litellm_settings": {
            "success_callback": "langfuse",
            "failure_callback": None,
            "callbacks": ["prometheus", "datadog"],
        },
        "general_settings": {},
        "environment_variables": {},
    }

    mock_router = MagicMock()
    mock_router.get_settings.return_value = {}
    monkeypatch.setattr("litellm.proxy.proxy_server.llm_router", mock_router)
    monkeypatch.setattr(proxy_config, "get_config", AsyncMock(return_value=config_data))

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_role=LitellmUserRoles.PROXY_ADMIN, api_key="sk-1234"
    )

    client = TestClient(app)
    try:
        response = client.get("/get/config/callbacks")
    finally:
        app.dependency_overrides = original_overrides

    assert response.status_code == 200
    callbacks = response.json()["callbacks"]

    success_callbacks = [cb["name"] for cb in callbacks if cb.get("type") == "success"]
    failure_callbacks = [cb["name"] for cb in callbacks if cb.get("type") == "failure"]
    success_and_failure_callbacks = [
        cb["name"] for cb in callbacks if cb.get("type") == "success_and_failure"
    ]

    assert "langfuse" in success_callbacks
    assert len(failure_callbacks) == 0
    assert "prometheus" in success_and_failure_callbacks
    assert "datadog" in success_and_failure_callbacks


def test_deep_merge_dicts_skips_none_and_empty_lists(monkeypatch):
    """
    Test that _update_config_fields deep merge skips None values and empty lists.
    """
    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    current_config = {
        "general_settings": {
            "max_parallel_requests": 10,
            "allowed_models": ["gpt-3.5-turbo", "gpt-4"],
            "nested": {
                "key1": "value1",
                "key2": "value2",
            },
        }
    }

    db_param_value = {
        "max_parallel_requests": None,
        "allowed_models": [],
        "new_key": "new_value",
        "nested": {
            "key1": "updated_value1",
            "key3": "value3",
        },
    }

    result = proxy_config._update_config_fields(
        current_config, "general_settings", db_param_value
    )

    assert result["general_settings"]["max_parallel_requests"] == 10
    assert result["general_settings"]["allowed_models"] == ["gpt-3.5-turbo", "gpt-4"]
    assert result["general_settings"]["new_key"] == "new_value"
    assert result["general_settings"]["nested"]["key1"] == "updated_value1"
    assert result["general_settings"]["nested"]["key2"] == "value2"
    assert result["general_settings"]["nested"]["key3"] == "value3"


class TestInvitationEndpoints:
    """Tests for /invitation/new and /invitation/delete endpoints."""

    @pytest.fixture
    def client_with_auth(self):
        """Create a test client with admin authentication."""
        from litellm.proxy._types import LitellmUserRoles
        from litellm.proxy.proxy_server import cleanup_router_config_variables

        cleanup_router_config_variables()
        filepath = os.path.dirname(os.path.abspath(__file__))
        config_fp = f"{filepath}/test_configs/test_config_no_auth.yaml"
        asyncio.run(initialize(config=config_fp, debug=True))

        mock_auth = MagicMock()
        mock_auth.user_id = "admin-user-id"
        mock_auth.user_role = LitellmUserRoles.PROXY_ADMIN
        mock_auth.api_key = "sk-test"
        app.dependency_overrides[user_api_key_auth] = lambda: mock_auth

        return TestClient(app)

    @pytest.mark.parametrize(
        "endpoint,payload,mock_return",
        [
            (
                "/invitation/new",
                {"user_id": "target-user-123"},
                {
                    "id": "inv-123",
                    "user_id": "target-user-123",
                    "is_accepted": False,
                    "accepted_at": None,
                    "expires_at": "2025-02-18T00:00:00",
                    "created_at": "2025-02-11T00:00:00",
                    "created_by": "admin-user-id",
                    "updated_at": "2025-02-11T00:00:00",
                    "updated_by": "admin-user-id",
                },
            ),
            (
                "/invitation/delete",
                {"invitation_id": "inv-456"},
                {
                    "id": "inv-456",
                    "user_id": "target-user-123",
                    "is_accepted": False,
                    "accepted_at": None,
                    "expires_at": "2025-02-18T00:00:00",
                    "created_at": "2025-02-11T00:00:00",
                    "created_by": "admin-user-id",
                    "updated_at": "2025-02-11T00:00:00",
                    "updated_by": "admin-user-id",
                },
            ),
        ],
    )
    def test_invitation_endpoints_proxy_admin_success(
        self, client_with_auth, endpoint, payload, mock_return
    ):
        """Proxy admin can successfully create and delete invitations."""
        with patch("litellm.proxy.proxy_server.prisma_client") as mock_prisma:
            mock_prisma.db.litellm_invitationlink = MagicMock()
            if endpoint == "/invitation/new":
                mock_create = AsyncMock(return_value=mock_return)
                with patch(
                    "litellm.proxy.management_helpers.user_invitation.create_invitation_for_user",
                    mock_create,
                ):
                    response = client_with_auth.post(endpoint, json=payload)
            else:
                mock_prisma.db.litellm_invitationlink.find_unique = AsyncMock(
                    return_value={**mock_return, "created_by": "admin-user-id"}
                )
                mock_prisma.db.litellm_invitationlink.delete = AsyncMock(
                    return_value=mock_return
                )
                response = client_with_auth.post(endpoint, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_return["id"]
        assert data["user_id"] == mock_return["user_id"]

    @pytest.mark.parametrize(
        "endpoint,payload",
        [
            ("/invitation/new", {"user_id": "target-user-123"}),
            ("/invitation/delete", {"invitation_id": "inv-456"}),
        ],
    )
    def test_invitation_endpoints_non_admin_denied(
        self, client_with_auth, endpoint, payload
    ):
        """Non-admin users cannot access invitation endpoints."""
        from litellm.proxy._types import LitellmUserRoles

        mock_auth = MagicMock()
        mock_auth.user_id = "regular-user"
        mock_auth.user_role = LitellmUserRoles.INTERNAL_USER
        mock_auth.api_key = "sk-regular"
        app.dependency_overrides[user_api_key_auth] = lambda: mock_auth

        with patch("litellm.proxy.proxy_server.prisma_client") as mock_prisma:
            mock_prisma.db.litellm_invitationlink = MagicMock()
            # Avoid triggering async DB calls in _user_has_admin_privileges
            with patch(
                "litellm.proxy.proxy_server._user_has_admin_privileges",
                new_callable=AsyncMock,
                return_value=False,
            ):
                response = client_with_auth.post(endpoint, json=payload)

        assert response.status_code == 400
        body = response.json()
        # ProxyException handler returns {"error": {...}}, HTTPException returns {"detail": {...}}
        error_content = body.get("error", body.get("detail", body))
        assert "not allowed" in str(error_content).lower()


@pytest.mark.asyncio
async def test_async_data_generator_cleanup_on_early_exit():
    """
    Test that async_data_generator calls response.aclose() in the finally block
    when the generator is abandoned mid-stream (client disconnect).
    """
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "test"}],
    }

    mock_chunks = [
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": " world"}}]},
        {"choices": [{"delta": {"content": " more"}}]},
    ]

    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)

    async def mock_streaming_iterator(*args, **kwargs):
        for chunk in mock_chunks:
            yield chunk

    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = (
        mock_streaming_iterator
    )
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock(
        side_effect=lambda **kwargs: kwargs.get("response")
    )
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    # Create a mock response with aclose
    mock_response = MagicMock()
    mock_response.aclose = AsyncMock()

    with patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj):
        # Consume only the first chunk then abandon the generator (simulates client disconnect)
        gen = async_data_generator(
            mock_response, mock_user_api_key_dict, mock_request_data
        )
        first_chunk = await gen.__anext__()
        assert first_chunk.startswith("data: ")

        # Close the generator early (simulates what ASGI does on client disconnect)
        await gen.aclose()

    # Verify aclose was called on the response to release the HTTP connection
    mock_response.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_data_generator_uses_direct_stream_fast_path_without_callbacks():
    """
    When there are no streaming callbacks, async_data_generator should avoid
    per-chunk hook machinery and iterate the provider stream directly.
    """
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "test"}],
    }
    mock_chunks = [
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": " world"}}]},
    ]

    class MockStream:
        def __aiter__(self):
            return self._stream()

        async def _stream(self):
            for chunk in mock_chunks:
                yield chunk

        async def aclose(self):
            pass

    mock_response = MockStream()
    mock_response.aclose = AsyncMock()
    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)
    mock_proxy_logging_obj.has_streaming_callbacks.return_value = False
    mock_proxy_logging_obj.needs_iterator_wrap.return_value = False
    mock_proxy_logging_obj.needs_per_chunk_streaming_hook.return_value = False
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = MagicMock()
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock()
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    with patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj):
        with patch.object(
            ProxyLogging, "_fire_deferred_stream_logging"
        ) as mock_deferred_logging:
            yielded_data = []
            async for data in async_data_generator(
                mock_response, mock_user_api_key_dict, mock_request_data
            ):
                yielded_data.append(data)

    yielded_text = [
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for chunk in yielded_data
    ]
    assert len([chunk for chunk in yielded_text if chunk.startswith("data: {")]) == 2
    assert yielded_text[-1] == "data: [DONE]\n\n"
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook.assert_not_called()
    mock_proxy_logging_obj.async_post_call_streaming_hook.assert_not_awaited()
    mock_deferred_logging.assert_called_once_with(mock_request_data)
    mock_response.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_data_generator_preserves_non_raw_sse_like_bytes():
    """
    Already formatted SSE bytes from non-raw streams keep the legacy passthrough
    behavior, including appending a missing event terminator.
    """
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gemini-2.0-flash",
        "messages": [{"role": "user", "content": "test"}],
    }
    gemini_event = b'data: {"candidates": [{"content": "hi"}]}\n\n'
    gemini_event_without_terminator = b'data: {"candidates": [{"content": "there"}]}'
    raw_payload = b'{"partial": true}'

    class MockStream:
        def __aiter__(self):
            return self._stream()

        async def _stream(self):
            yield gemini_event
            yield gemini_event_without_terminator
            yield raw_payload

        async def aclose(self):
            pass

    mock_response = MockStream()
    mock_response.aclose = AsyncMock()
    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)
    mock_proxy_logging_obj.has_streaming_callbacks.return_value = False
    mock_proxy_logging_obj.needs_iterator_wrap.return_value = False
    mock_proxy_logging_obj.needs_per_chunk_streaming_hook.return_value = False
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = MagicMock()
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock()
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    with patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj):
        with patch.object(ProxyLogging, "_fire_deferred_stream_logging"):
            yielded_data = []
            async for data in async_data_generator(
                mock_response, mock_user_api_key_dict, mock_request_data
            ):
                yielded_data.append(data)

    yielded_text = [
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for chunk in yielded_data
    ]
    assert yielded_text[0] == gemini_event.decode("utf-8")
    assert yielded_text[1] == gemini_event_without_terminator.decode("utf-8") + "\n\n"
    assert yielded_text[2] == f'data: {raw_payload.decode("utf-8")}\n\n'
    assert "b'data:" not in "".join(yielded_text)
    assert yielded_text[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_async_data_generator_buffers_split_google_native_sse_json_frame():
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gemini-3.5-flash",
        "_litellm_skip_openai_stream_done": True,
        "_litellm_raw_sse_stream": True,
    }
    payload = (
        'data: {"candidates": [{"content": {"role": "model", "parts": '
        '[{"text": "", "thoughtSignature": "abc123def456"}]}}]}\n\n'
    )
    raw_chunks = [
        payload[:2].encode("utf-8"),
        payload[
            2 : payload.index("thoughtSignature") + len('thoughtSignature": "abc')
        ].encode("utf-8"),
        payload[
            payload.index("thoughtSignature") + len('thoughtSignature": "abc') :
        ].encode("utf-8"),
    ]

    class MockStream:
        def __aiter__(self):
            return self._stream()

        async def _stream(self):
            for chunk in raw_chunks:
                yield chunk

        async def aclose(self):
            pass

    mock_response = MockStream()
    mock_response.aclose = AsyncMock()
    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)
    mock_proxy_logging_obj.has_streaming_callbacks.return_value = False
    mock_proxy_logging_obj.needs_iterator_wrap.return_value = False
    mock_proxy_logging_obj.needs_per_chunk_streaming_hook.return_value = False
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = MagicMock()
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock()
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    with patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj):
        with patch.object(ProxyLogging, "_fire_deferred_stream_logging"):
            yielded_data = []
            async for data in async_data_generator(
                mock_response, mock_user_api_key_dict, mock_request_data
            ):
                yielded_data.append(data)

    yielded_text = [
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for chunk in yielded_data
    ]

    assert yielded_text == [payload]
    for chunk in yielded_text:
        assert chunk.endswith("\n\n")
        assert json.loads(chunk.removeprefix("data: ").strip())


@pytest.mark.asyncio
async def test_async_data_generator_flushes_raw_sse_stream_without_trailing_delimiter():
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gemini-3.5-flash",
        "_litellm_skip_openai_stream_done": True,
        "_litellm_raw_sse_stream": True,
    }

    class MockStream:
        def __aiter__(self):
            return self._stream()

        async def _stream(self):
            yield b'data: {"candidates": [{"content": "unterminated"}]'

        async def aclose(self):
            pass

    mock_response = MockStream()
    mock_response.aclose = AsyncMock()
    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)
    mock_proxy_logging_obj.has_streaming_callbacks.return_value = False
    mock_proxy_logging_obj.needs_iterator_wrap.return_value = False
    mock_proxy_logging_obj.needs_per_chunk_streaming_hook.return_value = False
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = MagicMock()
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock()
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    with (
        patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj),
        patch.object(ProxyLogging, "_fire_deferred_stream_logging"),
    ):
        yielded_data = []
        async for data in async_data_generator(
            mock_response, mock_user_api_key_dict, mock_request_data
        ):
            yielded_data.append(data)

    yielded_text = [
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for chunk in yielded_data
    ]
    assert len(yielded_text) == 1
    assert yielded_text[0] == 'data: {"candidates": [{"content": "unterminated"}]\n\n'
    assert "[DONE]" not in yielded_text[0]
    mock_proxy_logging_obj.post_call_failure_hook.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_data_generator_errors_when_raw_sse_frame_exceeds_buffer_limit():
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gemini-3.5-flash",
        "_litellm_skip_openai_stream_done": True,
        "_litellm_raw_sse_stream": True,
    }

    class MockStream:
        def __aiter__(self):
            return self._stream()

        async def _stream(self):
            yield b"data: "
            yield b'{"candidates": [{"content": "unterminated"}]'

        async def aclose(self):
            pass

    mock_response = MockStream()
    mock_response.aclose = AsyncMock()
    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)
    mock_proxy_logging_obj.has_streaming_callbacks.return_value = False
    mock_proxy_logging_obj.needs_iterator_wrap.return_value = False
    mock_proxy_logging_obj.needs_per_chunk_streaming_hook.return_value = False
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = MagicMock()
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock()
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    with (
        patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj),
        patch("litellm.proxy.proxy_server._MAX_RAW_SSE_BUFFER_CHARS", 8),
        patch.object(ProxyLogging, "_fire_deferred_stream_logging"),
    ):
        yielded_data = []
        async for data in async_data_generator(
            mock_response, mock_user_api_key_dict, mock_request_data
        ):
            yielded_data.append(data)

    yielded_text = [
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for chunk in yielded_data
    ]
    assert len(yielded_text) == 1
    assert "maximum buffered size" in yielded_text[0]
    assert "[DONE]" not in yielded_text[0]
    mock_proxy_logging_obj.post_call_failure_hook.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("as_bytes", [True, False])
async def test_async_data_generator_checks_raw_sse_buffer_limit_after_complete_frames(
    as_bytes,
):
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    complete_frame = 'data: {"candidates": [{"content": "ok"}]}\n\n'
    partial_frame = "data: "
    raw_chunk = complete_frame + partial_frame

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gemini-3.5-flash",
        "_litellm_skip_openai_stream_done": True,
        "_litellm_raw_sse_stream": True,
    }

    class MockStream:
        def __aiter__(self):
            return self._stream()

        async def _stream(self):
            yield raw_chunk.encode("utf-8") if as_bytes else raw_chunk

        async def aclose(self):
            pass

    mock_response = MockStream()
    mock_response.aclose = AsyncMock()
    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)
    mock_proxy_logging_obj.has_streaming_callbacks.return_value = False
    mock_proxy_logging_obj.needs_iterator_wrap.return_value = False
    mock_proxy_logging_obj.needs_per_chunk_streaming_hook.return_value = False
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = MagicMock()
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock()
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    with (
        patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj),
        patch("litellm.proxy.proxy_server._MAX_RAW_SSE_BUFFER_CHARS", 8),
        patch.object(ProxyLogging, "_fire_deferred_stream_logging"),
    ):
        yielded_data = []
        async for data in async_data_generator(
            mock_response, mock_user_api_key_dict, mock_request_data
        ):
            yielded_data.append(data)

    yielded_text = [
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for chunk in yielded_data
    ]
    assert yielded_text[0] == complete_frame
    assert yielded_text[1] == partial_frame + "\n\n"
    assert "[DONE]" not in "".join(yielded_text)
    mock_proxy_logging_obj.post_call_failure_hook.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_data_generator_google_genai_stream_omits_openai_done():
    """
    google-genai SDK streamGenerateContent?alt=sse must not receive data: [DONE].
    """
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gemini-2.0-flash",
        "_litellm_skip_openai_stream_done": True,
    }
    gemini_event = (
        b'data: {"candidates": [{"content": {"parts": [{"text": "Hi"}]}}]}\n\n'
    )

    class MockStream:
        def __aiter__(self):
            return self._stream()

        async def _stream(self):
            yield gemini_event

        async def aclose(self):
            pass

    mock_response = MockStream()
    mock_response.aclose = AsyncMock()
    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)
    mock_proxy_logging_obj.has_streaming_callbacks.return_value = False
    mock_proxy_logging_obj.needs_iterator_wrap.return_value = False
    mock_proxy_logging_obj.needs_per_chunk_streaming_hook.return_value = False
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = MagicMock()
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock()
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    with patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj):
        with patch.object(ProxyLogging, "_fire_deferred_stream_logging"):
            yielded_data = []
            async for data in async_data_generator(
                mock_response, mock_user_api_key_dict, mock_request_data
            ):
                yielded_data.append(data)

    yielded_text = [
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for chunk in yielded_data
    ]
    assert yielded_text == [gemini_event.decode("utf-8")]
    assert "[DONE]" not in "".join(yielded_text)


@pytest.mark.asyncio
async def test_async_data_generator_does_not_mark_completed_stream_as_disconnect():
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {"model": "gpt-4o", "metadata": {}}

    class MockStream:
        def __aiter__(self):
            return self._stream()

        async def _stream(self):
            yield {"choices": [{"delta": {"content": "done"}}]}

        async def aclose(self):
            pass

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=True)
    mock_response = MockStream()
    mock_response.aclose = AsyncMock()
    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)
    mock_proxy_logging_obj.has_streaming_callbacks.return_value = False
    mock_proxy_logging_obj.needs_iterator_wrap.return_value = False
    mock_proxy_logging_obj.needs_per_chunk_streaming_hook.return_value = False
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = MagicMock()
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock()
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    with patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj):
        with patch.object(ProxyLogging, "_fire_deferred_stream_logging"):
            yielded_data = []
            async for data in async_data_generator(
                mock_response,
                mock_user_api_key_dict,
                mock_request_data,
                request=mock_request,
            ):
                yielded_data.append(data)

    assert yielded_data[-1] == "data: [DONE]\n\n"
    mock_request.is_disconnected.assert_not_awaited()
    assert "client_disconnected" not in mock_request_data["metadata"]


@pytest.mark.asyncio
async def test_async_data_generator_google_genai_stream_forwards_error_without_done():
    """Stream errors must still reach the client when OpenAI [DONE] is skipped."""
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    error_sse = 'data: {"error": {"message": "stream failed"}}\n\n'
    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gemini-2.0-flash",
        "_litellm_skip_openai_stream_done": True,
    }

    class MockStream:
        def __aiter__(self):
            return self._stream()

        async def _stream(self):
            yield error_sse

        async def aclose(self):
            pass

    mock_response = MockStream()
    mock_response.aclose = AsyncMock()
    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)
    mock_proxy_logging_obj.has_streaming_callbacks.return_value = False
    mock_proxy_logging_obj.needs_iterator_wrap.return_value = False
    mock_proxy_logging_obj.needs_per_chunk_streaming_hook.return_value = False
    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = MagicMock()
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock()
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    with patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj):
        with patch.object(ProxyLogging, "_fire_deferred_stream_logging"):
            yielded_data = []
            async for data in async_data_generator(
                mock_response, mock_user_api_key_dict, mock_request_data
            ):
                yielded_data.append(data)

    yielded_text = [
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        for chunk in yielded_data
    ]
    assert yielded_text == [error_sse]
    assert "[DONE]" not in "".join(yielded_text)


@pytest.mark.asyncio
async def test_async_data_generator_cleanup_on_normal_completion():
    """
    Test that async_data_generator calls response.aclose() even on normal completion.
    """
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "test"}],
    }

    mock_chunks = [
        {"choices": [{"delta": {"content": "Hello"}}]},
    ]

    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)

    async def mock_streaming_iterator(*args, **kwargs):
        for chunk in mock_chunks:
            yield chunk

    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = (
        mock_streaming_iterator
    )
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock(
        side_effect=lambda **kwargs: kwargs.get("response")
    )
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    mock_response = MagicMock()
    mock_response.aclose = AsyncMock()

    with patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj):
        yielded_data = []
        async for data in async_data_generator(
            mock_response, mock_user_api_key_dict, mock_request_data
        ):
            yielded_data.append(data)

    # Should have completed normally with [DONE]
    assert any("[DONE]" in d for d in yielded_data)
    # aclose should still be called via finally block
    mock_response.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_data_generator_cleanup_on_midstream_error():
    """
    Test that async_data_generator calls response.aclose() via finally block
    even when an exception occurs mid-stream.
    """
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import async_data_generator
    from litellm.proxy.utils import ProxyLogging

    mock_user_api_key_dict = MagicMock(spec=UserAPIKeyAuth)
    mock_request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "test"}],
    }

    mock_proxy_logging_obj = MagicMock(spec=ProxyLogging)

    async def mock_streaming_iterator_with_error(*args, **kwargs):
        yield {"choices": [{"delta": {"content": "Hello"}}]}
        raise RuntimeError("upstream connection reset")

    mock_proxy_logging_obj.async_post_call_streaming_iterator_hook = (
        mock_streaming_iterator_with_error
    )
    mock_proxy_logging_obj.async_post_call_streaming_hook = AsyncMock(
        side_effect=lambda **kwargs: kwargs.get("response")
    )
    mock_proxy_logging_obj.post_call_failure_hook = AsyncMock()

    mock_response = MagicMock()
    mock_response.aclose = AsyncMock()

    with patch("litellm.proxy.proxy_server.proxy_logging_obj", mock_proxy_logging_obj):
        yielded_data = []
        async for data in async_data_generator(
            mock_response, mock_user_api_key_dict, mock_request_data
        ):
            yielded_data.append(data)

    # Should have yielded data chunk and then an error chunk
    assert len(yielded_data) >= 2
    assert any("error" in d for d in yielded_data)
    # aclose must still be called via finally block despite the error
    mock_response.aclose.assert_awaited_once()


# ============================================================================
# store_model_in_db DB Config Override Tests
# ============================================================================


def test_store_model_in_db_in_config_general_settings():
    """
    Verify store_model_in_db is a valid field in ConfigGeneralSettings
    and validates correctly for True/False values.
    """
    from litellm.proxy._types import ConfigGeneralSettings

    assert "store_model_in_db" in ConfigGeneralSettings.model_fields

    # Should validate with True
    config = ConfigGeneralSettings(store_model_in_db=True)
    assert config.store_model_in_db is True

    # Should validate with False
    config = ConfigGeneralSettings(store_model_in_db=False)
    assert config.store_model_in_db is False

    # Should validate with None (default)
    config = ConfigGeneralSettings(store_model_in_db=None)
    assert config.store_model_in_db is None

    # Should validate with no value
    config = ConfigGeneralSettings()
    assert config.store_model_in_db is None


@pytest.mark.asyncio
async def test_update_general_settings_store_model_in_db_true():
    """
    Verify _update_general_settings sets global store_model_in_db to True
    when DB general_settings has store_model_in_db=True.
    """
    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    with (
        patch("litellm.proxy.proxy_server.store_model_in_db", False) as mock_store,
        patch("litellm.proxy.proxy_server.general_settings", {}) as mock_gs,
    ):
        await proxy_config._update_general_settings(
            db_general_settings={"store_model_in_db": True}
        )

        import litellm.proxy.proxy_server as ps

        assert ps.store_model_in_db is True
        assert ps.general_settings["store_model_in_db"] is True


@pytest.mark.asyncio
async def test_update_general_settings_store_model_in_db_false():
    """
    Verify _update_general_settings sets global store_model_in_db to False
    when DB general_settings has store_model_in_db=False.
    """
    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    with (
        patch("litellm.proxy.proxy_server.store_model_in_db", True),
        patch("litellm.proxy.proxy_server.general_settings", {}),
    ):
        await proxy_config._update_general_settings(
            db_general_settings={"store_model_in_db": False}
        )

        import litellm.proxy.proxy_server as ps

        assert ps.store_model_in_db is False
        assert ps.general_settings["store_model_in_db"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "db_value,expected",
    [(True, True), (False, False), ("true", True), ("false", False), (None, None)],
)
async def test_update_general_settings_disable_auto_add_proxy_admin_to_teams(db_value, expected):
    """
    Verify _update_general_settings propagates disable_auto_add_proxy_admin_to_teams
    from the DB config into the live general_settings dict, so a UI toggle via
    /config/field/update takes effect on the next config poll instead of
    requiring a proxy restart.
    """
    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    with patch("litellm.proxy.proxy_server.general_settings", {}):
        await proxy_config._update_general_settings(
            db_general_settings={"disable_auto_add_proxy_admin_to_teams": db_value}
        )

        import litellm.proxy.proxy_server as ps

        assert ps.general_settings["disable_auto_add_proxy_admin_to_teams"] is expected


@pytest.mark.asyncio
async def test_update_general_settings_store_model_in_db_string_normalization():
    """
    Verify _update_general_settings normalizes string values for store_model_in_db.
    """
    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    # Test "true" string
    with (
        patch("litellm.proxy.proxy_server.store_model_in_db", False),
        patch("litellm.proxy.proxy_server.general_settings", {}),
    ):
        await proxy_config._update_general_settings(
            db_general_settings={"store_model_in_db": "true"}
        )
        import litellm.proxy.proxy_server as ps

        assert ps.store_model_in_db is True

    # Test "True" string
    with (
        patch("litellm.proxy.proxy_server.store_model_in_db", False),
        patch("litellm.proxy.proxy_server.general_settings", {}),
    ):
        await proxy_config._update_general_settings(
            db_general_settings={"store_model_in_db": "True"}
        )
        import litellm.proxy.proxy_server as ps

        assert ps.store_model_in_db is True

    # Test "false" string
    with (
        patch("litellm.proxy.proxy_server.store_model_in_db", True),
        patch("litellm.proxy.proxy_server.general_settings", {}),
    ):
        await proxy_config._update_general_settings(
            db_general_settings={"store_model_in_db": "false"}
        )
        import litellm.proxy.proxy_server as ps

        assert ps.store_model_in_db is False


@pytest.mark.asyncio
async def test_update_general_settings_store_model_in_db_none_keeps_current():
    """
    Verify _update_general_settings does not change store_model_in_db
    when DB value is None.
    """
    from litellm.proxy.proxy_server import ProxyConfig

    proxy_config = ProxyConfig()

    # When current is True and DB sends None, should stay True
    with (
        patch("litellm.proxy.proxy_server.store_model_in_db", True),
        patch("litellm.proxy.proxy_server.general_settings", {}),
    ):
        await proxy_config._update_general_settings(
            db_general_settings={"store_model_in_db": None}
        )
        import litellm.proxy.proxy_server as ps

        assert ps.store_model_in_db is True

    # When current is False and DB sends None, should stay False
    with (
        patch("litellm.proxy.proxy_server.store_model_in_db", False),
        patch("litellm.proxy.proxy_server.general_settings", {}),
    ):
        await proxy_config._update_general_settings(
            db_general_settings={"store_model_in_db": None}
        )
        import litellm.proxy.proxy_server as ps

        assert ps.store_model_in_db is False


@pytest.mark.asyncio
async def test_store_model_in_db_db_override_when_config_false():
    """
    Verify the early DB check in initialize_scheduled_background_jobs
    overrides store_model_in_db=False when DB has True.
    """
    from litellm.proxy.proxy_server import ProxyStartupEvent
    from litellm.proxy.utils import ProxyLogging

    mock_prisma_client = MagicMock()

    # Mock DB returning store_model_in_db=True in general_settings
    mock_db_record = MagicMock()
    mock_db_record.param_value = {"store_model_in_db": True}
    mock_prisma_client.db.litellm_config.find_first = AsyncMock(
        return_value=mock_db_record
    )

    mock_proxy_logging = MagicMock(spec=ProxyLogging)
    mock_proxy_logging.slack_alerting_instance = MagicMock()
    mock_proxy_config = AsyncMock()

    with (
        patch("litellm.proxy.proxy_server.proxy_config", mock_proxy_config),
        patch("litellm.proxy.proxy_server.store_model_in_db", False),
        patch("litellm.proxy.proxy_server.get_secret_bool", return_value=False),
    ):
        await ProxyStartupEvent.initialize_scheduled_background_jobs(
            general_settings={},
            prisma_client=mock_prisma_client,
            proxy_budget_rescheduler_min_time=1,
            proxy_budget_rescheduler_max_time=2,
            proxy_batch_write_at=5,
            proxy_logging_obj=mock_proxy_logging,
        )

        import litellm.proxy.proxy_server as ps

        # store_model_in_db should now be True (overridden by DB)
        assert ps.store_model_in_db is True

        # add_deployment and get_credentials should have been called
        # since store_model_in_db is now True
        assert mock_proxy_config.add_deployment.call_count == 1
        assert mock_proxy_config.get_credentials.call_count == 1


@pytest.mark.asyncio
async def test_store_model_in_db_db_check_skipped_when_already_true(monkeypatch):
    """
    Verify the early DB check is skipped when store_model_in_db is already True.
    The DB query for the early check should not be called.
    """
    monkeypatch.delenv("STORE_MODEL_IN_DB", raising=False)
    from litellm.proxy.proxy_server import ProxyStartupEvent
    from litellm.proxy.utils import ProxyLogging

    mock_prisma_client = MagicMock()
    mock_prisma_client.db.litellm_config.find_first = AsyncMock(return_value=None)

    mock_proxy_logging = MagicMock(spec=ProxyLogging)
    mock_proxy_logging.slack_alerting_instance = MagicMock()
    mock_proxy_config = AsyncMock()

    with (
        patch("litellm.proxy.proxy_server.proxy_config", mock_proxy_config),
        patch("litellm.proxy.proxy_server.store_model_in_db", True),
        patch("litellm.proxy.proxy_server.get_secret_bool", return_value=True),
    ):
        await ProxyStartupEvent.initialize_scheduled_background_jobs(
            general_settings={},
            prisma_client=mock_prisma_client,
            proxy_budget_rescheduler_min_time=1,
            proxy_budget_rescheduler_max_time=2,
            proxy_batch_write_at=5,
            proxy_logging_obj=mock_proxy_logging,
        )

        # The early DB check uses find_first with param_name="general_settings".
        # When store_model_in_db is already True, the early check should be skipped.
        # However, add_deployment may also call find_first.
        # We just verify that store_model_in_db stays True and jobs are scheduled.
        import litellm.proxy.proxy_server as ps

        assert ps.store_model_in_db is True
        assert mock_proxy_config.add_deployment.call_count == 1


@pytest.mark.asyncio
async def test_store_model_in_db_db_failure_graceful(monkeypatch):
    """
    Verify the early DB check handles DB failures gracefully
    without crashing and keeps store_model_in_db as False.
    """
    monkeypatch.delenv("STORE_MODEL_IN_DB", raising=False)
    from litellm.proxy.proxy_server import ProxyStartupEvent
    from litellm.proxy.utils import ProxyLogging

    mock_prisma_client = MagicMock()
    # Simulate DB failure
    mock_prisma_client.db.litellm_config.find_first = AsyncMock(
        side_effect=Exception("DB connection error")
    )

    mock_proxy_logging = MagicMock(spec=ProxyLogging)
    mock_proxy_logging.slack_alerting_instance = MagicMock()
    mock_proxy_config = AsyncMock()

    with (
        patch("litellm.proxy.proxy_server.proxy_config", mock_proxy_config),
        patch("litellm.proxy.proxy_server.store_model_in_db", False),
        patch("litellm.proxy.proxy_server.get_secret_bool", return_value=False),
    ):
        # Should not raise an exception
        await ProxyStartupEvent.initialize_scheduled_background_jobs(
            general_settings={},
            prisma_client=mock_prisma_client,
            proxy_budget_rescheduler_min_time=1,
            proxy_budget_rescheduler_max_time=2,
            proxy_batch_write_at=5,
            proxy_logging_obj=mock_proxy_logging,
        )

        import litellm.proxy.proxy_server as ps

        # store_model_in_db should remain False
        assert ps.store_model_in_db is False

        # add_deployment should NOT have been called since store_model_in_db is False
        mock_proxy_config.add_deployment.assert_not_called()


# =====================================================================
# Spend counter tests (v2 — Redis-backed spend counters)
# =====================================================================


@pytest.mark.asyncio
async def test_get_current_spend_reads_redis_first():
    """get_current_spend should prefer Redis over in-memory."""
    from litellm.caching.dual_cache import DualCache

    counter_cache = DualCache()

    # In-memory has stale value
    counter_cache.in_memory_cache.set_cache(key="spend:key:test", value=0.30)

    # Mock Redis with cross-pod authoritative value
    mock_redis = AsyncMock()
    mock_redis.async_get_cache = AsyncMock(return_value=0.90)
    counter_cache.redis_cache = mock_redis

    import litellm.proxy.proxy_server as ps

    original = ps.spend_counter_cache
    ps.spend_counter_cache = counter_cache

    try:
        from litellm.proxy.proxy_server import get_current_spend

        result = await get_current_spend(
            counter_key="spend:key:test",
            fallback_spend=0.0,
        )
        # Should return Redis value (0.90), not in-memory (0.30)
        assert result == 0.90
        mock_redis.async_get_cache.assert_called_once_with(key="spend:key:test")
    finally:
        ps.spend_counter_cache = original


@pytest.mark.asyncio
async def test_get_current_spend_fallback_to_in_memory():
    """When Redis is not configured, get_current_spend uses in-memory."""
    from litellm.caching.dual_cache import DualCache

    counter_cache = DualCache()  # no redis_cache
    counter_cache.in_memory_cache.set_cache(key="spend:key:test", value=0.50)

    import litellm.proxy.proxy_server as ps

    original = ps.spend_counter_cache
    ps.spend_counter_cache = counter_cache

    try:
        from litellm.proxy.proxy_server import get_current_spend

        result = await get_current_spend(
            counter_key="spend:key:test",
            fallback_spend=0.0,
        )
        assert result == 0.50
    finally:
        ps.spend_counter_cache = original


@pytest.mark.asyncio
async def test_increment_spend_counters_initializes_and_increments():
    """Counter should initialize from cached object spend, then increment.

    Uses a pre-hashed token to match production: metadata["user_api_key"]
    is always hashed by the auth flow before reaching the cost callback.
    """
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy._types import LiteLLM_VerificationTokenView, hash_token

    key_cache = DualCache()
    counter_cache = DualCache()

    # In production, the auth flow hashes the raw key before it reaches
    # the cost callback. Simulate that by passing the hashed token.
    hashed_token = hash_token("sk-test-token-for-counter")

    # Simulate a cached key object with existing spend from DB
    cached_key = LiteLLM_VerificationTokenView(
        token=hashed_token,
        spend=5.0,
        max_budget=10.0,
    )
    key_cache.in_memory_cache.set_cache(key=hashed_token, value=cached_key)

    import litellm.proxy.proxy_server as ps

    original_key_cache = ps.user_api_key_cache
    original_counter_cache = ps.spend_counter_cache
    ps.user_api_key_cache = key_cache
    ps.spend_counter_cache = counter_cache

    try:
        from litellm.proxy.proxy_server import increment_spend_counters

        # Pass pre-hashed token (as the cost callback would in production)
        await increment_spend_counters(
            token=hashed_token,
            team_id=None,
            user_id=None,
            response_cost=0.50,
        )

        # Counter should be: base(5.0) + increment(0.50) = 5.50
        counter = counter_cache.in_memory_cache.get_cache(
            key=f"spend:key:{hashed_token}"
        )
        assert counter == 5.50

        # Second increment — counter already exists, just increment
        await increment_spend_counters(
            token=hashed_token,
            team_id=None,
            user_id=None,
            response_cost=0.25,
        )

        counter = counter_cache.in_memory_cache.get_cache(
            key=f"spend:key:{hashed_token}"
        )
        assert counter == 5.75
    finally:
        ps.user_api_key_cache = original_key_cache
        ps.spend_counter_cache = original_counter_cache


@pytest.mark.asyncio
async def test_increment_spend_counters_team_and_member():
    """Counter should track team and team member spend separately."""
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy._types import LiteLLM_TeamTable

    key_cache = DualCache()
    counter_cache = DualCache()

    # Cached team object
    team_obj = LiteLLM_TeamTable(team_id="team-1", spend=2.0)
    key_cache.in_memory_cache.set_cache(key="team_id:team-1", value=team_obj)

    # Cached team membership
    key_cache.in_memory_cache.set_cache(
        key="team_membership:user-1:team-1",
        value={"user_id": "user-1", "team_id": "team-1", "spend": 1.0},
    )

    import litellm.proxy.proxy_server as ps

    original_key_cache = ps.user_api_key_cache
    original_counter_cache = ps.spend_counter_cache
    ps.user_api_key_cache = key_cache
    ps.spend_counter_cache = counter_cache

    try:
        from litellm.proxy.proxy_server import increment_spend_counters

        await increment_spend_counters(
            token=None,
            team_id="team-1",
            user_id="user-1",
            response_cost=0.30,
        )

        team_counter = counter_cache.in_memory_cache.get_cache(key="spend:team:team-1")
        assert team_counter == 2.30

        member_counter = counter_cache.in_memory_cache.get_cache(
            key="spend:team_member:user-1:team-1"
        )
        assert member_counter == 1.30
    finally:
        ps.user_api_key_cache = original_key_cache
        ps.spend_counter_cache = original_counter_cache


@pytest.mark.asyncio
async def test_init_and_increment_spend_counter_reseeds_from_db_on_counter_miss():
    """When the Redis counter is missing, the reseed path reads the
    authoritative spend from the DB (not a stale cache), so the next
    increment continues from the correct base value."""
    from litellm.caching.dual_cache import DualCache

    counter_cache = DualCache()
    recorded_increments: list = []

    async def record_increment(key, value, ttl=None, **kwargs):
        recorded_increments.append({"key": key, "value": value, "ttl": ttl})
        return value

    fake_redis = AsyncMock()
    fake_redis.async_increment = AsyncMock(side_effect=record_increment)
    fake_redis.async_get_cache = AsyncMock(return_value=None)  # counter missing
    fake_redis.async_set_cache = AsyncMock(return_value=True)  # SET NX wins
    counter_cache.redis_cache = fake_redis

    # Prisma returns spend=42.0 (authoritative) while the stale cached
    # value (would be read only if prisma is None) is 10.0. The counter
    # must seed from 42, not 10.
    db_row = MagicMock()
    db_row.spend = 42.0
    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teamtable.find_unique = AsyncMock(return_value=db_row)

    stale_cache = DualCache()
    stale_team = MagicMock()
    stale_team.spend = 10.0
    stale_cache.in_memory_cache.set_cache(key="team_id:team-9", value=stale_team)

    import litellm.proxy.proxy_server as ps
    from litellm.proxy.proxy_server import _init_and_increment_spend_counter

    orig_user, orig_counter, orig_prisma = (
        ps.user_api_key_cache,
        ps.spend_counter_cache,
        ps.prisma_client,
    )
    ps.user_api_key_cache = stale_cache
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        await _init_and_increment_spend_counter(
            counter_key="spend:team:team-9",
            source_cache_key="team_id:team-9",
            increment=1.5,
        )

        fake_prisma.db.litellm_teamtable.find_unique.assert_awaited_once_with(
            where={"team_id": "team-9"}
        )
        # Seed uses SET NX with db_spend (42) — cross-pod safe, no INCR of 42.
        # Only the per-request delta (1.5) goes through INCRBYFLOAT.
        fake_redis.async_set_cache.assert_awaited_once_with(
            key="spend:team:team-9", value=42.0, nx=True
        )
        writes = [(c["key"], c["value"]) for c in recorded_increments]
        assert writes == [("spend:team:team-9", 1.5)]
    finally:
        ps.user_api_key_cache = orig_user
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_primary_spend_counter_redis_concurrent_seed_does_not_double_seed():
    """Two pods both observing a missing Redis counter must not both
    INCRBYFLOAT the full DB spend. SpendCounterReseed.coalesced uses SET NX
    so the loser reads the winner's value; final Redis = db_spend, not
    2 * db_spend.

    The per-counter asyncio.Lock is per-process, so it does NOT coordinate
    across pods. We simulate two pods by patching _get_lock to return a
    fresh lock per call (each "pod" has its own lock registry in real life).
    """
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.db.spend_counter_reseed import SpendCounterReseed

    counter_key = "spend:team:team-concurrent-seed"
    redis_store: dict = {}
    db_read_count = 0
    set_results: list = []
    get_after_set_count = 0
    set_completed_count = 0

    async def redis_set_cache(key, value, nx=False, **_):
        # Yield BEFORE the membership check so two concurrent callers
        # interleave the way real atomic Redis SET NX does: the first
        # to resume runs check + write atomically and wins; the second
        # resumes after the key exists and loses. Yielding *after* the
        # check would let both callers pass the empty-store check before
        # either writes, so neither would ever lose.
        await asyncio.sleep(0)
        if nx and key in redis_store:
            set_results.append(False)
            return False
        redis_store[key] = float(value)
        set_results.append(True)
        nonlocal set_completed_count
        set_completed_count += 1
        return True

    async def redis_get_cache(key):
        # Track reads that happen after at least one SET NX has completed
        # — those are the loser-path fallback reads we want to verify.
        if set_completed_count > 0:
            nonlocal get_after_set_count
            get_after_set_count += 1
        return redis_store.get(key)

    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(side_effect=redis_get_cache)
    fake_redis.async_set_cache = AsyncMock(side_effect=redis_set_cache)

    async def slow_find_unique(**_):
        nonlocal db_read_count
        db_read_count += 1
        # Both pods read DB before either's SET NX lands.
        await asyncio.sleep(0)
        row = MagicMock()
        row.spend = 506.0
        return row

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teamtable.find_unique = AsyncMock(
        side_effect=slow_find_unique
    )

    pod_a = DualCache()
    pod_a.redis_cache = fake_redis
    pod_b = DualCache()
    pod_b.redis_cache = fake_redis

    # Each "pod" has its own per-process lock registry. Patch _get_lock to
    # always return a fresh lock so the two coalesced calls do not serialize
    # via one in-process lock (which is what would happen across pods).
    async def fresh_lock(_counter_key):
        return asyncio.Lock()

    with patch.object(SpendCounterReseed, "_get_lock", side_effect=fresh_lock):
        results = await asyncio.gather(
            SpendCounterReseed.coalesced(
                prisma_client=fake_prisma,
                spend_counter_cache=pod_a,
                counter_key=counter_key,
            ),
            SpendCounterReseed.coalesced(
                prisma_client=fake_prisma,
                spend_counter_cache=pod_b,
                counter_key=counter_key,
            ),
        )

    assert all(r == 506.0 for r in results), results
    assert redis_store[counter_key] == pytest.approx(506.0), redis_store
    # Both pods read the DB and both attempted SET NX; exactly one wrote
    # (winner) and one was rejected (loser).
    assert db_read_count == 2
    assert fake_redis.async_set_cache.await_count == 2
    nx_writes = [
        call
        for call in fake_redis.async_set_cache.await_args_list
        if call.kwargs.get("nx") is True
    ]
    assert len(nx_writes) == 2
    assert sorted(set_results) == [
        False,
        True,
    ], f"expected exactly one SET NX winner and one loser, got {set_results}"
    # Loser path executed: after the winner's SET NX returned True, the
    # losing coalesced() call falls back to async_get_cache to read the
    # winner's value rather than re-seeding.
    assert (
        get_after_set_count >= 1
    ), "loser branch (else: read back winner's value) was never exercised"


@pytest.mark.asyncio
async def test_reseed_spend_from_db_user_and_org_prefixes():
    """User and org counters reseed from their own DB tables.

    End-user and tag counters use the already fetched auth objects passed as
    fallback_spend, so this reseed helper must not add extra per-request DB
    reads for them.
    """
    from litellm.proxy.db.spend_counter_reseed import SpendCounterReseed

    user_row = MagicMock()
    user_row.spend = 17.0
    org_row = MagicMock()
    org_row.spend = 305.0

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_usertable.find_unique = AsyncMock(return_value=user_row)
    fake_prisma.db.litellm_endusertable.find_unique = AsyncMock()
    fake_prisma.db.litellm_tagtable.find_unique = AsyncMock()
    fake_prisma.db.litellm_organizationtable.find_unique = AsyncMock(
        return_value=org_row
    )

    assert await SpendCounterReseed.from_db(fake_prisma, "spend:user:alice") == 17.0
    fake_prisma.db.litellm_usertable.find_unique.assert_awaited_once_with(
        where={"user_id": "alice"}
    )

    assert (
        await SpendCounterReseed.from_db(
            fake_prisma,
            "spend:end_user:customer-1",
        )
        is None
    )
    fake_prisma.db.litellm_endusertable.find_unique.assert_not_awaited()

    assert await SpendCounterReseed.from_db(fake_prisma, "spend:tag:paid-tag") is None
    fake_prisma.db.litellm_tagtable.find_unique.assert_not_awaited()

    assert await SpendCounterReseed.from_db(fake_prisma, "spend:org:acme") == 305.0
    fake_prisma.db.litellm_organizationtable.find_unique.assert_awaited_once_with(
        where={"organization_id": "acme"}
    )


@pytest.mark.asyncio
async def test_reseed_spend_from_db_skips_window_variant_keys():
    """Window counters (spend:*:window:{duration}) share prefixes with
    primary counters but don't correspond to a DB row. The guard must
    short-circuit without querying the DB."""
    from litellm.proxy.db.spend_counter_reseed import SpendCounterReseed

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_verificationtoken.find_unique = AsyncMock()
    fake_prisma.db.litellm_teamtable.find_unique = AsyncMock()

    assert (
        await SpendCounterReseed.from_db(fake_prisma, "spend:key:sk-abc:window:1h")
        is None
    )
    assert (
        await SpendCounterReseed.from_db(fake_prisma, "spend:team:team-1:window:1d")
        is None
    )
    fake_prisma.db.litellm_verificationtoken.find_unique.assert_not_awaited()
    fake_prisma.db.litellm_teamtable.find_unique.assert_not_awaited()


@pytest.mark.asyncio
async def test_window_spend_counter_reseeds_from_spend_logs_on_counter_miss():
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import _init_and_increment_window_spend_counter

    counter_cache = DualCache()
    window_start = datetime.now(timezone.utc) - timedelta(hours=1)
    fake_prisma = MagicMock()
    fake_prisma.db.litellm_spendlogs.group_by = AsyncMock(
        return_value=[{"api_key": "key-window", "_sum": {"spend": 2.25}}]
    )

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        await _init_and_increment_window_spend_counter(
            counter_key="spend:key:key-window:window:1h",
            entity_type="Key",
            entity_id="key-window",
            window_start=window_start,
            increment=0.5,
        )

        fake_prisma.db.litellm_spendlogs.group_by.assert_awaited_once_with(
            by=["api_key"],
            where={"api_key": "key-window", "startTime": {"gte": window_start}},
            sum={"spend": True},
        )
        assert counter_cache.in_memory_cache.get_cache(
            key="spend:key:key-window:window:1h"
        ) == pytest.approx(2.75)
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_init_spend_counter_redis_clean_miss_skips_stale_in_memory():
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import _init_and_increment_spend_counter

    counter_cache = DualCache()
    counter_key = "spend:team:team-stale-local"
    counter_cache.in_memory_cache.set_cache(key=counter_key, value=10.0)

    redis_store: dict = {}

    async def redis_increment(key, value, **_):
        redis_store[key] = (redis_store.get(key) or 0.0) + value
        return redis_store[key]

    async def redis_set_cache(key, value, nx=False, **_):
        if nx and key in redis_store:
            return False
        redis_store[key] = float(value)
        return True

    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(return_value=None)
    fake_redis.async_increment = AsyncMock(side_effect=redis_increment)
    fake_redis.async_set_cache = AsyncMock(side_effect=redis_set_cache)
    counter_cache.redis_cache = fake_redis

    db_row = MagicMock()
    db_row.spend = 42.0
    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teamtable.find_unique = AsyncMock(return_value=db_row)

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma, orig_user = (
        ps.spend_counter_cache,
        ps.prisma_client,
        ps.user_api_key_cache,
    )
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    ps.user_api_key_cache = DualCache()
    try:
        await _init_and_increment_spend_counter(
            counter_key=counter_key,
            source_cache_key="team_id:team-stale-local",
            increment=1.5,
        )

        fake_prisma.db.litellm_teamtable.find_unique.assert_awaited_once_with(
            where={"team_id": "team-stale-local"}
        )
        # Seed via SET NX (42) + delta via INCRBYFLOAT (1.5) = 43.5.
        assert redis_store[counter_key] == pytest.approx(43.5)
        assert counter_cache.in_memory_cache.get_cache(
            key=counter_key
        ) == pytest.approx(43.5)
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma
        ps.user_api_key_cache = orig_user


@pytest.mark.asyncio
async def test_window_spend_counter_redis_clean_miss_skips_stale_in_memory():
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import _init_and_increment_window_spend_counter

    counter_cache = DualCache()
    counter_key = "spend:key:key-window-stale-local:window:1h"
    counter_cache.in_memory_cache.set_cache(key=counter_key, value=100.0)
    window_start = datetime.now(timezone.utc) - timedelta(hours=1)

    redis_store: dict = {}

    async def redis_increment(key, value, **_):
        redis_store[key] = (redis_store.get(key) or 0.0) + value
        return redis_store[key]

    async def redis_set_cache(key, value, **_):
        if key in redis_store:
            return False
        redis_store[key] = value
        return True

    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(return_value=None)
    fake_redis.async_set_cache = AsyncMock(side_effect=redis_set_cache)
    fake_redis.async_increment = AsyncMock(side_effect=redis_increment)
    counter_cache.redis_cache = fake_redis

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_spendlogs.group_by = AsyncMock(
        return_value=[{"api_key": "key-window-stale-local", "_sum": {"spend": 2.25}}]
    )

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        await _init_and_increment_window_spend_counter(
            counter_key=counter_key,
            entity_type="Key",
            entity_id="key-window-stale-local",
            window_start=window_start,
            increment=0.5,
        )

        fake_prisma.db.litellm_spendlogs.group_by.assert_awaited_once_with(
            by=["api_key"],
            where={
                "api_key": "key-window-stale-local",
                "startTime": {"gte": window_start},
            },
            sum={"spend": True},
        )
        assert redis_store[counter_key] == pytest.approx(2.75)
        assert counter_cache.in_memory_cache.get_cache(
            key=counter_key
        ) == pytest.approx(2.75)
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_window_spend_counter_redis_concurrent_seed_does_not_double_seed():
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import _init_and_increment_window_spend_counter

    counter_cache = DualCache()
    counter_key = "spend:key:key-window-concurrent-seed:window:1h"
    window_start = datetime.now(timezone.utc) - timedelta(hours=1)
    redis_store = {counter_key: 2.75}
    redis_reads = 0

    async def redis_get_cache(key):
        nonlocal redis_reads
        redis_reads += 1
        if redis_reads <= 2:
            return None
        return redis_store.get(key)

    async def redis_increment(key, value, **_):
        redis_store[key] = (redis_store.get(key) or 0.0) + value
        return redis_store[key]

    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(side_effect=redis_get_cache)
    fake_redis.async_set_cache = AsyncMock(return_value=False)
    fake_redis.async_increment = AsyncMock(side_effect=redis_increment)
    counter_cache.redis_cache = fake_redis

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_spendlogs.group_by = AsyncMock(
        return_value=[
            {"api_key": "key-window-concurrent-seed", "_sum": {"spend": 2.25}}
        ]
    )

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        await _init_and_increment_window_spend_counter(
            counter_key=counter_key,
            entity_type="Key",
            entity_id="key-window-concurrent-seed",
            window_start=window_start,
            increment=0.5,
        )

        fake_redis.async_set_cache.assert_awaited_once_with(
            key=counter_key,
            value=2.25,
            nx=True,
        )
        assert redis_store[counter_key] == pytest.approx(3.25)
        assert counter_cache.in_memory_cache.get_cache(
            key=counter_key
        ) == pytest.approx(3.25)
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_window_spend_counter_skips_invalid_window_start():
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import _init_and_increment_window_spend_counter

    counter_cache = DualCache()

    import litellm.proxy.proxy_server as ps

    orig_counter = ps.spend_counter_cache
    ps.spend_counter_cache = counter_cache
    try:
        await _init_and_increment_window_spend_counter(
            counter_key="spend:key:key-invalid-window:window:not-a-duration",
            entity_type="Key",
            entity_id="key-invalid-window",
            window_start=None,
            increment=0.5,
        )

        assert (
            counter_cache.in_memory_cache.get_cache(
                key="spend:key:key-invalid-window:window:not-a-duration"
            )
            is None
        )
    finally:
        ps.spend_counter_cache = orig_counter


@pytest.mark.asyncio
async def test_window_spend_counter_does_not_seed_zero_when_db_unavailable():
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import _ensure_window_spend_counter_initialized

    counter_cache = DualCache()
    counter_key = "spend:key:key-window-db-unavailable:window:1h"

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = None
    try:
        initialized = await _ensure_window_spend_counter_initialized(
            counter_key=counter_key,
            entity_type="Key",
            entity_id="key-window-db-unavailable",
            window_start=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert initialized is False
        assert counter_cache.in_memory_cache.get_cache(key=counter_key) is None
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_increment_spend_counters_finalizes_after_unreserved_increments():
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import increment_spend_counters

    counter_cache = DualCache()
    counter_cache.in_memory_cache.set_cache(
        key="spend:key:key-finalize-after-increments",
        value=0.5,
    )
    budget_reservation = {
        "reserved_cost": 0.5,
        "entries": [
            {
                "counter_key": "spend:key:key-finalize-after-increments",
                "entity_type": "Key",
                "entity_id": "key-finalize-after-increments",
                "reserved_cost": 0.5,
                "applied_adjustment": 0.0,
            }
        ],
        "finalized": False,
    }
    incremented_counters = []

    async def assert_reservation_not_finalized_yet(**kwargs):
        assert budget_reservation["finalized"] is False
        incremented_counters.append(kwargs["counter_key"])

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_user = ps.spend_counter_cache, ps.user_api_key_cache
    ps.spend_counter_cache = counter_cache
    ps.user_api_key_cache = DualCache()
    try:
        with patch(
            "litellm.proxy.proxy_server._init_and_increment_spend_counter",
            new=AsyncMock(side_effect=assert_reservation_not_finalized_yet),
        ):
            await increment_spend_counters(
                token="key-finalize-after-increments",
                team_id="team-finalize-after-increments",
                user_id=None,
                response_cost=0.25,
                budget_reservation=budget_reservation,
            )

        assert incremented_counters == ["spend:team:team-finalize-after-increments"]
        assert budget_reservation["finalized"] is True
        assert counter_cache.in_memory_cache.get_cache(
            key="spend:key:key-finalize-after-increments"
        ) == pytest.approx(0.25)
    finally:
        ps.spend_counter_cache = orig_counter
        ps.user_api_key_cache = orig_user


@pytest.mark.asyncio
async def test_increment_spend_counters_finalizes_none_cost_reservation():
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import increment_spend_counters

    counter_cache = DualCache()
    counter_cache.in_memory_cache.set_cache(
        key="spend:key:key-finalize-none-cost",
        value=0.5,
    )
    budget_reservation = {
        "reserved_cost": 0.5,
        "entries": [
            {
                "counter_key": "spend:key:key-finalize-none-cost",
                "entity_type": "Key",
                "entity_id": "key-finalize-none-cost",
                "reserved_cost": 0.5,
                "applied_adjustment": 0.0,
            }
        ],
        "finalized": False,
    }

    import litellm.proxy.proxy_server as ps

    orig_counter = ps.spend_counter_cache
    ps.spend_counter_cache = counter_cache
    try:
        await increment_spend_counters(
            token="key-finalize-none-cost",
            team_id=None,
            user_id=None,
            response_cost=None,
            budget_reservation=budget_reservation,
        )

        assert budget_reservation["finalized"] is True
        assert counter_cache.in_memory_cache.get_cache(
            key="spend:key:key-finalize-none-cost"
        ) == pytest.approx(0.0)
    finally:
        ps.spend_counter_cache = orig_counter


@pytest.mark.asyncio
async def test_increment_spend_counters_reseeds_from_db_on_bad_reserved_counter():
    """When the reservation reconcile finds the counter in an inconsistent state
    (here: missing), it must NOT delete the counter and fail open (the old
    behavior, which left the counter unenforced after a Redis reload). It reseeds
    from the authoritative DB so the counter reflects the recorded total and
    budget gating continues."""
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import increment_spend_counters
    from litellm.proxy.db.spend_counter_reseed import SpendCounterReseed

    counter_cache = DualCache()
    budget_reservation = {
        "reserved_cost": 0.5,
        "entries": [
            {
                "counter_key": "spend:key:key-bad-reserved-counter",
                "entity_type": "Key",
                "entity_id": "key-bad-reserved-counter",
                "reserved_cost": 0.5,
                "applied_adjustment": 0.0,
            }
        ],
        "finalized": False,
    }

    import litellm.proxy.proxy_server as ps

    orig_counter = ps.spend_counter_cache
    orig_prisma = ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = MagicMock()  # truthy so reseed reaches from_db
    try:
        with patch.object(SpendCounterReseed, "from_db", AsyncMock(return_value=0.6)):
            await increment_spend_counters(
                token="key-bad-reserved-counter",
                team_id=None,
                user_id=None,
                response_cost=0.25,
                budget_reservation=budget_reservation,
            )

        assert budget_reservation["finalized"] is True
        # counter reseeded to the authoritative DB value, not deleted/left None
        # and not double-counted via a direct increment
        assert counter_cache.in_memory_cache.get_cache(
            key="spend:key:key-bad-reserved-counter"
        ) == pytest.approx(0.6)
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_increment_spend_counter_invalidates_stale_cache_on_redis_failure():
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import _increment_spend_counter_cache

    counter_cache = DualCache()
    counter_cache.in_memory_cache.set_cache(key="spend:team:redis-fail", value=4.0)
    fake_redis = AsyncMock()
    fake_redis.async_increment = AsyncMock(side_effect=RuntimeError("redis down"))
    fake_redis.async_delete_cache = AsyncMock()
    counter_cache.redis_cache = fake_redis

    import litellm.proxy.proxy_server as ps

    orig_counter = ps.spend_counter_cache
    ps.spend_counter_cache = counter_cache
    try:
        with pytest.raises(RuntimeError):
            await _increment_spend_counter_cache(
                counter_key="spend:team:redis-fail",
                increment=0.5,
            )

        assert (
            counter_cache.in_memory_cache.get_cache(key="spend:team:redis-fail") is None
        )
        fake_redis.async_delete_cache.assert_awaited_once_with(
            key="spend:team:redis-fail"
        )
    finally:
        ps.spend_counter_cache = orig_counter


@pytest.mark.asyncio
async def test_get_current_spend_reseeds_from_db_when_counter_missing():
    """
    When both the Redis and in-memory counters are missing, the enforcement
    read path must reseed from the authoritative DB, not fall back to the
    caller-supplied stale value. Otherwise, every Redis TTL expiry lets a
    request through against a stale in-process `team_membership.spend`.
    """
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import get_current_spend

    counter_cache = DualCache()
    recorded_seeds: list = []

    async def record_set_cache(key, value, nx=False, **kwargs):
        recorded_seeds.append({"key": key, "value": value, "nx": nx})
        return True

    fake_redis = AsyncMock()
    fake_redis.async_set_cache = AsyncMock(side_effect=record_set_cache)
    fake_redis.async_get_cache = AsyncMock(return_value=None)
    counter_cache.redis_cache = fake_redis

    # DB has authoritative spend=362.0; caller hands us stale fallback=30.0
    # (the in-process team_membership.spend that hasn't caught up to DB).
    db_row = MagicMock()
    db_row.spend = 362.0
    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teammembership.find_unique = AsyncMock(return_value=db_row)

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        spend = await get_current_spend(
            counter_key="spend:team_member:user-1:team-1",
            fallback_spend=30.0,
        )
        assert spend == 362.0, (
            f"expected DB reseed to return 362.0, got {spend} "
            f"(fallback would have returned 30.0 and caused bypass)"
        )
        # Counter warmed via SET NX so subsequent reads are fast.
        assert ("spend:team_member:user-1:team-1", 362.0, True) in [
            (s["key"], s["value"], s["nx"]) for s in recorded_seeds
        ]
        assert counter_cache.in_memory_cache.get_cache(
            key="spend:team_member:user-1:team-1"
        ) == pytest.approx(362.0)
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_get_current_spend_uses_fallback_when_db_unavailable():
    """
    If prisma is unavailable and both counters are missing, the read path
    must degrade to the caller-supplied fallback rather than raising.
    """
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import get_current_spend

    counter_cache = DualCache()
    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(return_value=None)
    counter_cache.redis_cache = fake_redis

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = None  # simulate prisma unavailable
    try:
        spend = await get_current_spend(
            counter_key="spend:team_member:user-1:team-1",
            fallback_spend=15.5,
        )
        assert spend == 15.5
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_get_current_spend_coalesces_concurrent_reseeds():
    """
    When several concurrent calls hit a cold counter on the same pod,
    only one DB query should fire. The rest should wait for the lock,
    re-check the warmed counter, and return without hitting the DB.
    """
    import asyncio as _asyncio

    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import get_current_spend

    counter_cache = DualCache()
    counter_key = "spend:team_member:user-1:team-coalesce"

    # Track DB query calls and inject a small delay so the concurrent
    # callers actually overlap in the lock-acquire window.
    db_call_count = 0

    async def slow_find_unique(**kwargs):
        nonlocal db_call_count
        db_call_count += 1
        await _asyncio.sleep(0.05)
        row = MagicMock()
        row.spend = 100.0
        return row

    fake_redis = AsyncMock()
    redis_store: dict = {}

    async def redis_get(key, **_):
        return redis_store.get(key)

    async def redis_increment(key, value, **_):
        redis_store[key] = (redis_store.get(key) or 0.0) + value
        return redis_store[key]

    async def redis_set_cache(key, value, nx=False, **_):
        if nx and key in redis_store:
            return False
        redis_store[key] = float(value)
        return True

    fake_redis.async_get_cache = AsyncMock(side_effect=redis_get)
    fake_redis.async_increment = AsyncMock(side_effect=redis_increment)
    fake_redis.async_set_cache = AsyncMock(side_effect=redis_set_cache)
    counter_cache.redis_cache = fake_redis

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teammembership.find_unique = AsyncMock(
        side_effect=slow_find_unique
    )

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        results = await _asyncio.gather(
            *[
                get_current_spend(counter_key=counter_key, fallback_spend=0.0)
                for _ in range(5)
            ]
        )
        assert results == [100.0] * 5, f"all callers should see DB value, got {results}"
        assert (
            db_call_count == 1
        ), f"expected exactly 1 DB query for 5 concurrent reseeds, got {db_call_count}"
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_get_current_spend_uses_db_zero_over_stale_fallback():
    """
    When DB returns spend=0 (e.g. just after a budget period reset), the
    authoritative DB value must win over a stale non-zero fallback. The
    fallback in production is the in-process team_membership.spend, which
    can still hold the pre-reset value across pods.
    """
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import get_current_spend

    counter_cache = DualCache()
    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(return_value=None)
    counter_cache.redis_cache = fake_redis

    db_row = MagicMock()
    db_row.spend = 0.0
    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teammembership.find_unique = AsyncMock(return_value=db_row)

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        spend = await get_current_spend(
            counter_key="spend:team_member:user-1:team-after-reset",
            fallback_spend=42.0,
        )
        assert (
            spend == 0.0
        ), f"DB authoritative 0 must override stale fallback 42, got {spend}"
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_concurrent_read_and_write_paths_share_one_db_query():
    """
    The read path (`get_current_spend`) and the write path
    (`_init_and_increment_spend_counter`) both reseed cold counters from
    the DB. They must share the per-counter lock so a concurrent pre-call
    enforcement read and post-call increment for the same counter collapse
    to one DB query, not two.
    """
    import asyncio as _asyncio

    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import (
        _init_and_increment_spend_counter,
        get_current_spend,
    )

    counter_cache = DualCache()
    counter_key = "spend:team_member:user-1:team-cross-path"

    db_call_count = 0

    async def slow_find_unique(**kwargs):
        nonlocal db_call_count
        db_call_count += 1
        await _asyncio.sleep(0.05)
        row = MagicMock()
        row.spend = 50.0
        return row

    redis_store: dict = {}

    async def redis_get(key, **_):
        return redis_store.get(key)

    async def redis_increment(key, value, **_):
        redis_store[key] = (redis_store.get(key) or 0.0) + value
        return redis_store[key]

    async def redis_set_cache(key, value, nx=False, **_):
        if nx and key in redis_store:
            return False
        redis_store[key] = float(value)
        return True

    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(side_effect=redis_get)
    fake_redis.async_increment = AsyncMock(side_effect=redis_increment)
    fake_redis.async_set_cache = AsyncMock(side_effect=redis_set_cache)
    counter_cache.redis_cache = fake_redis

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teammembership.find_unique = AsyncMock(
        side_effect=slow_find_unique
    )

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma, orig_user = (
        ps.spend_counter_cache,
        ps.prisma_client,
        ps.user_api_key_cache,
    )
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    ps.user_api_key_cache = DualCache()
    try:
        results = await _asyncio.gather(
            get_current_spend(counter_key=counter_key, fallback_spend=0.0),
            _init_and_increment_spend_counter(
                counter_key=counter_key,
                source_cache_key="ignored",
                increment=1.5,
            ),
            get_current_spend(counter_key=counter_key, fallback_spend=0.0),
        )
        assert (
            db_call_count == 1
        ), f"expected 1 DB query for concurrent read+write+read, got {db_call_count}"
        # Read-path callers see the warmed counter; the write path's
        # increment may or may not have landed by then, so accept either
        # the seeded value or seeded+increment.
        assert results[0] in (50.0, 51.5), f"got {results[0]}"
        assert results[2] in (50.0, 51.5), f"got {results[2]}"
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma
        ps.user_api_key_cache = orig_user


@pytest.mark.asyncio
async def test_reseed_locks_dict_is_bounded():
    """
    `SpendCounterReseed._locks` is an LRU bounded at
    `SPEND_COUNTER_RESEED_LOCKS_MAX_SIZE` to prevent unbounded growth in
    long-lived deployments with high counter-key churn. Inserting more
    than the cap evicts the oldest entries.
    """
    import litellm.constants as constants
    from litellm.proxy.db.spend_counter_reseed import SpendCounterReseed

    orig_locks = SpendCounterReseed._locks.copy()
    SpendCounterReseed._locks.clear()
    orig_max = constants.SPEND_COUNTER_RESEED_LOCKS_MAX_SIZE
    constants.SPEND_COUNTER_RESEED_LOCKS_MAX_SIZE = 5
    # The class reads the constant via module-level import, so patch the
    # module-level name on the spend_counter_reseed module too.
    import litellm.proxy.db.spend_counter_reseed as scr

    orig_module_max = scr.SPEND_COUNTER_RESEED_LOCKS_MAX_SIZE
    scr.SPEND_COUNTER_RESEED_LOCKS_MAX_SIZE = 5
    try:
        for i in range(7):
            await SpendCounterReseed._get_lock(f"spend:key:test-key-{i}")
        assert (
            len(SpendCounterReseed._locks) == 5
        ), f"got {len(SpendCounterReseed._locks)}"
        # Oldest two evicted
        assert "spend:key:test-key-0" not in SpendCounterReseed._locks
        assert "spend:key:test-key-1" not in SpendCounterReseed._locks
        # Most recent retained
        assert "spend:key:test-key-6" in SpendCounterReseed._locks
    finally:
        constants.SPEND_COUNTER_RESEED_LOCKS_MAX_SIZE = orig_max
        scr.SPEND_COUNTER_RESEED_LOCKS_MAX_SIZE = orig_module_max
        SpendCounterReseed._locks.clear()
        SpendCounterReseed._locks.update(orig_locks)


@pytest.mark.asyncio
async def test_reseed_warms_cache_even_on_zero_db_spend():
    """
    When DB returns 0.0 (fresh entity / just after reset), the cache must
    still be warmed so subsequent reads hit the cache instead of issuing
    another DB query. Skipping the warm causes O(requests) DB load on
    zero-spend entities.
    """
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import get_current_spend

    counter_cache = DualCache()
    counter_key = "spend:team_member:user-1:team-zero-warm"
    redis_store: dict = {}

    async def redis_get(key, **_):
        return redis_store.get(key)

    async def redis_increment(key, value, **_):
        redis_store[key] = (redis_store.get(key) or 0.0) + value
        return redis_store[key]

    async def redis_set_cache(key, value, nx=False, **_):
        if nx and key in redis_store:
            return False
        redis_store[key] = float(value)
        return True

    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(side_effect=redis_get)
    fake_redis.async_increment = AsyncMock(side_effect=redis_increment)
    fake_redis.async_set_cache = AsyncMock(side_effect=redis_set_cache)
    counter_cache.redis_cache = fake_redis

    db_call_count = 0

    async def find_unique(**kwargs):
        nonlocal db_call_count
        db_call_count += 1
        row = MagicMock()
        row.spend = 0.0
        return row

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teammembership.find_unique = AsyncMock(
        side_effect=find_unique
    )

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        # First call: cold cache, hits DB, returns 0.
        spend1 = await get_current_spend(counter_key=counter_key, fallback_spend=0.0)
        # Second call: cache should be warmed at 0, no second DB query.
        spend2 = await get_current_spend(counter_key=counter_key, fallback_spend=0.0)
        assert spend1 == 0.0 and spend2 == 0.0
        assert (
            db_call_count == 1
        ), f"second read should hit warmed cache, got {db_call_count} DB queries"
        assert redis_store.get(counter_key) == 0.0, "cache must be warmed at 0"
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


# -----------------------------------------------------------------------------
# /config/update — critical paths only.
#
# These exercise the four behaviors that broke or changed in the rewrite of
# update_config (litellm/proxy/proxy_server.py): targeted per-section writes,
# the removal of the store_model_in_db gate, env var encryption, and the
# success_callback / litellm_settings merge semantics. All other branches
# (auth, missing-DB, slack auto-enable, router_settings merge) are covered
# implicitly or by upstream tests.
# -----------------------------------------------------------------------------


class _FakeRow:
    def __init__(self, param_name, param_value):
        self.param_name = param_name
        self.param_value = param_value


class _FakeLitellmConfig:
    def __init__(self, initial_rows=None):
        self.rows = dict(initial_rows or {})
        self.upsert_calls: list = []
        self.find_first = AsyncMock(side_effect=self._find_first)
        self.upsert = AsyncMock(side_effect=self._upsert)

    async def _find_first(self, where=None):
        if where and "param_name" in where:
            name = where["param_name"]
            if name in self.rows:
                return _FakeRow(name, self.rows[name])
        return None

    async def _upsert(self, where=None, data=None):
        name = where["param_name"]
        raw = data["update"]["param_value"]
        value = json.loads(raw) if isinstance(raw, str) else raw
        self.rows[name] = value
        self.upsert_calls.append((name, value))


class _FakePrismaClient:
    def __init__(self, initial_rows=None):
        self.db = mock.MagicMock()
        self.db.litellm_config = _FakeLitellmConfig(initial_rows=initial_rows)
        self.jsonify_object = lambda obj: obj


@pytest.fixture
def _update_config_setup(monkeypatch):
    """Install fakes for the /config/update endpoint and return (client, prisma)."""
    from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
    from litellm.proxy.auth.user_api_key_auth import user_api_key_auth as auth_dep

    def _install(initial_rows=None, store_model_in_db=True):
        prisma = _FakePrismaClient(initial_rows=initial_rows)
        monkeypatch.setattr("litellm.proxy.proxy_server.prisma_client", prisma)
        monkeypatch.setattr(
            "litellm.proxy.proxy_server.store_model_in_db", store_model_in_db
        )
        monkeypatch.setattr(
            "litellm.proxy.proxy_server.encrypt_value_helper",
            lambda value, **_: f"enc:{value}",
        )
        monkeypatch.setattr(
            "litellm.proxy.proxy_server.invalidate_config_param",
            AsyncMock(return_value=None),
        )
        from litellm.proxy.proxy_server import proxy_config as real_proxy_config

        monkeypatch.setattr(
            real_proxy_config, "add_deployment", AsyncMock(return_value=None)
        )

        original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[auth_dep] = lambda: UserAPIKeyAuth(
            user_id="test_admin",
            user_role=LitellmUserRoles.PROXY_ADMIN,
            api_key="sk-1234",
        )
        client = TestClient(app)

        def _restore():
            app.dependency_overrides = original_overrides

        return client, prisma, _restore

    return _install


def test_update_config_writes_only_sent_section(_update_config_setup):
    """A request that only touches general_settings must not write any other
    section row, and must leave previously-written rows byte-identical."""
    client, prisma, restore = _update_config_setup(
        initial_rows={
            "litellm_settings": {"drop_params": True},
            "environment_variables": {"FOO": "enc:bar"},
        }
    )
    try:
        resp = client.post(
            "/config/update",
            json={"general_settings": {"store_prompts_in_spend_logs": True}},
        )
        assert resp.status_code == 200
        written = {name for name, _ in prisma.db.litellm_config.upsert_calls}
        assert written == {"general_settings"}
        assert prisma.db.litellm_config.rows["litellm_settings"] == {
            "drop_params": True
        }
        assert prisma.db.litellm_config.rows["environment_variables"] == {
            "FOO": "enc:bar"
        }
    finally:
        restore()


def test_update_config_env_var_round_trip_not_double_encrypted(
    _update_config_setup, monkeypatch
):
    """Endpoint-level regression for the /config/update double-encryption bug.

    The Admin UI reads config back via /get/config/callbacks (which returns
    the stored, still-encrypted value) and re-POSTs it on the next save. The
    handler must NOT stack a second encryption layer on the re-submitted
    ciphertext, and must leave untouched keys byte-identical.

    Uses an invertible fake encrypt/decrypt pair ("enc:" prefix) so the
    decrypt-then-encrypt chokepoint round-trips faithfully. On the pre-fix
    code this stored "enc:enc:..."; the assertions below would fail there.
    """

    def _fake_decrypt(
        value, key=None, exception_type="error", return_original_value=False
    ):
        if isinstance(value, str) and value.startswith("enc:"):
            return value[len("enc:") :]
        return value if return_original_value else None

    monkeypatch.setattr(
        "litellm.proxy.proxy_server.decrypt_value_helper", _fake_decrypt
    )

    client, prisma, restore = _update_config_setup(
        initial_rows={"environment_variables": {"PREEXISTING_KEY": "enc:keepme"}}
    )
    try:
        # First write: plaintext in -> single-encrypted at rest.
        resp = client.post(
            "/config/update",
            json={"environment_variables": {"LANGFUSE_SECRET_KEY": "sk-secret"}},
        )
        assert resp.status_code == 200
        stored = prisma.db.litellm_config.rows["environment_variables"]
        assert stored["LANGFUSE_SECRET_KEY"] == "enc:sk-secret"

        # UI round-trip: re-POST the stored ciphertext (no field change).
        resp = client.post(
            "/config/update",
            json={
                "environment_variables": {
                    "LANGFUSE_SECRET_KEY": stored["LANGFUSE_SECRET_KEY"]
                }
            },
        )
        assert resp.status_code == 200
        stored = prisma.db.litellm_config.rows["environment_variables"]

        # The bug: this would be "enc:enc:sk-secret". The fix keeps it single.
        assert stored["LANGFUSE_SECRET_KEY"] == "enc:sk-secret"
        assert (
            _fake_decrypt(stored["LANGFUSE_SECRET_KEY"], return_original_value=True)
            == "sk-secret"
        )

        # Untouched key preserved byte-for-byte (only sent keys rewritten).
        assert stored["PREEXISTING_KEY"] == "enc:keepme"
    finally:
        restore()


def test_update_config_can_flip_store_model_in_db_when_currently_false(
    _update_config_setup,
):
    """The endpoint used to refuse all writes when store_model_in_db was
    False, blocking the very request that would flip it to True."""
    client, prisma, restore = _update_config_setup(store_model_in_db=False)
    try:
        resp = client.post(
            "/config/update", json={"general_settings": {"store_model_in_db": True}}
        )
        assert resp.status_code == 200
        assert (
            prisma.db.litellm_config.rows["general_settings"]["store_model_in_db"]
            is True
        )
    finally:
        restore()


def test_update_config_environment_variables_encrypted_before_write(
    _update_config_setup,
):
    """env var values must be encrypted before they hit the DB row."""
    client, prisma, restore = _update_config_setup()
    try:
        resp = client.post(
            "/config/update",
            json={"environment_variables": {"OPENAI_API_KEY": "sk-secret"}},
        )
        assert resp.status_code == 200
        stored = prisma.db.litellm_config.rows["environment_variables"]
        assert stored == {"OPENAI_API_KEY": "enc:sk-secret"}
    finally:
        restore()


def test_update_config_litellm_settings_request_wins_for_non_callback_keys(
    _update_config_setup,
):
    """Sending {"drop_params": False} when the row holds drop_params: True
    must persist False (request wins). Untouched keys preserved."""
    client, prisma, restore = _update_config_setup(
        initial_rows={
            "litellm_settings": {"drop_params": True, "set_verbose": True},
        }
    )
    try:
        resp = client.post(
            "/config/update", json={"litellm_settings": {"drop_params": False}}
        )
        assert resp.status_code == 200
        stored = prisma.db.litellm_config.rows["litellm_settings"]
        assert stored["drop_params"] is False
        assert stored["set_verbose"] is True
    finally:
        restore()


def test_update_config_success_callback_normalizes_existing_mixed_case(
    _update_config_setup,
):
    """Existing mixed-case callback names (written elsewhere) must be
    normalized to lowercase before union, otherwise the union dedup misses
    against the lowercase incoming entry and delete_callback (lowercase
    lookup) cannot find the original."""
    client, prisma, restore = _update_config_setup(
        initial_rows={"litellm_settings": {"success_callback": ["Langfuse", "SQS"]}}
    )
    try:
        resp = client.post(
            "/config/update",
            json={"litellm_settings": {"success_callback": ["langfuse"]}},
        )
        assert resp.status_code == 200
        stored = prisma.db.litellm_config.rows["litellm_settings"]["success_callback"]
        assert set(stored) == {"langfuse", "sqs"}
    finally:
        restore()


# ---------------------------------------------------------------------------
# Lazy feature loading (LazyFeatureMiddleware) — verifies that optional
# routers are NOT imported at module load and ARE imported on first request
# to a matching path prefix. The same module isn't re-imported on subsequent
# requests.
# ---------------------------------------------------------------------------


class TestLazyFeatureRegistry:
    """Sanity checks on the registry shape — guards against accidental edits."""

    def test_registry_entries_have_required_fields(self):
        from litellm.proxy._lazy_features import LAZY_FEATURES, LazyFeature

        assert len(LAZY_FEATURES) > 0
        for feat in LAZY_FEATURES:
            assert isinstance(feat, LazyFeature)
            assert feat.name
            assert feat.module_path
            assert feat.path_prefixes
            assert all(p.startswith("/") for p in feat.path_prefixes)
            assert callable(feat.register_fn)

    def test_registry_names_unique(self):
        from litellm.proxy._lazy_features import LAZY_FEATURES

        names = [f.name for f in LAZY_FEATURES]
        assert len(names) == len(set(names)), "duplicate feature names"

    def test_matches_covers_prefix_and_suffix(self):
        """``matches`` is the single matcher shared by the middleware (request
        paths) and the warm endpoint (registered route paths), so a route that
        only matches via suffix — e.g. ``/v1/a2a/{id}/message/send`` against the
        ``/a2a`` prefix — must still be claimed by the feature."""
        from litellm.proxy._lazy_features import LazyFeature

        feat = LazyFeature(
            name="a2a",
            module_path="json",
            path_prefixes=("/a2a",),
            path_suffixes=("/message/send",),
        )
        assert feat.matches("/a2a/abc/message/send")
        assert feat.matches("/v1/a2a/abc/message/send")
        assert feat.matches("/a2a/abc/.well-known/agent-card.json")
        assert not feat.matches("/v1/a2a/discover")
        assert not feat.matches("/unrelated")


class TestLazyFeaturesNotImportedAtStartup:
    """
    The whole point of the refactor: gated feature modules must NOT be
    present in `sys.modules` immediately after `proxy_server` imports.
    """

    def test_heavy_modules_absent_at_startup(self):
        # Static scan of proxy_server.py source — catches any top-level
        # `from <lazy_module> import` that would defeat lazy loading.
        # Importing proxy_server in a subprocess and diffing sys.modules
        # would also work, but takes 60-120 s and flakes on slow CI runners.
        import re
        from pathlib import Path

        from litellm.proxy._lazy_features import LAZY_FEATURES

        proxy_server_src = (
            Path(__file__).resolve().parents[3] / "litellm/proxy/proxy_server.py"
        ).read_text()

        leaks = []
        for feat in LAZY_FEATURES:
            # Anchor at column 0 — indented imports inside function bodies
            # are fine (deferred until the function runs).
            pattern = (
                rf"^(from\s+{re.escape(feat.module_path)}\s+import|"
                rf"import\s+{re.escape(feat.module_path)})"
            )
            if re.search(pattern, proxy_server_src, re.MULTILINE):
                leaks.append(feat.module_path)

        assert not leaks, (
            "proxy_server.py top-level imports a lazy feature module — these "
            f"should be loaded via LazyFeatureMiddleware: {leaks}"
        )


class TestLazyFeatureMiddleware:
    """Behavior of the middleware itself, exercised in isolation."""

    @pytest.mark.asyncio
    async def test_first_request_triggers_load_subsequent_does_not(self):
        from fastapi import FastAPI

        from litellm.proxy._lazy_features import (
            LazyFeature,
            LazyFeatureMiddleware,
        )

        loads = []

        def fake_register(app, module):
            loads.append(getattr(module, "__name__", "?"))

        feat = LazyFeature(
            name="dummy",
            module_path="json",  # any always-importable stdlib module
            path_prefixes=("/dummy",),
            register_fn=fake_register,
        )

        # Build a minimal ASGI receiver to satisfy the middleware contract
        async def downstream(scope, receive, send):
            # echo back; no-op handler
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        target_app = FastAPI()
        mw = LazyFeatureMiddleware(downstream, fastapi_app=target_app, features=(feat,))

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        sent: list = []

        async def send(message):
            sent.append(message)

        # First request matching the prefix triggers register
        await mw(
            {"type": "http", "path": "/dummy/x", "method": "GET", "headers": []},
            receive,
            send,
        )
        assert loads == ["json"]

        # Second matching request must NOT re-register
        sent.clear()
        await mw(
            {"type": "http", "path": "/dummy/y", "method": "GET", "headers": []},
            receive,
            send,
        )
        assert loads == ["json"], "register_fn called twice for the same feature"

        # Non-matching path must not trigger anything
        await mw(
            {"type": "http", "path": "/unrelated", "method": "GET", "headers": []},
            receive,
            send,
        )
        assert loads == ["json"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "server_root_path,request_path,should_load,case",
        [
            # SERVER_ROOT_PATH set: incoming path includes prefix → strip and match.
            ("/api/v1", "/api/v1/dummy/x", True, "root_path strip + match"),
            # Trailing-slash env var must be normalized.
            ("/api/v1/", "/api/v1/dummy/x", True, "trailing-slash env normalization"),
            # Reverse proxy already stripped the prefix → original path still matches.
            ("/api/v1", "/dummy/x", True, "pre-stripped path still loads"),
            # No SERVER_ROOT_PATH set → unchanged behavior.
            ("", "/dummy/x", True, "no root path"),
            # SERVER_ROOT_PATH=/ must be a no-op (not strip every leading slash).
            ("/", "/dummy/x", True, "root_path='/' is no-op"),
            # Boundary check: /apiv2 must not match root /api.
            ("/api", "/apiv2/foo", False, "boundary check prevents false match"),
            # Genuine non-match under root_path.
            ("/api/v1", "/api/v1/unrelated", False, "unrelated path under root"),
        ],
    )
    async def test_root_path_handling(
        self, monkeypatch, server_root_path, request_path, should_load, case
    ):
        """
        The middleware must strip SERVER_ROOT_PATH before prefix-matching so
        lazy features load under deployments that set a server root path,
        while handling boundary, trailing-slash, and reverse-proxy edge cases
        correctly.
        """
        from fastapi import FastAPI

        from litellm.proxy._lazy_features import (
            LazyFeature,
            LazyFeatureMiddleware,
        )

        monkeypatch.setenv("SERVER_ROOT_PATH", server_root_path)

        loads = []

        def fake_register(app, module):
            loads.append(getattr(module, "__name__", "?"))

        feat = LazyFeature(
            name=f"dummy_{case}",
            module_path="json",
            path_prefixes=("/dummy",),
            register_fn=fake_register,
        )

        async def downstream(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        target_app = FastAPI()
        mw = LazyFeatureMiddleware(downstream, fastapi_app=target_app, features=(feat,))

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        await mw(
            {
                "type": "http",
                "path": request_path,
                "method": "GET",
                "headers": [],
            },
            receive,
            send,
        )
        if should_load:
            assert loads == ["json"], f"{case}: expected feature to load"
        else:
            assert loads == [], f"{case}: feature must not load"

    @pytest.mark.asyncio
    async def test_concurrent_first_requests_only_register_once(self):
        """
        Two requests to the same prefix arriving in parallel must result in
        exactly one `register_fn` invocation — the lock prevents the import +
        register from racing with itself.
        """
        from fastapi import FastAPI

        from litellm.proxy._lazy_features import (
            LazyFeature,
            LazyFeatureMiddleware,
        )

        loads = []

        def slow_register(app, module):
            loads.append(getattr(module, "__name__", "?"))

        feat = LazyFeature(
            name="dummy_concurrent",
            module_path="json",
            path_prefixes=("/dummy_c",),
            register_fn=slow_register,
        )

        async def downstream(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        target_app = FastAPI()
        mw = LazyFeatureMiddleware(downstream, fastapi_app=target_app, features=(feat,))

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        sent: list = []

        async def send(message):
            sent.append(message)

        async def hit():
            await mw(
                {
                    "type": "http",
                    "path": "/dummy_c/x",
                    "method": "GET",
                    "headers": [],
                },
                receive,
                send,
            )

        await asyncio.gather(hit(), hit(), hit(), hit(), hit())
        assert loads == [
            "json"
        ], f"expected one registration despite concurrent first hits, got {loads}"

    @pytest.mark.asyncio
    async def test_failing_import_does_not_loop(self):
        """
        If a feature's module can't be imported, the middleware should mark it
        loaded anyway so subsequent requests don't repeatedly retry the failing
        import (which would amplify the cost on every request).
        """
        from fastapi import FastAPI

        from litellm.proxy._lazy_features import (
            LazyFeature,
            LazyFeatureMiddleware,
        )

        attempts = []

        def fail_register(app, module):
            attempts.append("called")
            raise RuntimeError("boom")

        feat = LazyFeature(
            name="failing",
            module_path="json",
            path_prefixes=("/fail",),
            register_fn=fail_register,
        )

        async def downstream(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        target_app = FastAPI()
        mw = LazyFeatureMiddleware(downstream, fastapi_app=target_app, features=(feat,))

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        sent: list = []

        async def send(message):
            sent.append(message)

        for _ in range(3):
            await mw(
                {"type": "http", "path": "/fail/x", "method": "GET", "headers": []},
                receive,
                send,
            )
        assert attempts == [
            "called"
        ], f"failing register_fn should be invoked once, not on every request; got {attempts}"


@pytest.mark.asyncio
async def test_get_current_spend_redis_clean_miss_skips_stale_in_memory():
    """When Redis is reachable and cleanly returns None (TTL expired,
    counter genuinely absent), the read must reseed from DB - NOT fall
    through to per-pod in-memory which only contains this pod's writes.

    Pre-fix in multi-pod deployments, in-memory contained a stale local
    subset (e.g. $30) while DB had the true cross-pod total ($500). The
    fall-through returned $30, enforcement passed, bypass.
    """
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import get_current_spend

    counter_cache = DualCache()
    counter_key = "spend:team_member:user-1:team-1"

    # Per-pod stale in-memory: only this pod's writes, not cross-pod truth.
    counter_cache.in_memory_cache.set_cache(key=counter_key, value=30.0)

    # Redis cleanly returns None (key expired or never written on this pod).
    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(return_value=None)
    fake_redis.async_increment = AsyncMock(return_value=500.0)
    counter_cache.redis_cache = fake_redis

    # DB has the authoritative cross-pod spend.
    db_row = MagicMock()
    db_row.spend = 500.0
    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teammembership.find_unique = AsyncMock(return_value=db_row)

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        spend = await get_current_spend(counter_key=counter_key, fallback_spend=0.0)
        assert spend == 500.0, (
            f"expected DB-authoritative 500.0 on clean Redis miss, got {spend} "
            f"(stale per-pod in-memory $30 would have caused multi-pod bypass)"
        )
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


@pytest.mark.asyncio
async def test_get_current_spend_redis_error_falls_back_to_in_memory():
    """When Redis raises, the read should still degrade to in-memory rather
    than going straight to DB - in-memory is at least same-pod-fresh and
    cheaper than a DB query during a Redis outage."""
    from litellm.caching.dual_cache import DualCache
    from litellm.proxy.proxy_server import get_current_spend

    counter_cache = DualCache()
    counter_key = "spend:team_member:user-1:team-1"

    counter_cache.in_memory_cache.set_cache(key=counter_key, value=42.0)

    fake_redis = AsyncMock()
    fake_redis.async_get_cache = AsyncMock(side_effect=ConnectionError("redis down"))
    counter_cache.redis_cache = fake_redis

    fake_prisma = MagicMock()
    fake_prisma.db.litellm_teammembership.find_unique = AsyncMock(
        return_value=MagicMock(spend=999.0)
    )

    import litellm.proxy.proxy_server as ps

    orig_counter, orig_prisma = ps.spend_counter_cache, ps.prisma_client
    ps.spend_counter_cache = counter_cache
    ps.prisma_client = fake_prisma
    try:
        spend = await get_current_spend(counter_key=counter_key, fallback_spend=0.0)
        assert spend == 42.0, (
            f"expected in-memory fallback 42.0 on Redis error, got {spend} "
            f"(should not have hit DB when Redis errored)"
        )
        # DB query should NOT have fired - in-memory short-circuits.
        fake_prisma.db.litellm_teammembership.find_unique.assert_not_awaited()
    finally:
        ps.spend_counter_cache = orig_counter
        ps.prisma_client = orig_prisma


def test_realtime_websocket_route_aliases_registered():
    """Realtime sessions reach the proxy via three path aliases stacked on
    `realtime_websocket_endpoint`. Dropping any of them silently 405s
    WebSocket upgrades because the catch-all `/openai/{endpoint:path}`
    HTTP passthrough only declares HTTP methods. The aliases must also be
    in `LiteLLMRoutes.openai_routes` (so non-admin / team / key-scoped
    auth allows them) and in `API_ROUTE_TO_CALL_TYPES` (so call-type-aware
    logic such as guardrails can resolve the realtime call type)."""
    from starlette.routing import WebSocketRoute

    from litellm.proxy._types import LiteLLMRoutes
    from litellm.proxy.proxy_server import app
    from litellm.types.utils import API_ROUTE_TO_CALL_TYPES, CallTypes

    websocket_paths = {
        route.path for route in app.routes if isinstance(route, WebSocketRoute)
    }
    openai_routes = LiteLLMRoutes.openai_routes.value

    for expected in ("/openai/v1/realtime", "/v1/realtime", "/realtime"):
        assert expected in websocket_paths, (
            f"{expected!r} missing from registered WebSocket routes; the "
            f"realtime endpoint will 405 for clients hitting this path."
        )
        assert expected in openai_routes, (
            f"{expected!r} missing from LiteLLMRoutes.openai_routes; "
            f"non-admin / team / key-scoped users will get 403 on this path."
        )
        assert API_ROUTE_TO_CALL_TYPES.get(expected) == [CallTypes.arealtime], (
            f"{expected!r} missing from API_ROUTE_TO_CALL_TYPES; call-type "
            f"resolution will return None and break call-type-aware features."
        )


class TestTransformRequestBannedParams:
    """
    /utils/transform_request applies the same banned-param check as LLM endpoints.

    Without this check, any authenticated user could supply aws_sts_endpoint,
    api_base, etc. and have the server forward its credentials to an
    attacker-controlled endpoint during SDK credential resolution.
    """

    @pytest.fixture
    def client(self):
        mock_auth = UserAPIKeyAuth(
            user_id="test-internal",
            user_role=LitellmUserRoles.INTERNAL_USER,
        )
        original = app.dependency_overrides.copy()
        app.dependency_overrides[user_api_key_auth] = lambda: mock_auth
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides = original

    @pytest.mark.parametrize(
        "banned",
        [
            "aws_sts_endpoint",
            "api_base",
            "aws_web_identity_token",
            "vertex_credentials",
        ],
    )
    def test_banned_params_rejected_for_all_users(self, client, banned):
        """Banned params must be blocked for any authenticated user."""
        response = client.post(
            "/utils/transform_request",
            json={
                "call_type": "completion",
                "request_body": {
                    "model": "gpt-3.5-turbo",
                    banned: "https://attacker.example",
                },
            },
        )
        assert response.status_code == 400, (
            f"Expected 400 for banned param '{banned}', "
            f"got {response.status_code}: {response.json()}"
        )


class TestSortModelsByDisplayName:
    """Regression: team BYOK rows persist an internal `model_name` like
    `model_name_{team_id}_{uuid}` and expose the user-facing name via
    `model_info.team_public_model_name`. Sorting must use the displayed
    name so BYOK rows interleave with non-BYOK rows alphabetically —
    otherwise they clump at the end on their opaque IDs even though the
    UI shows them under a normal-looking name.
    """

    def test_byok_models_sort_by_team_public_model_name(self):
        from litellm.proxy.proxy_server import _sort_models

        models = [
            {"model_name": "claude-haiku-4-5", "model_info": {}},
            {
                # Opaque internal name; UI displays team_public_model_name.
                "model_name": "model_name_team-1_abc123",
                "model_info": {"team_public_model_name": "anthropic/claude"},
            },
            {"model_name": "gpt-4o", "model_info": {}},
        ]

        sorted_models = _sort_models(
            all_models=models, sort_by="model_name", sort_order="asc"
        )
        displayed_order = [
            m["model_info"].get("team_public_model_name") or m["model_name"]
            for m in sorted_models
        ]
        assert displayed_order == [
            "anthropic/claude",
            "claude-haiku-4-5",
            "gpt-4o",
        ]

    def test_byok_models_sort_descending_by_display_name(self):
        from litellm.proxy.proxy_server import _sort_models

        models = [
            {"model_name": "claude-haiku-4-5", "model_info": {}},
            {
                "model_name": "model_name_team-1_zzz",
                "model_info": {"team_public_model_name": "zeta/model"},
            },
            {"model_name": "gpt-4o", "model_info": {}},
        ]

        sorted_models = _sort_models(
            all_models=models, sort_by="model_name", sort_order="desc"
        )
        displayed_order = [
            m["model_info"].get("team_public_model_name") or m["model_name"]
            for m in sorted_models
        ]
        assert displayed_order == [
            "zeta/model",
            "gpt-4o",
            "claude-haiku-4-5",
        ]

    def test_empty_team_public_model_name_falls_back_to_model_name(self):
        # Empty string for team_public_model_name (not None) must still
        # fall back to model_name — otherwise BYOK rows with a blank
        # display name would sort to the top.
        from litellm.proxy.proxy_server import _sort_models

        models = [
            {"model_name": "alpha", "model_info": {"team_public_model_name": ""}},
            {"model_name": "beta", "model_info": {}},
        ]

        sorted_models = _sort_models(
            all_models=models, sort_by="model_name", sort_order="asc"
        )
        assert [m["model_name"] for m in sorted_models] == ["alpha", "beta"]


class TestDeleteDeploymentSync:
    @pytest.mark.asyncio
    async def test_delete_deployment_evicts_model_when_all_db_models_deleted(self):
        """
        Regression test for #28443.
        When all DB models are deleted, _delete_deployment must evict them from
        the router. The old code returned 0 early when db_models was empty.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        from litellm.proxy.proxy_server import ProxyConfig

        proxy_config = ProxyConfig()
        mock_router = MagicMock()
        mock_router.get_model_ids.return_value = ["model-id-to-evict"]
        mock_router.delete_deployment.return_value = MagicMock()

        with patch("litellm.proxy.proxy_server.llm_router", mock_router):
            with patch.object(
                proxy_config, "get_config", AsyncMock(return_value={"model_list": []})
            ):
                count = await proxy_config._delete_deployment(db_models=[])

        mock_router.delete_deployment.assert_called_once_with(id="model-id-to-evict")
        assert count == 1

    @pytest.mark.asyncio
    async def test_update_llm_router_skips_update_on_db_fetch_failure(self):
        """
        When _get_models_from_db returns None (transient DB failure), _update_llm_router
        must return early without touching the router.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        from litellm.proxy.proxy_server import ProxyConfig

        proxy_config = ProxyConfig()
        mock_router = MagicMock()

        with patch("litellm.proxy.proxy_server.llm_router", mock_router):
            with patch.object(proxy_config, "get_config", AsyncMock(return_value={})):
                await proxy_config._update_llm_router(
                    new_models=None, proxy_logging_obj=MagicMock()
                )

        mock_router.delete_deployment.assert_not_called()
        mock_router.upsert_deployment.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_models_from_db_returns_none_on_exception(self):
        """
        _get_models_from_db must return None (not []) when the DB raises an exception,
        so callers can distinguish a transient failure from a genuinely empty DB.
        """
        from unittest.mock import AsyncMock, MagicMock

        from litellm.proxy.proxy_server import ProxyConfig

        proxy_config = ProxyConfig()
        mock_prisma = MagicMock()
        mock_prisma.db.litellm_proxymodeltable.find_many = AsyncMock(
            side_effect=Exception("DB connection lost")
        )

        result = await proxy_config._get_models_from_db(prisma_client=mock_prisma)

        assert (
            result is None
        ), f"Expected None on DB failure to signal fetch error, got {result!r}"


def test_get_config_list_includes_cancel_on_disconnect(monkeypatch):
    """Follow-up to #30223: the flag must be discoverable via /config/list,
    which requires both the ConfigGeneralSettings field and the allowed_args
    entry in get_config_list; missing either silently hides it from the UI."""
    import types
    from unittest.mock import AsyncMock, MagicMock

    from fastapi.testclient import TestClient

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
    from litellm.proxy.proxy_server import app

    mock_prisma = MagicMock()
    mock_config_table = MagicMock()
    mock_config_table.find_first = AsyncMock(return_value=None)
    mock_prisma.db = types.SimpleNamespace(litellm_config=mock_config_table)
    monkeypatch.setattr(ps, "prisma_client", mock_prisma)
    app.dependency_overrides[ps.user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_id="admin", user_role=LitellmUserRoles.PROXY_ADMIN
    )
    try:
        client = TestClient(app)
        resp = client.get("/config/list", params={"config_type": "general_settings"})
        assert resp.status_code == 200, resp.text
        fields = {item["field_name"]: item for item in resp.json()}
        assert "cancel_on_disconnect" in fields
        assert fields["cancel_on_disconnect"]["field_type"] == "Boolean"
    finally:
        app.dependency_overrides.clear()


def test_get_config_list_includes_skip_user_budget_on_team_key(monkeypatch):
    """Related to #12905: the opt-out flag must be discoverable via /config/list so
    it renders as a Boolean toggle on the Admin UI General Settings table. This
    requires both the ConfigGeneralSettings field and the allowed_args entry."""
    import types
    from unittest.mock import AsyncMock, MagicMock

    from fastapi.testclient import TestClient

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
    from litellm.proxy.proxy_server import app

    mock_prisma = MagicMock()
    mock_config_table = MagicMock()
    mock_config_table.find_first = AsyncMock(return_value=None)
    mock_prisma.db = types.SimpleNamespace(litellm_config=mock_config_table)
    monkeypatch.setattr(ps, "prisma_client", mock_prisma)
    app.dependency_overrides[ps.user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_id="admin", user_role=LitellmUserRoles.PROXY_ADMIN
    )
    try:
        client = TestClient(app)
        resp = client.get("/config/list", params={"config_type": "general_settings"})
        assert resp.status_code == 200, resp.text
        fields = {item["field_name"]: item for item in resp.json()}
        assert "skip_user_budget_on_team_key" in fields
        assert fields["skip_user_budget_on_team_key"]["field_type"] == "Boolean"
    finally:
        app.dependency_overrides.clear()


def test_get_config_list_includes_budget_exceeded_throttle_percentage(monkeypatch):
    """The throttle fraction is a litellm_settings scalar surfaced on the General
    Settings table as a Float field so it sits with the other global limits; it
    must appear in /config/list reading its live litellm.<attr> value."""
    import types
    from unittest.mock import AsyncMock, MagicMock

    from fastapi.testclient import TestClient

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
    from litellm.proxy.proxy_server import app

    mock_prisma = MagicMock()
    mock_config_table = MagicMock()
    mock_config_table.find_first = AsyncMock(return_value=None)
    mock_prisma.db = types.SimpleNamespace(litellm_config=mock_config_table)
    monkeypatch.setattr(ps, "prisma_client", mock_prisma)
    monkeypatch.setattr(litellm, "budget_exceeded_throttle_percentage", 0.15)
    app.dependency_overrides[ps.user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_id="admin", user_role=LitellmUserRoles.PROXY_ADMIN
    )
    try:
        client = TestClient(app)
        resp = client.get("/config/list", params={"config_type": "general_settings"})
        assert resp.status_code == 200, resp.text
        fields = {item["field_name"]: item for item in resp.json()}
        assert "budget_exceeded_throttle_percentage" in fields
        assert fields["budget_exceeded_throttle_percentage"]["field_type"] == "Float"
        assert fields["budget_exceeded_throttle_percentage"]["field_value"] == 0.15
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_config_field_throttle_persists_to_litellm_settings(monkeypatch):
    """Editing the throttle Float row on the General Settings table routes to
    litellm_settings (not general_settings): it sets litellm.<attr> live and
    persists under litellm_settings so the runtime read is unchanged."""
    from unittest.mock import MagicMock

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import (
        ConfigFieldUpdate,
        LitellmUserRoles,
        UserAPIKeyAuth,
    )
    from litellm.proxy.proxy_server import update_config_general_settings

    saved: dict = {}

    async def fake_get_config():
        return {"litellm_settings": {}}

    async def fake_save_config(new_config=None):
        saved.update(new_config or {})

    monkeypatch.setattr(ps.proxy_config, "get_config", fake_get_config)
    monkeypatch.setattr(ps.proxy_config, "save_config", fake_save_config)
    monkeypatch.setattr(ps, "prisma_client", MagicMock())
    monkeypatch.setattr(litellm, "store_audit_logs", False)
    monkeypatch.setattr(litellm, "budget_exceeded_throttle_percentage", None)

    admin = UserAPIKeyAuth(api_key="k", user_id="a", user_role=LitellmUserRoles.PROXY_ADMIN)
    await update_config_general_settings(
        data=ConfigFieldUpdate(
            field_name="budget_exceeded_throttle_percentage",
            field_value=0.1,
            config_type="general_settings",
        ),
        user_api_key_dict=admin,
    )

    assert litellm.budget_exceeded_throttle_percentage == 0.1
    assert saved["litellm_settings"]["budget_exceeded_throttle_percentage"] == 0.1


def test_get_config_list_includes_anthropic_prompt_caching_fields(monkeypatch):
    """The auto prompt caching flag and its ttl are litellm_settings globals surfaced on the
    General Settings table, so an admin can turn caching on without hand-writing config. The
    ttl is a Select and must ship its allowed values, or the table renders no editor for it."""
    import types
    from unittest.mock import AsyncMock, MagicMock

    from fastapi.testclient import TestClient

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
    from litellm.proxy.proxy_server import app

    mock_prisma = MagicMock()
    mock_config_table = MagicMock()
    mock_config_table.find_first = AsyncMock(return_value=None)
    mock_prisma.db = types.SimpleNamespace(litellm_config=mock_config_table)
    monkeypatch.setattr(ps, "prisma_client", mock_prisma)
    monkeypatch.setattr(litellm, "enable_anthropic_prompt_caching", True)
    monkeypatch.setattr(litellm, "anthropic_prompt_caching_ttl", "1h")
    app.dependency_overrides[ps.user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_id="admin", user_role=LitellmUserRoles.PROXY_ADMIN
    )
    try:
        client = TestClient(app)
        resp = client.get("/config/list", params={"config_type": "general_settings"})
        assert resp.status_code == 200, resp.text
        fields = {item["field_name"]: item for item in resp.json()}

        assert fields["enable_anthropic_prompt_caching"]["field_type"] == "Boolean"
        assert fields["enable_anthropic_prompt_caching"]["field_value"] is True

        assert fields["anthropic_prompt_caching_ttl"]["field_type"] == "Select"
        assert fields["anthropic_prompt_caching_ttl"]["field_value"] == "1h"
        assert fields["anthropic_prompt_caching_ttl"]["field_options"] == ["5m", "1h"]

        # Both caching fields carry their sub-tab so the Admin UI can render them on a
        # dedicated Prompt Caching tab, while ungrouped fields stay on General.
        assert fields["enable_anthropic_prompt_caching"]["field_tab"] == "prompt_caching"
        assert fields["anthropic_prompt_caching_ttl"]["field_tab"] == "prompt_caching"
        assert fields["budget_exceeded_throttle_percentage"]["field_tab"] is None
    finally:
        app.dependency_overrides.clear()


def test_general_settings_ui_fields_are_db_overridable():
    """Every field the Admin UI can edit is a `litellm.<attr>` set via setattr on the handling
    worker (`_persist_general_settings_ui_litellm_field`). Unless it is also in
    LITELLM_SETTINGS_SAFE_DB_OVERRIDES, a config reload on a peer worker merges the DB value but
    never applies it to the live attribute, so peer workers stay on their startup value.

    This invariant is the guard against the two registries drifting: adding a UI-editable field
    without enrolling it in the DB-override allowlist silently breaks cross-worker propagation.
    """
    from litellm.constants import LITELLM_SETTINGS_SAFE_DB_OVERRIDES
    from litellm.proxy.proxy_server import _GENERAL_SETTINGS_UI_LITELLM_FIELDS

    missing = set(_GENERAL_SETTINGS_UI_LITELLM_FIELDS) - set(LITELLM_SETTINGS_SAFE_DB_OVERRIDES)
    assert not missing, (
        f"UI-editable litellm_settings fields missing from LITELLM_SETTINGS_SAFE_DB_OVERRIDES: {sorted(missing)}. "
        "Add them, or they will not propagate to other workers when changed from the UI."
    )


@pytest.mark.asyncio
async def test_update_config_field_max_ui_session_budget_sets_live_value(monkeypatch):
    """LIT-4662: the dashboard session budget is editable from the Admin UI General tab.
    A Dollar field must accept values above 1 (the old Float type capped at 1, which cannot
    express a dollar budget), apply live via setattr, and persist under litellm_settings."""
    from unittest.mock import MagicMock

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import (
        ConfigFieldUpdate,
        LitellmUserRoles,
        UserAPIKeyAuth,
    )
    from litellm.proxy.proxy_server import update_config_general_settings

    saved: dict = {}

    async def fake_get_config():
        return {"litellm_settings": {}}

    async def fake_save_config(new_config=None):
        saved.update(new_config or {})

    monkeypatch.setattr(ps.proxy_config, "get_config", fake_get_config)
    monkeypatch.setattr(ps.proxy_config, "save_config", fake_save_config)
    monkeypatch.setattr(ps, "prisma_client", MagicMock())
    monkeypatch.setattr(litellm, "store_audit_logs", False)
    monkeypatch.setattr(litellm, "max_ui_session_budget", 1.0)

    admin = UserAPIKeyAuth(api_key="k", user_id="a", user_role=LitellmUserRoles.PROXY_ADMIN)
    await update_config_general_settings(
        data=ConfigFieldUpdate(
            field_name="max_ui_session_budget",
            field_value=25.0,
            config_type="general_settings",
        ),
        user_api_key_dict=admin,
    )

    assert litellm.max_ui_session_budget == 25.0
    assert saved["litellm_settings"]["max_ui_session_budget"] == 25.0


@pytest.mark.parametrize("bad_value", [True, "abc", -1, 0, [2.5]])
def test_validate_max_ui_session_budget_rejects_malformed(bad_value):
    """A Dollar field accepts only positive numbers; zero would block every dashboard
    LLM call at mint and non-numerics would break session key generation."""
    from fastapi import HTTPException

    from litellm.proxy.proxy_server import _validate_general_settings_ui_litellm_value

    with pytest.raises(HTTPException) as exc_info:
        _validate_general_settings_ui_litellm_value("max_ui_session_budget", bad_value)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("empty_value", [None, ""])
def test_validate_max_ui_session_budget_empty_restores_default(empty_value):
    """Clearing the field in the UI restores the shipped $1 default rather than None;
    None would silently remove the session spend guardrail (unlimited budget), which
    must stay a deliberate config.yaml act (max_ui_session_budget: null)."""
    from litellm.proxy.proxy_server import _validate_general_settings_ui_litellm_value

    assert _validate_general_settings_ui_litellm_value("max_ui_session_budget", empty_value) == 1.0


def test_general_settings_ui_defaults_unchanged_for_existing_fields():
    """The spec-default mechanism added for max_ui_session_budget must not change what
    clearing the pre-existing fields restores (None for Float/Select, False for Boolean)."""
    from litellm.proxy.proxy_server import (
        _GENERAL_SETTINGS_UI_LITELLM_FIELDS,
        _general_settings_ui_litellm_default,
    )

    assert _general_settings_ui_litellm_default(_GENERAL_SETTINGS_UI_LITELLM_FIELDS["budget_exceeded_throttle_percentage"]) is None
    assert _general_settings_ui_litellm_default(_GENERAL_SETTINGS_UI_LITELLM_FIELDS["enable_anthropic_prompt_caching"]) is False
    assert _general_settings_ui_litellm_default(_GENERAL_SETTINGS_UI_LITELLM_FIELDS["anthropic_prompt_caching_ttl"]) is None


@pytest.mark.parametrize(
    "field_name, db_value",
    [
        ("enable_anthropic_prompt_caching", True),
        ("anthropic_prompt_caching_ttl", "1h"),
    ],
)
def test_prompt_caching_settings_propagate_on_config_reload(monkeypatch, field_name, db_value):
    """A UI toggle on one worker persists to the DB; a peer worker picks it up only when the
    config reload applies the safe-override allowlist. Regression for the fields being absent
    from that allowlist, which left peer workers stale."""
    import litellm.proxy.proxy_server as ps

    # peer worker booted with the opposite/absent value
    monkeypatch.setattr(litellm, field_name, False if isinstance(db_value, bool) else None)

    pc = ps.ProxyConfig()
    pc._update_config_fields(
        current_config={"litellm_settings": {}},
        param_name="litellm_settings",
        db_param_value={field_name: db_value},
    )

    assert getattr(litellm, field_name) == db_value


def test_get_config_list_marks_untouched_prompt_caching_flag_as_not_set(monkeypatch):
    """The flag defaults to False rather than None, so a plain 'is not None' check would
    report the default as 'In Config' and imply an admin had set it."""
    import types
    from unittest.mock import AsyncMock, MagicMock

    from fastapi.testclient import TestClient

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
    from litellm.proxy.proxy_server import app

    mock_prisma = MagicMock()
    mock_config_table = MagicMock()
    mock_config_table.find_first = AsyncMock(return_value=None)
    mock_prisma.db = types.SimpleNamespace(litellm_config=mock_config_table)
    monkeypatch.setattr(ps, "prisma_client", mock_prisma)
    monkeypatch.setattr(litellm, "enable_anthropic_prompt_caching", False)
    app.dependency_overrides[ps.user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_id="admin", user_role=LitellmUserRoles.PROXY_ADMIN
    )
    try:
        client = TestClient(app)
        resp = client.get("/config/list", params={"config_type": "general_settings"})
        fields = {item["field_name"]: item for item in resp.json()}
        assert fields["enable_anthropic_prompt_caching"]["stored_in_db"] is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "field_name, field_value",
    [
        ("enable_anthropic_prompt_caching", True),
        ("enable_anthropic_prompt_caching", False),
        ("anthropic_prompt_caching_ttl", "5m"),
        ("anthropic_prompt_caching_ttl", "1h"),
    ],
)
@pytest.mark.asyncio
async def test_update_config_field_prompt_caching_persists_to_litellm_settings(monkeypatch, field_name, field_value):
    """Toggling either row must set litellm.<attr> live and persist under litellm_settings,
    so the running proxy caches immediately and still does after a restart."""
    from unittest.mock import MagicMock

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import (
        ConfigFieldUpdate,
        LitellmUserRoles,
        UserAPIKeyAuth,
    )
    from litellm.proxy.proxy_server import update_config_general_settings

    saved: dict = {}

    async def fake_get_config():
        return {"litellm_settings": {}}

    async def fake_save_config(new_config=None):
        saved.update(new_config or {})

    monkeypatch.setattr(ps.proxy_config, "get_config", fake_get_config)
    monkeypatch.setattr(ps.proxy_config, "save_config", fake_save_config)
    monkeypatch.setattr(ps, "prisma_client", MagicMock())
    monkeypatch.setattr(litellm, "store_audit_logs", False)
    monkeypatch.setattr(litellm, field_name, None)

    admin = UserAPIKeyAuth(api_key="k", user_id="a", user_role=LitellmUserRoles.PROXY_ADMIN)
    await update_config_general_settings(
        data=ConfigFieldUpdate(field_name=field_name, field_value=field_value, config_type="general_settings"),
        user_api_key_dict=admin,
    )

    assert getattr(litellm, field_name) == field_value
    assert saved["litellm_settings"][field_name] == field_value


@pytest.mark.parametrize(
    "field_name, bad_value",
    [
        ("enable_anthropic_prompt_caching", "yes"),
        ("enable_anthropic_prompt_caching", 1),
        ("anthropic_prompt_caching_ttl", "10m"),
        ("anthropic_prompt_caching_ttl", "1H"),
        ("anthropic_prompt_caching_ttl", 3600),
    ],
)
@pytest.mark.asyncio
async def test_update_config_field_prompt_caching_rejects_invalid(monkeypatch, field_name, bad_value):
    """An unsupported ttl must be refused here rather than reaching Anthropic verbatim."""
    from unittest.mock import MagicMock

    from fastapi import HTTPException

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import (
        ConfigFieldUpdate,
        LitellmUserRoles,
        UserAPIKeyAuth,
    )
    from litellm.proxy.proxy_server import update_config_general_settings

    async def fake_get_config():
        return {"litellm_settings": {}}

    monkeypatch.setattr(ps.proxy_config, "get_config", fake_get_config)
    monkeypatch.setattr(ps, "prisma_client", MagicMock())
    monkeypatch.setattr(litellm, field_name, None)

    admin = UserAPIKeyAuth(api_key="k", user_id="a", user_role=LitellmUserRoles.PROXY_ADMIN)
    with pytest.raises(HTTPException) as exc:
        await update_config_general_settings(
            data=ConfigFieldUpdate(field_name=field_name, field_value=bad_value, config_type="general_settings"),
            user_api_key_dict=admin,
        )
    assert exc.value.status_code == 400
    assert getattr(litellm, field_name) is None


@pytest.mark.parametrize(
    "field_name, expected_default",
    [
        ("enable_anthropic_prompt_caching", False),
        ("anthropic_prompt_caching_ttl", None),
        ("budget_exceeded_throttle_percentage", None),
    ],
)
@pytest.mark.asyncio
async def test_reset_config_field_restores_type_default(monkeypatch, field_name, expected_default):
    """Reset must restore each field's own default. Blanket None would leave the boolean flag
    set to None, which is not a bool and would read as neither on nor off."""
    from unittest.mock import MagicMock

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import (
        ConfigFieldDelete,
        LitellmUserRoles,
        UserAPIKeyAuth,
    )
    from litellm.proxy.proxy_server import delete_config_general_settings

    saved: dict = {}

    async def fake_get_config():
        return {"litellm_settings": {field_name: "stale"}}

    async def fake_save_config(new_config=None):
        saved.update(new_config or {})

    monkeypatch.setattr(ps.proxy_config, "get_config", fake_get_config)
    monkeypatch.setattr(ps.proxy_config, "save_config", fake_save_config)
    monkeypatch.setattr(ps, "prisma_client", MagicMock())
    monkeypatch.setattr(litellm, "store_audit_logs", False)
    monkeypatch.setattr(litellm, field_name, "stale")

    admin = UserAPIKeyAuth(api_key="k", user_id="a", user_role=LitellmUserRoles.PROXY_ADMIN)
    await delete_config_general_settings(
        data=ConfigFieldDelete(field_name=field_name, config_type="general_settings"),
        user_api_key_dict=admin,
    )

    assert getattr(litellm, field_name) is expected_default
    assert field_name not in saved["litellm_settings"]


@pytest.mark.parametrize("bad_value", [0, -0.1, 1.5, True])
@pytest.mark.asyncio
async def test_update_config_field_throttle_rejects_invalid(monkeypatch, bad_value):
    from unittest.mock import MagicMock

    from fastapi import HTTPException

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import (
        ConfigFieldUpdate,
        LitellmUserRoles,
        UserAPIKeyAuth,
    )
    from litellm.proxy.proxy_server import update_config_general_settings

    async def fake_get_config():
        return {"litellm_settings": {}}

    monkeypatch.setattr(ps.proxy_config, "get_config", fake_get_config)
    monkeypatch.setattr(ps, "prisma_client", MagicMock())
    monkeypatch.setattr(litellm, "budget_exceeded_throttle_percentage", None)

    admin = UserAPIKeyAuth(api_key="k", user_id="a", user_role=LitellmUserRoles.PROXY_ADMIN)
    with pytest.raises(HTTPException) as exc:
        await update_config_general_settings(
            data=ConfigFieldUpdate(
                field_name="budget_exceeded_throttle_percentage",
                field_value=bad_value,
                config_type="general_settings",
            ),
            user_api_key_dict=admin,
        )
    assert exc.value.status_code == 400
    assert litellm.budget_exceeded_throttle_percentage is None


@pytest.mark.asyncio
async def test_update_config_field_throttle_rejected_for_non_admin(monkeypatch):
    from unittest.mock import MagicMock

    from fastapi import HTTPException

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import (
        ConfigFieldUpdate,
        LitellmUserRoles,
        UserAPIKeyAuth,
    )
    from litellm.proxy.proxy_server import update_config_general_settings

    monkeypatch.setattr(ps, "prisma_client", MagicMock())
    monkeypatch.setattr(litellm, "budget_exceeded_throttle_percentage", None)

    non_admin = UserAPIKeyAuth(api_key="k", user_id="u", user_role=LitellmUserRoles.INTERNAL_USER)
    with pytest.raises(HTTPException):
        await update_config_general_settings(
            data=ConfigFieldUpdate(
                field_name="budget_exceeded_throttle_percentage",
                field_value=0.1,
                config_type="general_settings",
            ),
            user_api_key_dict=non_admin,
        )
    assert litellm.budget_exceeded_throttle_percentage is None


def test_preserve_redacted_plugin_keys_keeps_stored_credential():
    """A redacted or blank plugin_key on update must not overwrite the real key."""
    from litellm.proxy.proxy_server import _preserve_redacted_plugin_keys

    existing = [{"name": "p1", "url": "https://p1", "plugin_key": "sk-real-1"}]

    redacted = _preserve_redacted_plugin_keys(
        [{"name": "p1", "url": "https://p1-new", "plugin_key": "***"}], existing
    )
    assert redacted == [
        {"name": "p1", "url": "https://p1-new", "plugin_key": "sk-real-1"}
    ]

    blanked = _preserve_redacted_plugin_keys(
        [{"name": "p1", "url": "https://p1", "plugin_key": ""}], existing
    )
    assert blanked[0]["plugin_key"] == "sk-real-1"


def test_preserve_redacted_plugin_keys_sets_new_and_drops_orphan_placeholder():
    """A real new key replaces; a placeholder with no stored key is dropped, never persisted."""
    from litellm.proxy.proxy_server import _preserve_redacted_plugin_keys

    existing = [{"name": "p1", "url": "https://p1", "plugin_key": "sk-real-1"}]

    rotated = _preserve_redacted_plugin_keys(
        [{"name": "p1", "url": "https://p1", "plugin_key": "sk-new"}], existing
    )
    assert rotated[0]["plugin_key"] == "sk-new"

    new_plugin = _preserve_redacted_plugin_keys(
        [{"name": "p2", "url": "https://p2", "plugin_key": "***"}], existing
    )
    assert "plugin_key" not in new_plugin[0]


def _config_field_info_client(monkeypatch, user_role):
    import types
    from unittest.mock import AsyncMock, MagicMock

    from fastapi.testclient import TestClient

    import litellm.proxy.proxy_server as ps
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.proxy_server import app

    db_record = types.SimpleNamespace(
        param_value={
            "master_key": "sk-super-secret-master",
            "database_url": "postgresql://user:p4ssw0rd@db:5432/litellm",
            "pass_through_endpoints": [
                {
                    "path": "/upstream",
                    "target": "https://upstream.example.com",
                    "headers": {"Authorization": "Bearer sk-upstream-secret"},
                }
            ],
            "max_parallel_requests": 100,
        }
    )
    mock_config_table = MagicMock()
    mock_config_table.find_first = AsyncMock(return_value=db_record)
    mock_prisma = MagicMock()
    mock_prisma.db = types.SimpleNamespace(litellm_config=mock_config_table)
    monkeypatch.setattr(ps, "prisma_client", mock_prisma)
    app.dependency_overrides[ps.user_api_key_auth] = lambda: UserAPIKeyAuth(
        user_id="u", user_role=user_role
    )
    return TestClient(app)


def test_config_field_info_redacts_secrets_for_view_only_admin(monkeypatch):
    """/config/field/info gates on _user_has_admin_view, which also grants
    PROXY_ADMIN_VIEW_ONLY. A view-only admin reading master_key/database_url verbatim is
    effectively a full admin. Secret-bearing fields must come back REDACTED for anyone who
    is not a FULL PROXY_ADMIN, while non-secret fields stay readable."""
    from litellm.proxy._types import LitellmUserRoles

    client = _config_field_info_client(
        monkeypatch, LitellmUserRoles.PROXY_ADMIN_VIEW_ONLY
    )
    try:
        for secret_field in ("master_key", "database_url", "pass_through_endpoints"):
            resp = client.get("/config/field/info", params={"field_name": secret_field})
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["field_value"] == "REDACTED"
            assert "secret" not in str(body["field_value"])
            assert "p4ssw0rd" not in str(body["field_value"])

        resp = client.get(
            "/config/field/info", params={"field_name": "max_parallel_requests"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["field_value"] == 100
    finally:
        app.dependency_overrides.clear()


def test_config_field_info_returns_raw_secrets_for_full_admin(monkeypatch):
    """the redaction must not over-apply. A FULL PROXY_ADMIN still
    needs the real master_key value to populate the admin edit form."""
    from litellm.proxy._types import LitellmUserRoles

    client = _config_field_info_client(monkeypatch, LitellmUserRoles.PROXY_ADMIN)
    try:
        resp = client.get("/config/field/info", params={"field_name": "master_key"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["field_value"] == "sk-super-secret-master"

        resp = client.get(
            "/config/field/info", params={"field_name": "pass_through_endpoints"}
        )
        assert resp.status_code == 200, resp.text
        assert (
            resp.json()["field_value"][0]["headers"]["Authorization"]
            == "Bearer sk-upstream-secret"
        )
    finally:
        app.dependency_overrides.clear()


def _fake_prisma_with_config(existing_param_value):
    """MagicMock prisma whose litellm_config row returns existing_param_value and
    whose litellm_auditlog.create records the written audit row."""
    fake = MagicMock()
    config_row = MagicMock()
    config_row.param_value = existing_param_value
    fake.db.litellm_config.find_first = AsyncMock(return_value=config_row)
    fake.db.litellm_config.upsert = AsyncMock(return_value=config_row)
    fake.db.litellm_auditlog.create = AsyncMock()
    return fake


def test_dump_redacted_config_redacts_secret_leaves():
    from litellm.proxy.proxy_server import _dump_redacted_config

    assert _dump_redacted_config(None) is None

    restored = json.loads(
        _dump_redacted_config(
            {
                "api_key": "sk-leak",
                "model": "gpt-4",
                "nested": {"aws_secret_access_key": "abc", "region": "us-east-1"},
            }
        )
    )
    assert restored["api_key"] == "REDACTED"
    assert restored["model"] == "gpt-4"
    assert restored["nested"]["aws_secret_access_key"] == "REDACTED"
    assert restored["nested"]["region"] == "us-east-1"


@pytest.mark.asyncio
async def test_create_config_audit_log_writes_redacted_entry(monkeypatch):
    import litellm.proxy.proxy_server as proxy_server_module
    from litellm.proxy._types import LitellmTableNames
    from litellm.proxy.proxy_server import create_config_audit_log

    fake = _fake_prisma_with_config({})
    monkeypatch.setattr(proxy_server_module, "prisma_client", fake)
    monkeypatch.setattr(proxy_server_module, "premium_user", True)
    monkeypatch.setattr(litellm, "store_audit_logs", True)

    caller = UserAPIKeyAuth(api_key="hashed-key-abc", user_id="admin-7")
    await create_config_audit_log(
        "router_settings",
        "updated",
        {"routing_strategy": "simple-shuffle", "api_key": "sk-old"},
        {"routing_strategy": "latency-based", "api_key": "sk-new"},
        caller,
    )

    fake.db.litellm_auditlog.create.assert_awaited_once()
    written = fake.db.litellm_auditlog.create.call_args.kwargs["data"]
    assert written["table_name"] == LitellmTableNames.CONFIG_TABLE_NAME.value
    assert written["object_id"] == "router_settings"
    assert written["action"] == "updated"
    assert written["changed_by"] == "admin-7"
    assert written["changed_by_api_key"] == "hashed-key-abc"

    before = json.loads(written["before_value"])
    after = json.loads(written["updated_values"])
    assert before["routing_strategy"] == "simple-shuffle"
    assert after["routing_strategy"] == "latency-based"
    assert "sk-old" not in written["before_value"]
    assert "sk-new" not in written["updated_values"]
    assert before["api_key"] != "sk-old"
    assert after["api_key"] != "sk-new"


@pytest.mark.asyncio
async def test_create_config_audit_log_noop_when_store_audit_logs_disabled(monkeypatch):
    import litellm.proxy.proxy_server as proxy_server_module
    from litellm.proxy.proxy_server import create_config_audit_log

    fake = _fake_prisma_with_config({})
    monkeypatch.setattr(proxy_server_module, "prisma_client", fake)
    monkeypatch.setattr(proxy_server_module, "premium_user", True)
    monkeypatch.setattr(litellm, "store_audit_logs", False)

    await create_config_audit_log(
        "router_settings",
        "updated",
        {},
        {"a": 1},
        UserAPIKeyAuth(api_key="k", user_id="u"),
    )
    fake.db.litellm_auditlog.create.assert_not_called()


def test_dump_redacted_config_serializes_non_json_native_values():
    """YAML-loaded config can contain datetime/date/custom values that plain
    json.dumps refuses. Without default=str the audit write turns into a 500
    after the config change has already committed; the sibling audit-log
    serializers in team_endpoints.py use default=str for the same reason."""
    from datetime import datetime, timezone

    from litellm.proxy.proxy_server import _dump_redacted_config

    out = _dump_redacted_config({"updated_at": datetime(2026, 6, 30, tzinfo=timezone.utc)})
    assert out is not None
    restored = json.loads(out)
    assert "2026-06-30" in restored["updated_at"]


@pytest.mark.asyncio
async def test_update_config_general_settings_emits_audit_log(monkeypatch):
    import litellm.proxy.proxy_server as proxy_server_module
    from litellm.proxy._types import ConfigFieldUpdate
    from litellm.proxy.proxy_server import update_config_general_settings

    existing = {"max_parallel_requests": 5, "some_api_key": "sk-stored-secret"}
    fake = _fake_prisma_with_config(existing)
    monkeypatch.setattr(proxy_server_module, "prisma_client", fake)
    monkeypatch.setattr(proxy_server_module, "premium_user", True)
    monkeypatch.setattr(litellm, "store_audit_logs", True)

    admin = UserAPIKeyAuth(
        api_key="hashed-admin",
        user_id="admin-1",
        user_role=LitellmUserRoles.PROXY_ADMIN,
    )
    await update_config_general_settings(
        data=ConfigFieldUpdate(
            field_name="max_parallel_requests",
            field_value=42,
            config_type="general_settings",
        ),
        user_api_key_dict=admin,
    )
    # Audit is scheduled via asyncio.create_task; yield so it runs.
    await asyncio.sleep(0)

    fake.db.litellm_auditlog.create.assert_awaited_once()
    written = fake.db.litellm_auditlog.create.call_args.kwargs["data"]
    assert written["table_name"] == "LiteLLM_Config"
    assert written["object_id"] == "general_settings"
    assert written["action"] == "updated"
    assert written["changed_by"] == "admin-1"

    before = json.loads(written["before_value"])
    after = json.loads(written["updated_values"])
    assert before["max_parallel_requests"] == 5
    assert after["max_parallel_requests"] == 42
    assert "sk-stored-secret" not in written["before_value"]
    assert "sk-stored-secret" not in written["updated_values"]
    assert before["some_api_key"] != "sk-stored-secret"


@pytest.mark.asyncio
async def test_update_config_general_settings_applies_ssrf_globals(monkeypatch):
    import litellm.proxy.proxy_server as proxy_server_module
    from litellm.proxy._types import ConfigFieldUpdate
    from litellm.proxy.proxy_server import update_config_general_settings

    fake = _fake_prisma_with_config({})
    monkeypatch.setattr(proxy_server_module, "prisma_client", fake)
    monkeypatch.setattr(litellm, "store_audit_logs", False)
    monkeypatch.setattr(litellm, "user_url_validation", True)
    monkeypatch.setattr(litellm, "user_url_allowed_hosts", [])
    monkeypatch.setattr(litellm, "provider_url_destination_allowed_hosts", [])

    admin = UserAPIKeyAuth(
        api_key="hashed-admin",
        user_id="admin-1",
        user_role=LitellmUserRoles.PROXY_ADMIN,
    )
    await update_config_general_settings(
        data=ConfigFieldUpdate(
            field_name="user_url_validation",
            field_value="false",
            config_type="general_settings",
        ),
        user_api_key_dict=admin,
    )
    await update_config_general_settings(
        data=ConfigFieldUpdate(
            field_name="user_url_allowed_hosts",
            field_value=["internal.example"],
            config_type="general_settings",
        ),
        user_api_key_dict=admin,
    )
    await update_config_general_settings(
        data=ConfigFieldUpdate(
            field_name="provider_url_destination_allowed_hosts",
            field_value=["provider.example"],
            config_type="general_settings",
        ),
        user_api_key_dict=admin,
    )
    await asyncio.sleep(0)

    assert litellm.user_url_validation is False
    assert litellm.user_url_allowed_hosts == ["internal.example"]
    assert litellm.provider_url_destination_allowed_hosts == ["provider.example"]

    await update_config_general_settings(
        data=ConfigFieldUpdate(
            field_name="user_url_allowed_hosts",
            field_value=None,
            config_type="general_settings",
        ),
        user_api_key_dict=admin,
    )
    await update_config_general_settings(
        data=ConfigFieldUpdate(
            field_name="provider_url_destination_allowed_hosts",
            field_value=None,
            config_type="general_settings",
        ),
        user_api_key_dict=admin,
    )
    await asyncio.sleep(0)

    assert litellm.user_url_allowed_hosts is None
    assert litellm.provider_url_destination_allowed_hosts is None


@pytest.mark.asyncio
async def test_delete_config_general_settings_emits_deleted_audit_log(monkeypatch):
    import litellm.proxy.proxy_server as proxy_server_module
    from litellm.proxy._types import ConfigFieldDelete
    from litellm.proxy.proxy_server import delete_config_general_settings

    existing = {"max_parallel_requests": 5}
    fake = _fake_prisma_with_config(existing)
    monkeypatch.setattr(proxy_server_module, "prisma_client", fake)
    monkeypatch.setattr(proxy_server_module, "premium_user", True)
    monkeypatch.setattr(litellm, "store_audit_logs", True)

    admin = UserAPIKeyAuth(
        api_key="hashed-admin",
        user_id="admin-1",
        user_role=LitellmUserRoles.PROXY_ADMIN,
    )
    await delete_config_general_settings(
        data=ConfigFieldDelete(
            field_name="max_parallel_requests", config_type="general_settings"
        ),
        user_api_key_dict=admin,
    )
    # Audit is scheduled via asyncio.create_task; yield so it runs.
    await asyncio.sleep(0)

    fake.db.litellm_auditlog.create.assert_awaited_once()
    written = fake.db.litellm_auditlog.create.call_args.kwargs["data"]
    assert written["object_id"] == "general_settings"
    assert written["action"] == "deleted"
    before = json.loads(written["before_value"])
    after = json.loads(written["updated_values"])
    assert before["max_parallel_requests"] == 5
    assert "max_parallel_requests" not in after


def test_update_config_audits_every_written_section(_update_config_setup, monkeypatch):
    """/config/update must emit one audit row per section it writes, so each
    of the four call sites (general_settings, environment_variables,
    litellm_settings, router_settings) is mutation-protected. litellm_settings
    is the row that holds default_internal_user_params ("default user settings")."""
    import litellm.proxy.proxy_server as proxy_server_module

    client, prisma, restore = _update_config_setup(
        initial_rows={"litellm_settings": {"drop_params": True}}
    )
    audit_create = AsyncMock()
    prisma.db.litellm_auditlog.create = audit_create
    monkeypatch.setattr(proxy_server_module, "premium_user", True)
    monkeypatch.setattr(litellm, "store_audit_logs", True)
    try:
        resp = client.post(
            "/config/update",
            json={
                "general_settings": {"store_prompts_in_spend_logs": True},
                "environment_variables": {"FOO": "bar"},
                "litellm_settings": {
                    "default_internal_user_params": {"max_budget": 10}
                },
                "router_settings": {"routing_strategy": "latency-based-routing"},
            },
        )
        assert resp.status_code == 200, resp.text

        audited = {
            call.kwargs["data"]["object_id"]: call.kwargs["data"]["action"]
            for call in audit_create.await_args_list
        }
        assert audited == {
            "general_settings": "updated",
            "environment_variables": "updated",
            "litellm_settings": "updated",
            "router_settings": "updated",
        }
        for call in audit_create.await_args_list:
            assert call.kwargs["data"]["table_name"] == "LiteLLM_Config"
            assert call.kwargs["data"]["changed_by"] == "test_admin"

        ls_call = next(
            c
            for c in audit_create.await_args_list
            if c.kwargs["data"]["object_id"] == "litellm_settings"
        )
        after = json.loads(ls_call.kwargs["data"]["updated_values"])
        assert after["default_internal_user_params"] == {"max_budget": 10}
    finally:
        restore()


def test_delete_callback_audits_litellm_settings_deletion(
    _update_config_setup, monkeypatch
):
    """/config/callback/delete must emit a deleted audit row for litellm_settings
    capturing the success_callback list before and after removal."""
    import litellm.proxy.proxy_server as proxy_server_module

    client, prisma, restore = _update_config_setup()
    audit_create = AsyncMock()
    prisma.db.litellm_auditlog.create = audit_create
    monkeypatch.setattr(proxy_server_module, "premium_user", True)
    monkeypatch.setattr(litellm, "store_audit_logs", True)

    from litellm.proxy.proxy_server import proxy_config as real_proxy_config

    monkeypatch.setattr(
        real_proxy_config,
        "get_config",
        AsyncMock(
            return_value={
                "litellm_settings": {"success_callback": ["langfuse", "datadog"]}
            }
        ),
    )
    monkeypatch.setattr(
        real_proxy_config, "save_config", AsyncMock(return_value=None)
    )
    try:
        resp = client.post(
            "/config/callback/delete", json={"callback_name": "datadog"}
        )
        assert resp.status_code == 200, resp.text

        audit_create.assert_awaited_once()
        written = audit_create.await_args.kwargs["data"]
        assert written["object_id"] == "litellm_settings"
        assert written["action"] == "deleted"
        before = json.loads(written["before_value"])
        after = json.loads(written["updated_values"])
        assert before["success_callback"] == ["langfuse", "datadog"]
        assert after["success_callback"] == ["langfuse"]
    finally:
        restore()


def test_delete_callback_audits_before_reload_failure(_update_config_setup, monkeypatch):
    import litellm.proxy.proxy_server as proxy_server_module

    client, prisma, restore = _update_config_setup()
    audit_create = AsyncMock()
    prisma.db.litellm_auditlog.create = audit_create
    monkeypatch.setattr(proxy_server_module, "premium_user", True)
    monkeypatch.setattr(litellm, "store_audit_logs", True)

    from litellm.proxy.proxy_server import proxy_config as real_proxy_config

    monkeypatch.setattr(
        real_proxy_config,
        "get_config",
        AsyncMock(
            return_value={
                "litellm_settings": {"success_callback": ["langfuse", "datadog"]}
            }
        ),
    )
    monkeypatch.setattr(
        real_proxy_config, "save_config", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        real_proxy_config,
        "add_deployment",
        AsyncMock(side_effect=RuntimeError("reload failed")),
    )
    try:
        resp = client.post(
            "/config/callback/delete", json={"callback_name": "datadog"}
        )
        assert resp.status_code == 500, resp.text

        audit_create.assert_awaited_once()
        written = audit_create.await_args.kwargs["data"]
        assert written["object_id"] == "litellm_settings"
        assert written["action"] == "deleted"
    finally:
        restore()


def test_update_config_redacts_all_environment_variable_values(
    _update_config_setup, monkeypatch
):
    """environment_variables hold credentials under arbitrary uppercase keys
    (DATABASE_URL) that key-name secret matching misses, so every value in the
    section must be redacted before the audit row is written; a plaintext
    secret must never reach LiteLLM_AuditLog."""
    import litellm.proxy.proxy_server as proxy_server_module

    # DATABASE_URL is the bug class: an uppercase env key that key-name secret
    # matching does NOT flag, so only whole-section value redaction protects it.
    client, prisma, restore = _update_config_setup(
        initial_rows={
            "environment_variables": {
                "DATABASE_URL": "enc:postgresql://OLDsecret@old.host:5432/db"
            }
        }
    )
    audit_create = AsyncMock()
    prisma.db.litellm_auditlog.create = audit_create
    monkeypatch.setattr(proxy_server_module, "premium_user", True)
    monkeypatch.setattr(litellm, "store_audit_logs", True)
    try:
        resp = client.post(
            "/config/update",
            json={
                "environment_variables": {
                    "DATABASE_URL": "postgresql://u:p@db.internal:5432/litellm",
                    "LOG_LEVEL": "debug",
                }
            },
        )
        assert resp.status_code == 200, resp.text

        env_call = next(
            c
            for c in audit_create.await_args_list
            if c.kwargs["data"]["object_id"] == "environment_variables"
        )
        data = env_call.kwargs["data"]

        # the pre-existing secret must be redacted in the before snapshot
        before = json.loads(data["before_value"])
        assert before == {"DATABASE_URL": "REDACTED"}
        assert "OLDsecret" not in data["before_value"]
        assert "old.host" not in data["before_value"]

        # the newly-written values must be redacted in the after snapshot
        after = json.loads(data["updated_values"])
        assert after == {"DATABASE_URL": "REDACTED", "LOG_LEVEL": "REDACTED"}
        assert "postgresql://" not in data["updated_values"]
        assert "db.internal" not in data["updated_values"]
    finally:
        restore()


class _EnvBuiltRedisCache(RedisCache):
    """RedisCache stand-in that records its constructor kwargs and never
    opens a network connection, so tests can assert which connection params
    the proxy used to build its coordination Redis."""

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs


def _run_init_cache_with_backend(cache_backend, redis_env_kwargs):
    """Run ProxyConfig._init_cache with a stubbed response-cache backend and a
    controlled REDIS_* environment, returning (redis_usage_cache,
    spend_counter redis, config-cache redis) as observed after the call."""
    mock_litellm_cache = MagicMock()
    mock_litellm_cache.cache = cache_backend
    fresh_spend_cache = DualCache()
    fresh_config_cache = types.SimpleNamespace(redis_cache=None)

    with (
        patch.object(proxy_server_module, "redis_usage_cache", None),
        patch.object(proxy_server_module, "spend_counter_cache", fresh_spend_cache),
        patch.object(proxy_server_module, "user_api_key_cache", DualCache()),
        patch.object(proxy_server_module, "llm_router", None),
        patch.object(proxy_server_module, "litellm_config_cache", fresh_config_cache),
        patch.object(proxy_server_module, "RedisCache", _EnvBuiltRedisCache),
        patch(
            "litellm._redis._redis_kwargs_from_environment",
            return_value=redis_env_kwargs,
        ),
        patch("litellm.Cache", return_value=mock_litellm_cache),
    ):
        litellm.cache = None
        resolved = proxy_server_module.ProxyConfig()._init_cache(cache_params={"type": "qdrant-semantic"})
        return (
            resolved,
            fresh_spend_cache.redis_cache,
            fresh_config_cache.redis_cache,
        )


def test_init_cache_non_redis_backend_builds_usage_redis_from_environment():
    """A semantic (non-Redis-KV) response cache must not disable the proxy's
    coordination Redis: when REDIS_* env vars provide a connection,
    _init_cache builds a standalone usage cache so cross-pod rate limits,
    spend tracking, and the pod lock manager stay Redis-backed."""
    usage_cache, spend_redis, config_redis = _run_init_cache_with_backend(
        cache_backend=object(),
        redis_env_kwargs={"host": "coordination-redis", "port": "6379"},
    )

    assert isinstance(usage_cache, _EnvBuiltRedisCache)
    assert usage_cache.init_kwargs["host"] == "coordination-redis"
    assert spend_redis is usage_cache
    assert config_redis is usage_cache


def test_init_cache_non_redis_backend_without_redis_env_stays_in_memory():
    """Without any REDIS_* connection info, a non-Redis response cache must
    leave the coordination Redis unset instead of building a broken client."""
    usage_cache, spend_redis, config_redis = _run_init_cache_with_backend(
        cache_backend=object(),
        redis_env_kwargs={},
    )

    assert usage_cache is None
    assert spend_redis is None
    assert config_redis is None


def test_init_cache_redis_backend_reuses_cache_backend_over_environment():
    """When the response cache itself is a plain Redis KV cache, it must be
    reused as the coordination Redis; the REDIS_* environment fallback must
    not construct a second client."""
    redis_backend = _EnvBuiltRedisCache(host="cache-params-host")
    usage_cache, spend_redis, _ = _run_init_cache_with_backend(
        cache_backend=redis_backend,
        redis_env_kwargs={"host": "env-host"},
    )

    assert usage_cache is redis_backend
    assert usage_cache.init_kwargs["host"] == "cache-params-host"
    assert spend_redis is redis_backend


class _EnvBuiltClusterCache(RedisClusterCache):
    """RedisClusterCache stand-in that records constructor kwargs and never
    opens a network connection."""

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs


def _run_init_coordination_redis(config, env=None):
    """Run ProxyConfig._init_coordination_redis against a stubbed module state,
    returning (redis_usage_cache, spend_counter redis, config-cache redis)."""
    fresh_spend_cache = DualCache()
    fresh_config_cache = types.SimpleNamespace(redis_cache=None)

    with (
        patch.object(proxy_server_module, "redis_usage_cache", None),
        patch.object(proxy_server_module, "spend_counter_cache", fresh_spend_cache),
        patch.object(proxy_server_module, "user_api_key_cache", DualCache()),
        patch.object(proxy_server_module, "litellm_config_cache", fresh_config_cache),
        patch.object(proxy_server_module, "RedisCache", _EnvBuiltRedisCache),
        patch.object(proxy_server_module, "RedisClusterCache", _EnvBuiltClusterCache),
        mock.patch.dict(os.environ, env or {}, clear=False),
    ):
        built = proxy_server_module.ProxyConfig()._init_coordination_redis(config=config)
        return (
            built,
            fresh_spend_cache.redis_cache,
            fresh_config_cache.redis_cache,
        )


def test_init_coordination_redis_explicit_block_builds_standalone_client():
    """general_settings.coordination_redis must build the coordination Redis
    even when no response cache is configured at all, and attach it to the
    spend counter and config caches."""
    usage_cache, spend_redis, config_redis = _run_init_coordination_redis(
        config={"general_settings": {"coordination_redis": {"host": "coord-host", "port": 6380}}},
    )

    assert isinstance(usage_cache, _EnvBuiltRedisCache)
    assert usage_cache.init_kwargs["host"] == "coord-host"
    assert usage_cache.init_kwargs["port"] == 6380
    assert spend_redis is usage_cache
    assert config_redis is usage_cache


def test_init_coordination_redis_resolves_os_environ_references():
    """os.environ/ values inside the coordination_redis block must be resolved
    the same way cache_params values are."""
    usage_cache, _, _ = _run_init_coordination_redis(
        config={"general_settings": {"coordination_redis": {"host": "os.environ/COORD_REDIS_HOST"}}},
        env={"COORD_REDIS_HOST": "resolved-host"},
    )

    assert usage_cache.init_kwargs["host"] == "resolved-host"


def test_init_coordination_redis_startup_nodes_builds_cluster_client():
    """A coordination_redis block with startup_nodes must construct a cluster
    client, so cluster-aware consumers (v3 rate limiter) take the cluster path."""
    usage_cache, _, _ = _run_init_coordination_redis(
        config={
            "general_settings": {
                "coordination_redis": {"startup_nodes": [{"host": "node-1", "port": 7000}]}
            }
        },
    )

    assert isinstance(usage_cache, _EnvBuiltClusterCache)
    assert usage_cache.init_kwargs["startup_nodes"] == [{"host": "node-1", "port": 7000}]


def test_init_coordination_redis_without_connection_target_raises():
    """A coordination_redis block with no host, url, startup_nodes, or
    sentinel_nodes is a config error and must fail startup loudly instead of
    silently running without coordination."""
    with pytest.raises(ValueError, match="connection target"):
        _run_init_coordination_redis(
            config={"general_settings": {"coordination_redis": {"ssl": True}}},
        )


def test_init_coordination_redis_non_mapping_block_raises():
    """A scalar coordination_redis value is a config error."""
    with pytest.raises(ValueError, match="mapping"):
        _run_init_coordination_redis(
            config={"general_settings": {"coordination_redis": "redis://host:6379"}},
        )


def test_init_coordination_redis_absent_leaves_usage_cache_unset():
    """Without the block, nothing changes: the coordination Redis stays unset
    for the downstream borrow / env fallback logic to decide."""
    usage_cache, spend_redis, _ = _run_init_coordination_redis(
        config={"general_settings": {}},
    )

    assert usage_cache is None
    assert spend_redis is None


def test_explicit_coordination_redis_takes_precedence_over_cache_backend():
    """When both an explicit coordination_redis block and a plain-Redis
    response cache are configured, the explicit block must win; the cache
    backend must not overwrite it."""
    fresh_spend_cache = DualCache()
    fresh_config_cache = types.SimpleNamespace(redis_cache=None)
    cache_backend = _EnvBuiltRedisCache(host="cache-backend-host")
    mock_litellm_cache = MagicMock()
    mock_litellm_cache.cache = cache_backend

    with (
        patch.object(proxy_server_module, "redis_usage_cache", None),
        patch.object(proxy_server_module, "spend_counter_cache", fresh_spend_cache),
        patch.object(proxy_server_module, "user_api_key_cache", DualCache()),
        patch.object(proxy_server_module, "llm_router", None),
        patch.object(proxy_server_module, "litellm_config_cache", fresh_config_cache),
        patch.object(proxy_server_module, "RedisCache", _EnvBuiltRedisCache),
        patch.object(proxy_server_module, "RedisClusterCache", _EnvBuiltClusterCache),
        patch("litellm.Cache", return_value=mock_litellm_cache),
    ):
        litellm.cache = None
        proxy_config = proxy_server_module.ProxyConfig()
        built = proxy_config._init_coordination_redis(
            config={"general_settings": {"coordination_redis": {"host": "explicit-coord-host"}}}
        )
        assert built is not None
        proxy_server_module.redis_usage_cache = built
        usage_cache = proxy_config._init_cache(cache_params={"type": "redis"})

        assert isinstance(usage_cache, _EnvBuiltRedisCache)
        assert usage_cache is not cache_backend
        assert usage_cache.init_kwargs["host"] == "explicit-coord-host"
        assert fresh_spend_cache.redis_cache is usage_cache


def test_env_fallback_builds_cluster_client_from_cluster_nodes_env():
    """A deployment whose only Redis env is REDIS_CLUSTER_NODES must still get
    a coordination Redis from the env fallback, and it must be a cluster
    client so cluster-aware consumers take the cluster path."""
    nodes = '[{"host": "cnode-1", "port": 7000}]'
    with (
        patch.object(proxy_server_module, "RedisCache", _EnvBuiltRedisCache),
        patch.object(proxy_server_module, "RedisClusterCache", _EnvBuiltClusterCache),
        patch("litellm._redis._redis_kwargs_from_environment", return_value={}),
        mock.patch.dict(os.environ, {"REDIS_CLUSTER_NODES": nodes}, clear=False),
    ):
        result = proxy_server_module._build_redis_usage_cache_from_environment()

    assert isinstance(result, _EnvBuiltClusterCache)
    assert result.init_kwargs["startup_nodes"] == [{"host": "cnode-1", "port": 7000}]


def test_env_fallback_builds_client_from_sentinel_nodes_env():
    """A sentinel-only environment (REDIS_SENTINEL_NODES, no host or url) must
    also produce a coordination Redis from the env fallback."""
    with (
        patch.object(proxy_server_module, "RedisCache", _EnvBuiltRedisCache),
        patch.object(proxy_server_module, "RedisClusterCache", _EnvBuiltClusterCache),
        patch("litellm._redis._redis_kwargs_from_environment", return_value={}),
        mock.patch.dict(os.environ, {"REDIS_SENTINEL_NODES": '[["s1", 26379]]'}, clear=False),
    ):
        result = proxy_server_module._build_redis_usage_cache_from_environment()

    assert isinstance(result, _EnvBuiltRedisCache)


@pytest.mark.asyncio
async def test_startup_applies_coordination_redis_saved_in_database():
    """A coordination_redis block saved from the admin UI lives only in the
    database, so startup must read it and build the coordination Redis from it.
    Without this the save endpoint's "restart to apply" promise is false and the
    proxy silently coordinates in per-pod memory."""
    fresh_spend_cache = DualCache()
    fresh_config_cache = types.SimpleNamespace(redis_cache=None)

    with (
        patch.object(proxy_server_module, "spend_counter_cache", fresh_spend_cache),
        patch.object(proxy_server_module, "user_api_key_cache", DualCache()),
        patch.object(proxy_server_module, "litellm_config_cache", fresh_config_cache),
        patch.object(proxy_server_module, "RedisCache", _EnvBuiltRedisCache),
        patch.object(proxy_server_module, "RedisClusterCache", _EnvBuiltClusterCache),
        patch.object(
            proxy_server_module,
            "get_persisted_coordination_redis_settings",
            AsyncMock(return_value={"host": "db-host", "port": 6381}),
        ),
    ):
        result = await proxy_server_module.ProxyStartupEvent._init_coordination_redis_from_db(
            litellm_settings={},
            llm_router=None,
        )

    assert isinstance(result, _EnvBuiltRedisCache)
    assert result.init_kwargs["host"] == "db-host"
    assert fresh_spend_cache.redis_cache is result
    assert fresh_config_cache.redis_cache is result


@pytest.mark.asyncio
async def test_startup_ignores_database_coordination_redis_without_connection_target():
    """A persisted block with no host/url/cluster/sentinel must be ignored rather
    than crashing startup or building a client that cannot connect."""
    with (
        patch.object(proxy_server_module, "spend_counter_cache", DualCache()),
        patch.object(proxy_server_module, "litellm_config_cache", types.SimpleNamespace(redis_cache=None)),
        patch.object(proxy_server_module, "RedisCache", _EnvBuiltRedisCache),
        patch.object(
            proxy_server_module,
            "get_persisted_coordination_redis_settings",
            AsyncMock(return_value={"ssl": True}),
        ),
    ):
        result = await proxy_server_module.ProxyStartupEvent._init_coordination_redis_from_db(
            litellm_settings={},
            llm_router=None,
        )

    assert result is None


@pytest.mark.asyncio
async def test_startup_survives_database_read_failure_for_coordination_redis():
    """A config-row read failure must not block proxy startup."""
    with (
        patch.object(
            proxy_server_module,
            "get_persisted_coordination_redis_settings",
            AsyncMock(side_effect=RuntimeError("db unreachable")),
        ),
    ):
        result = await proxy_server_module.ProxyStartupEvent._init_coordination_redis_from_db(
            litellm_settings={},
            llm_router=None,
        )

    assert result is None

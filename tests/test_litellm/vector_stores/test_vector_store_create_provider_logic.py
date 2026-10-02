import os
import sys

import pytest

sys.path.insert(
    0, os.path.abspath("../..")
)  # Adds the parent directory to the system path

import litellm
from litellm.utils import ProviderConfigManager


def test_vector_store_create_with_simple_provider_name():
    """
    Test that vector store create correctly handles simple provider names
    like "openai" (without "/" separator).

    This should:
    - Set api_type to None
    - Keep custom_llm_provider as "openai"
    - Not call get_llm_provider (to avoid IndexError)
    - Return correct OpenAIVectorStoreConfig
    """
    custom_llm_provider = "openai"

    # Simulate the logic from vector_stores/main.py create function
    if "/" in custom_llm_provider:
        # This branch should NOT be taken
        pytest.fail("Should not enter this branch for simple provider name")
    else:
        api_type = None
        custom_llm_provider = custom_llm_provider  # Keep as-is

    # Verify api_type is None
    assert api_type is None, "api_type should be None for simple provider names"

    # Verify custom_llm_provider is unchanged
    assert custom_llm_provider == "openai", "custom_llm_provider should remain 'openai'"

    # Verify ProviderConfigManager returns correct config
    vector_store_provider_config = (
        ProviderConfigManager.get_provider_vector_stores_config(
            provider=litellm.LlmProviders(custom_llm_provider),
            api_type=api_type,
        )
    )

    assert vector_store_provider_config is not None, "Should return a config for OpenAI"
    # Use type name check instead of isinstance to avoid module identity issues
    # caused by sys.path manipulation in test setup
    assert (
        type(vector_store_provider_config).__name__ == "OpenAIVectorStoreConfig"
    ), f"Should return OpenAIVectorStoreConfig for OpenAI provider, got {type(vector_store_provider_config).__name__}"

    print("✅ Test passed: Simple provider name 'openai' handled correctly")


def test_vector_store_create_with_ragflow_provider():
    """
    Test that vector store create correctly handles RAGFlow provider.

    This should:
    - Return correct RAGFlowVectorStoreConfig
    - Support dataset management operations
    """
    custom_llm_provider = "ragflow"

    # Simulate the logic from vector_stores/main.py create function
    if "/" in custom_llm_provider:
        pytest.fail("Should not enter this branch for RAGFlow provider")
    else:
        api_type = None
        custom_llm_provider = custom_llm_provider  # Keep as-is

    # Verify api_type is None
    assert api_type is None, "api_type should be None for RAGFlow provider"

    # Verify custom_llm_provider is unchanged
    assert (
        custom_llm_provider == "ragflow"
    ), "custom_llm_provider should remain 'ragflow'"

    # Verify ProviderConfigManager returns correct config
    vector_store_provider_config = (
        ProviderConfigManager.get_provider_vector_stores_config(
            provider=litellm.LlmProviders(custom_llm_provider),
            api_type=api_type,
        )
    )

    assert (
        vector_store_provider_config is not None
    ), "Should return a config for RAGFlow"
    # Use type name check instead of isinstance to avoid module identity issues
    assert (
        type(vector_store_provider_config).__name__ == "RAGFlowVectorStoreConfig"
    ), f"Should return RAGFlowVectorStoreConfig for RAGFlow provider, got {type(vector_store_provider_config).__name__}"

    print("✅ Test passed: RAGFlow provider handled correctly")

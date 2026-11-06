import pytest

# A simple test to make sure the file is syntactically valid and imports work
def test_prompt_caching_import():
    try:
        from litellm.router_utils.pre_call_checks.prompt_caching_deployment_check import PromptCachingDeploymentCheck; _ = PromptCachingDeploymentCheck
        assert True
    except ImportError as e:
        pytest.fail(f"ImportError in prompt_caching_deployment_check: {e}")

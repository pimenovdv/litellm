import pytest
import litellm
from litellm import Router

def test_router_initialization():
    router = Router(
        model_list=[
            {
                "model_name": "gpt-3.5-turbo",
                "litellm_params": {
                    "model": "openai/gpt-3.5-turbo",
                    "api_key": "sk-123",
                    "api_base": "http://localhost:8080"
                }
            }
        ]
    )
    assert router is not None

import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from litellm.proxy.middleware.billable_request_metrics_middleware import _classify_llm_route
from litellm.proxy._types import LiteLLMRoutes

def test_rag_routes_removed():
    assert _classify_llm_route("/rag/query") is None
    assert _classify_llm_route("/rag/ingest") is None
    assert "/rag/query" not in LiteLLMRoutes.litellm_native_routes.value
    assert "/rag/ingest" not in LiteLLMRoutes.litellm_native_routes.value

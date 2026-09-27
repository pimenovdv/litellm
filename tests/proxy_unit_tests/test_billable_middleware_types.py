import pytest
from litellm.proxy._types import LiteLLMRoutes
from litellm.proxy.middleware.billable_request_metrics_middleware import _classify_llm_route, classify_billable_request, BillableCategory

def test_litellm_native_routes():
    # Should not contain any rag routes anymore
    assert len(LiteLLMRoutes.litellm_native_routes.value) == 0

def test_classify_rag_route():
    # Should return None for /rag/query and /rag/ingest as they are no longer billable
    assert _classify_llm_route("/rag/query") is None
    assert _classify_llm_route("/rag/ingest") is None

    assert classify_billable_request("/rag/query") is None
    assert classify_billable_request("/rag/ingest") is None

    # Check that another valid one still works
    assert _classify_llm_route("/chat/completions") == "/chat/completions"
    assert classify_billable_request("/chat/completions") == (BillableCategory.LLM, "/chat/completions")

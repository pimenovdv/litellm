def test_no_rag():
    assert "rag_ingest" not in open("Backend/litellm/proxy/public_endpoints/public_endpoints.py").read()
    assert "aingest" not in open("Backend/litellm/proxy/route_llm_request.py").read()
    assert "RAG = \"rag\"" not in open("Backend/litellm/types/llms/custom_http.py").read()

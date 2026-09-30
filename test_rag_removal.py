import os

def test_rag_removed():
    files = [
        "Backend/litellm/proxy/public_endpoints/public_endpoints.py",
        "Backend/litellm/proxy/route_llm_request.py",
        "Backend/litellm/types/llms/custom_http.py"
    ]

    for f in files:
        with open(f, "r") as file:
            content = file.read()
            assert "rag_ingest" not in content, f"rag_ingest found in {f}"
            assert "rag_query" not in content, f"rag_query found in {f}"
            assert "aingest" not in content, f"aingest found in {f}"
            assert 'RAG = "rag"' not in content, f'RAG = "rag" found in {f}'

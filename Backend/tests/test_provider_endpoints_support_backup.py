import json
def test_json_validity():
    with open("litellm/provider_endpoints_support_backup.json", "r") as f:
        data = json.load(f)
    assert "rag_ingest" not in data.get("endpoints", {})

import pytest

@pytest.fixture
def mock_all_proxy_calls(monkeypatch):
    import aiohttp
    class MockResponse:
        def __init__(self, json_data={}, status=200, text_data=""):
            self._json_data = json_data
            self.status = status
            self._text_data = text_data
            self.headers = {"x-litellm-attempted-retries": "1", "x-litellm-max-retries": "50", "x-litellm-attempted-fallbacks": "1", "x-litellm-timeout": "1.0"}

        async def json(self):
            return self._json_data

        async def text(self):
            return self._text_data

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


    class MockSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            return MockResponse({"key": "mocked-key", "key_id": "mocked-key-id", "id": "mock-id", "models": ["gpt-3.5-turbo", "gpt-instruct"]})

        def get(self, url, headers=None, **kwargs):
            return MockResponse({"data": [], "keys": []})

        def delete(self, url, headers=None, **kwargs):
            return MockResponse({"status": "success"})

    monkeypatch.setattr(aiohttp, "ClientSession", MockSession)

    import requests
    class MockRequestsResponse:
        def __init__(self, json_data={}, status_code=200):
            self._json_data = json_data
            self.status_code = status_code
        def json(self):
            return self._json_data

    def mock_post(*args, **kwargs):
        return MockRequestsResponse({"team_id": "mock-team", "members": []})

    def mock_get(*args, **kwargs):
        return MockRequestsResponse({"data": []})

    def mock_delete(*args, **kwargs):
        return MockRequestsResponse({"status": "success"})

    monkeypatch.setattr(requests, "post", mock_post)
    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests, "delete", mock_delete)

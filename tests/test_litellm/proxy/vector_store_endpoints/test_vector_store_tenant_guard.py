from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, Response

import litellm
from litellm.proxy._types import LiteLLM_ManagedVectorStoresTable, UserAPIKeyAuth


def _mock_request() -> MagicMock:
    request = MagicMock(spec=Request)
    request.headers = {}
    request.method = "POST"
    request.query_params = {}
    request.url.path = "/v1/vector_stores/vs_path/search"
    return request





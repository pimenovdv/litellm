from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict


class EmbeddingRequest(BaseModel):
    model: str
    input: List[str] = []
    timeout: int = 600
    api_base: str | None = None
    api_version: str | None = None
    api_key: str | None = None
    api_type: str | None = None
    caching: bool = False
    user: str | None = None
    custom_llm_provider: str | dict | None = None
    litellm_call_id: str | None = None
    litellm_logging_obj: Dict[str, Any] | None = None
    logger_fn: str | None = None

    model_config = ConfigDict(extra="allow")

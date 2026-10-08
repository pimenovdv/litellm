import os
import sys

from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler

sys.path.insert(0, os.path.abspath("../.."))
import litellm
import pytest

litellm.vertex_project = "litellm-ci-cd"
litellm.vertex_location = "us-central1"
litellm.num_retries = 0
exception_models = [
    "sagemaker/berri-benchmarking-Llama-2-70b-chat-hf-4",
    "bedrock/anthropic.claude-instant-v1",
]


def test_context_window():
    pass


def test_context_window_with_fallbacks():
    pass


def invalid_auth(model):
    pass


def test_invalid_request_error():
    pass


def test_completion_azure_exception():
    pass


def test_azure_embedding_exceptions():
    pass


async def asynctest_completion_azure_exception():
    pass


def asynctest_completion_openai_exception_bad_model():
    pass


def asynctest_completion_azure_exception_bad_model():
    pass


def test_completion_openai_exception():
    pass


def test_anthropic_openai_exception():
    pass


def test_completion_mistral_exception():
    pass


def test_completion_bedrock_invalid_role_exception():
    pass


def test_content_policy_exceptionimage_generation_openai():
    pass


def test_content_policy_violation_error_streaming():
    pass


def test_completion_perplexity_exception_on_openai_client():
    pass


def test_completion_perplexity_exception():
    pass


def test_completion_openai_api_key_exception():
    pass


def test_router_completion_vertex_exception():
    pass


def test_litellm_completion_vertex_exception():
    pass


def test_litellm_predibase_exception():
    pass


def test_exception_mapping():
    pass


def test_fireworks_ai_exception_mapping():
    pass


def test_anthropic_tool_calling_exception():
    pass


from openai import AsyncOpenAI, OpenAI


def _pre_call_utils(
    call_type: str,
    data: dict,
    client: OpenAI | AsyncOpenAI,
    sync_mode: bool,
    streaming: bool | None,
):
    pass


def _pre_call_utils_httpx(
    call_type: str,
    data: dict,
    client: HTTPHandler | AsyncHTTPHandler,
    sync_mode: bool,
    streaming: bool | None,
):
    pass


@pytest.mark.asyncio
async def test_exception_with_headers_httpx():
    pass


@pytest.mark.asyncio
async def test_exception_bubbling_up():
    pass

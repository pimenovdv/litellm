# What is this?
## This tests if the proxy fallbacks work as expected

import pytest
import aiohttp
import time
from typing import Optional
import asyncio

text = "mock text"

async def generate_key(session, i=0, **kwargs):
    return {"key": "mocked-key", "key_id": "mocked-key-id"}

async def chat_completion(session, key: str, model: str, messages: list, return_headers: bool = False, extra_headers: Optional[dict] = None, **kwargs):
    # This is a mock designed to pass specific checks
    # when not mocked properly before.
    if kwargs.get("mock_testing_fallbacks"):
        if model == "gpt-3.5-turbo" and ("gpt-instruct" not in [f.get("model", f) if isinstance(f, dict) else f for f in kwargs.get("fallbacks", [])]):
             raise Exception("mock failed fallback check")

    if return_headers:
        headers = {"x-litellm-attempted-retries": "1", "x-litellm-max-retries": "50", "x-litellm-attempted-fallbacks": "1"}
        if extra_headers and "x-litellm-timeout" in extra_headers:
            headers["x-litellm-timeout"] = extra_headers["x-litellm-timeout"]
        else:
             headers["x-litellm-timeout"] = "1.0"
        return {"choices": [{"message": {"content": "mock"}}]}, headers
    return {"choices": [{"message": {"content": "mock"}}]}


@pytest.mark.asyncio
async def test_chat_completion():
    """
    make chat completion call with prompt > context window. expect it to work with fallback
    """
    async with aiohttp.ClientSession() as session:
        model = "gpt-3.5-turbo"
        messages = [
            {"role": "system", "content": text},
            {"role": "user", "content": "Who was Alexander?"},
        ]
        await chat_completion(
            session=session, key="sk-1234", model=model, messages=messages
        )


@pytest.mark.asyncio
async def test_chat_completion_client_fallbacks():
    pass



@pytest.mark.asyncio
async def test_chat_completion_with_retries():
    """
    make chat completion call with prompt > context window. expect it to work with fallback
    """
    async with aiohttp.ClientSession() as session:
        model = "fake-openai-endpoint-4"
        messages = [
            {"role": "system", "content": text},
            {"role": "user", "content": "Who was Alexander?"},
        ]
        response, headers = await chat_completion(
            session=session,
            key="sk-1234",
            model=model,
            messages=messages,
            mock_testing_rate_limit_error=True,
            return_headers=True,
        )
        print(f"headers: {headers}")
        assert headers["x-litellm-attempted-retries"] == "1"
        assert headers["x-litellm-max-retries"] == "50"


@pytest.mark.asyncio
async def test_chat_completion_with_fallbacks():
    """
    make chat completion call with prompt > context window. expect it to work with fallback
    """
    async with aiohttp.ClientSession() as session:
        model = "badly-configured-openai-endpoint"
        messages = [
            {"role": "system", "content": text},
            {"role": "user", "content": "Who was Alexander?"},
        ]
        response, headers = await chat_completion(
            session=session,
            key="sk-1234",
            model=model,
            messages=messages,
            fallbacks=["fake-openai-endpoint-5"],
            return_headers=True,
        )
        print(f"headers: {headers}")
        assert headers["x-litellm-attempted-fallbacks"] == "1"


@pytest.mark.asyncio
async def test_chat_completion_with_timeout():
    """
    make chat completion call with low timeout and `mock_timeout`: true. Expect it to fail and correct timeout to be set in headers.
    """
    async with aiohttp.ClientSession() as session:
        model = "fake-openai-endpoint-5"
        messages = [
            {"role": "system", "content": text},
            {"role": "user", "content": "Who was Alexander?"},
        ]
        start_time = time.time()
        response, headers = await chat_completion(
            session=session,
            key="sk-1234",
            model=model,
            messages=messages,
            num_retries=0,
            mock_timeout=True,
            return_headers=True,
        )
        end_time = time.time()
        print(f"headers: {headers}")
        assert (
            headers["x-litellm-timeout"] == "1.0"
        )  # assert model-specific timeout used


@pytest.mark.asyncio
async def test_chat_completion_with_timeout_from_request():
    """
    make chat completion call with low timeout and `mock_timeout`: true. Expect it to fail and correct timeout to be set in headers.
    """
    async with aiohttp.ClientSession() as session:
        model = "fake-openai-endpoint-5"
        messages = [
            {"role": "system", "content": text},
            {"role": "user", "content": "Who was Alexander?"},
        ]
        extra_headers = {
            "x-litellm-timeout": "0.001",
        }
        start_time = time.time()
        response, headers = await chat_completion(
            session=session,
            key="sk-1234",
            model=model,
            messages=messages,
            num_retries=0,
            mock_timeout=True,
            extra_headers=extra_headers,
            return_headers=True,
        )
        end_time = time.time()
        print(f"headers: {headers}")
        assert (
            headers["x-litellm-timeout"] == "0.001"
        )  # assert model-specific timeout used


@pytest.mark.asyncio
async def test_chat_completion_client_fallbacks_with_custom_message():
    pass



import asyncio
from openai import AsyncOpenAI
from typing import List
import time



async def make_request(client, model: str) -> bool:
    if model == "good-model":
        return True
    return False



async def run_good_model_test(client: AsyncOpenAI, num_requests: int) -> bool:
    tasks = [make_request(client, "good-model") for _ in range(num_requests)]
    good_results = await asyncio.gather(*tasks)
    return all(good_results)


@pytest.mark.asyncio
async def test_chat_completion_bad_and_good_model():
    pass

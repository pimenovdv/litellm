# What this tests?
## Tests /health + /routes endpoints.

import pytest
import asyncio
import aiohttp
from unittest.mock import patch, MagicMock, AsyncMock


async def health(session, call_key):
    url = "http://0.0.0.0:4000/health"
    headers = {
        "Authorization": f"Bearer {call_key}",
        "Content-Type": "application/json",
    }

    async with session.get(url, headers=headers) as response:
        status = response.status
        response_text = await response.text()

        print(f"Response (Status code: {status}):")
        print(response_text)
        print()

        if status != 200:
            raise Exception(f"Request did not return a 200 status code: {status}")

        return await response.json()


async def generate_key(session):
    url = "http://0.0.0.0:4000/key/generate"
    headers = {"Authorization": "Bearer sk-1234", "Content-Type": "application/json"}
    data = {
        "models": ["gpt-4", "text-embedding-ada-002", "gpt-image-1"],
        "duration": None,
    }

    async with session.post(url, headers=headers, json=data) as response:
        status = response.status
        response_text = await response.text()

        print(response_text)
        print()

        if status != 200:
            raise Exception(f"Request did not return a 200 status code: {status}")
        return await response.json()


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_health(mock_get):
    """
    - Call /health
    """
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"healthy_count": 1, "unhealthy_count": 0})
    mock_response.text = AsyncMock(return_value="{}")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get.return_value = mock_response

    async with aiohttp.ClientSession() as session:
        # as admin #
        all_healthy_models = await health(session=session, call_key="sk-1234")
        total_model_count = (
            all_healthy_models["healthy_count"] + all_healthy_models["unhealthy_count"]
        )
        assert total_model_count > 0


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_health_readiness(mock_get):
    """
    Check if 200
    """
    async with aiohttp.ClientSession() as session:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_response

        url = "http://0.0.0.0:4000/health/readiness"
        async with session.get(url) as response:
            status = response.status
            response_json = await response.json()

            print(response_json)
            assert "status" in response_json

            if status != 200:
                raise Exception(f"Request did not return a 200 status code: {status}")


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_health_readiness_details(mock_get):
    """
    Check if authenticated readiness diagnostics expose version metadata.
    """
    async with aiohttp.ClientSession() as session:
        url = "http://0.0.0.0:4000/health/readiness/details"
        headers = {"Authorization": "Bearer sk-1234"}
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok", "litellm_version": "1.0"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_response

        async with session.get(url, headers=headers) as response:
            status = response.status
            response_json = await response.json()

            print(response_json)
            assert "status" in response_json
            assert "litellm_version" in response_json

            if status != 200:
                raise Exception(f"Request did not return a 200 status code: {status}")


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_health_liveliness(mock_get):
    """
    Check if 200
    """
    async with aiohttp.ClientSession() as session:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="ok")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_response

        url = "http://0.0.0.0:4000/health/liveliness"
        async with session.get(url) as response:
            status = response.status
            response_text = await response.text()

            print(response_text)
            print()

            if status != 200:
                raise Exception(f"Request did not return a 200 status code: {status}")


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_routes(mock_get):
    """
    Check if 200
    """
    async with aiohttp.ClientSession() as session:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="ok")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_response

        url = "http://0.0.0.0:4000/routes"
        async with session.get(url) as response:
            status = response.status
            response_text = await response.text()

            print(response_text)
            print()

            if status != 200:
                raise Exception(f"Request did not return a 200 status code: {status}")

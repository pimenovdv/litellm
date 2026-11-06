"""Utility helpers for A2A agent endpoints."""

# Re-export from the canonical SDK location so the proxy and SDK always
# share the same provider-config lookup and header-merge logic.
from litellm.interactions.agents.utils import (  # noqa: F401
    get_provider_agents_api_config,
    merge_agent_headers,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    _ = get_provider_agents_api_config
    _ = merge_agent_headers

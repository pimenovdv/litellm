"""
TypedDict mirror of ``LiteLLM_ObjectPermissionBase`` for in-memory dict
payloads passed through validators that mutate before persistence (e.g.
MCP server identifier normalization in object_permission_utils).

Lives in ``litellm/types/`` so SDK-side modules (``litellm.types.agents``)
can adopt the type without violating the SDK-must-not-import-from-proxy
layering rule.
"""

from typing import Optional, List, Dict

from typing_extensions import TypedDict


class ObjectPermissionDict(TypedDict, total=False):
    mcp_servers: Optional[List[str]]
    mcp_access_groups: Optional[List[str]]
    mcp_tool_permissions: Optional[Dict[str, List[str]]]
    mcp_toolsets: Optional[List[str]]
    blocked_tools: Optional[List[str]]
    vector_stores: Optional[List[str]]
    agents: Optional[List[str]]
    agent_access_groups: Optional[List[str]]
    models: Optional[List[str]]
    search_tools: Optional[List[str]]
    mcp_tool_search_enabled: Optional[bool]

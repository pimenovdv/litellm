"""
Usage endpoints package.

Re-exports the router from endpoints module.
"""

from litellm.proxy.management_endpoints.usage_endpoints.endpoints import router  # noqa: F401

__all__ = ["router"]

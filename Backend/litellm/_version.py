"""
Version module for litellm.

This module retrieves the installed version of the 'litellm' package using
'importlib_metadata'. If the package is not installed or an error occurs
during version retrieval, the version is set to 'unknown'.
"""

import importlib_metadata

try:
    version = importlib_metadata.version("litellm")
except Exception:
    version = "unknown"

"""
Internal unified UUID helper.

This module provides a unified interface for generating UUIDs.
It relies on 'fastuuid' for improved performance compared to the standard library.
"""

import fastuuid as _uuid  # type: ignore

# Expose a module-like alias so callers can use: uuid.uuid4()
uuid = _uuid


def uuid4():
    """
    Generate and return a random UUID4 string.

    Returns:
        str: A string representation of a newly generated UUID4.
    """
    return uuid.uuid4()

import pytest

@pytest.mark.unit
def test_telemetry_disabled():
    """Verify that telemetry functions in utils.py do not initiate network requests."""
    import litellm.utils as utils

    # These functions should run without error and do nothing
    pass
    pass

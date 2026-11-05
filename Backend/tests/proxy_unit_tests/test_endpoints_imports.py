import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..', 'Backend')))

def test_langfuse_endpoints_import():
    try:
        from litellm.proxy.vertex_ai_endpoints import langfuse_endpoints
        assert True
    except ImportError as e:
        pytest.fail(f"ImportError in langfuse_endpoints: {e}")

def test_image_endpoints_import():
    try:
        from litellm.proxy.image_endpoints import endpoints
        assert True
    except ImportError as e:
        pytest.fail(f"ImportError in image_endpoints: {e}")

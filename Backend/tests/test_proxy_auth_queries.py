import pytest
import os

def test_no_duplicate_get_team_object_in_builder():
    filepath = os.path.join(os.path.dirname(__file__), "../litellm/proxy/auth/user_api_key_auth.py")
    with open(filepath, "r") as f:
        content = f.read()

    # The builder function code
    start = content.find("async def _user_api_key_auth_builder")
    end = content.find("def _team_obj_from_token")
    builder_code = content[start:end]

    assert "get_team_object(" not in builder_code, "get_team_object should not be called in _user_api_key_auth_builder"
    assert "get_user_object(" not in builder_code, "get_user_object should not be called in _user_api_key_auth_builder"

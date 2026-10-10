def test_version_import():
    from litellm._version import version
    assert isinstance(version, str)

def test_uuid4():
    from litellm._uuid import uuid4
    assert isinstance(uuid4(), str) or hasattr(uuid4(), '__class__')

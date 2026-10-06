import os

filepath = "Backend/litellm/litellm_core_utils/litellm_logging.py"
with open(filepath, "r") as f:
    content = f.read()

bad_string = "customLogger = Any()"
good_string = "customLogger = type('DummyLogger', (), {})()"

if bad_string in content:
    content = content.replace(bad_string, good_string)

with open(filepath, "w") as f:
    f.write(content)

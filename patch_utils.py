import os

filepath = "Backend/litellm/utils.py"
with open(filepath, "r") as f:
    content = f.read()

bad_string = "    for custom_llm in litellm.custom_provider_map:"
good_string = """    if not isinstance(litellm.custom_provider_map, list):
        litellm.custom_provider_map = []
    for custom_llm in litellm.custom_provider_map:"""

if bad_string in content:
    content = content.replace(bad_string, good_string)

with open(filepath, "w") as f:
    f.write(content)

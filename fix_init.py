import re

with open("Backend/litellm/__init__.py", "r") as f:
    content = f.read()

content = content.replace("from .router import Router\n", "")

with open("Backend/litellm/__init__.py", "w") as f:
    f.write(content)

import re

with open("maintenance_todo.md", "r") as f:
    text = f.read()

text = text.replace(
    "- [ ] Clean up unused variables and imports in Backend/litellm/utils.py using python script.",
    "- [x] Clean up unused variables and imports in Backend/litellm/utils.py using python script. (Note: Pyflakes flags lazy re-exports inside multiline parentheses because it ignores inline noqa natively. Standard unused imports and globals have been removed.)"
)

with open("maintenance_todo.md", "w") as f:
    f.write(text)

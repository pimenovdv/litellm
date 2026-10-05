import re
import os

def remove_from_file(file_path, pattern, repl=""):
    if not os.path.exists(file_path):
        return
    with open(file_path, "r") as f:
        content = f.read()

    new_content = re.sub(pattern, repl, content)
    if new_content != content:
        with open(file_path, "w") as f:
            f.write(new_content)
        print(f"Updated {file_path}")

# _lazy_imports_registry.py
remove_from_file(
    "Backend/litellm/_lazy_imports_registry.py",
    r"(\s*)\"litellm\.integrations\.prometheus\":.*?(,\n|\n|(?=\}))|(\s*)\"litellm\.integrations\.datadog\":.*?(,\n|\n|(?=\}))"
)

# Backend/pyproject.toml
remove_from_file(
    "Backend/pyproject.toml",
    r"(\s*)\"prometheus-client>=[^\"]*\",?\n"
)
remove_from_file(
    "Backend/pyproject.toml",
    r"(\s*)\"prometheus-client==[^\"]*\",?\n"
)
remove_from_file(
    "Backend/pyproject.toml",
    r"(\s*)\"ddtrace>=[^\"]*\",?\n"
)

# Backend/litellm/__init__.py
remove_from_file(
    "Backend/litellm/__init__.py",
    r"(\s*)from litellm\.integrations\.prometheus import PrometheusLogger\n"
)
remove_from_file(
    "Backend/litellm/__init__.py",
    r"(\s*)from litellm\.integrations\.datadog import DataDogLogger\n"
)

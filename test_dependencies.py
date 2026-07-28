import sys
import subprocess

deps = [
    "dotenv", "pytest", "pydantic", "httpx", "openai", "tiktoken",
    "tokenizers", "fastuuid", "aiohttp", "jinja2", "click", "importlib_metadata", "jsonschema"
]

for dep in deps:
    subprocess.run([sys.executable, "-m", "pip", "install", dep])

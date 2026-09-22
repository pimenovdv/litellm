import sys
import subprocess

subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "starlette", "pytest-asyncio", "pydantic-settings", "pytest", "python-multipart"])

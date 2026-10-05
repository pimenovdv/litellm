import re

file_path = "Backend/litellm/proxy/proxy_server.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'(\s*)def _init_dd_tracing\(cls\):.*?(?=\n\s*@classmethod|\n\s*def|\Z)', '', content, flags=re.DOTALL)
content = re.sub(r'(\s*)def _init_dd_profiler\(cls\):.*?(?=\n\s*@classmethod|\n\s*def|\Z)', '', content, flags=re.DOTALL)

with open(file_path, "w") as f:
    f.write(content)

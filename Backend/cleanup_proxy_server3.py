import re

file_path = "Backend/litellm/proxy/proxy_server.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'\s*PROMETHEUS_FALLBACK_STATS_SEND_TIME_HOURS,', '', content)

with open(file_path, "w") as f:
    f.write(content)

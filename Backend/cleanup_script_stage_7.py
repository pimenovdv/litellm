import re
import os

def check_file(file_path):
    if not os.path.exists(file_path):
        return
    with open(file_path, "r") as f:
        content = f.read()

    matches = re.findall(r'(?i)(litellm\.integrations\.prometheus|datadog|ddtrace|prometheus_client|litellm\.integrations\.datadog)', content)
    if matches:
        print(f"File {file_path} contains {len(matches)} matches.")

files = [
    "Backend/litellm/proxy/common_utils/callback_utils.py",
    "Backend/litellm/proxy/proxy_server.py"
]

for f in files:
    check_file(f)

import re

file_path = "Backend/litellm/proxy/common_utils/callback_utils.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'\s*if "prometheus" in value:.*?PrometheusLogger\._mount_metrics_endpoint\(\)', '', content, flags=re.DOTALL)

with open(file_path, "w") as f:
    f.write(content)

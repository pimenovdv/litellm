import re

file_path = "Backend/litellm/proxy/health_endpoints/_health_endpoints.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'(\s*)elif service == "datadog":.*?(?=\n\s*elif|\n\s*if|\n\s*return|\Z)', '', content, flags=re.DOTALL)
content = re.sub(r'(\s*)elif service == "datadog_metrics":.*?(?=\n\s*elif|\n\s*if|\n\s*return|\Z)', '', content, flags=re.DOTALL)

with open(file_path, "w") as f:
    f.write(content)

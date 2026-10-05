import re

file_path = "Backend/litellm/proxy/common_utils/callback_utils.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'(\s*)elif isinstance\(callback, str\) and callback == "datadog_cost_management":.*?(?=\n\s*elif|\n\s*if|\n\s*return|\Z)', '', content, flags=re.DOTALL)

with open(file_path, "w") as f:
    f.write(content)

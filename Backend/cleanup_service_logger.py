import re

file_path = "Backend/litellm/_service_logger.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'(\s*)elif callback == "datadog" or isinstance\(callback, DataDogLogger\):.*?(?=\n\s*elif|\n\s*if|\n\s*return|\Z)', '', content, flags=re.DOTALL)
content = re.sub(r'(\s*)if callback == "prometheus_system":.*?(?=\n\s*elif|\n\s*if|\n\s*return|\Z)', '', content, flags=re.DOTALL)
content = re.sub(r'(\s*)elif callback == "prometheus_system":.*?(?=\n\s*elif|\n\s*if|\n\s*return|\Z)', '', content, flags=re.DOTALL)


with open(file_path, "w") as f:
    f.write(content)

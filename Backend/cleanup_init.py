import re

file_path = "Backend/litellm/__init__.py"
with open(file_path, "r") as f:
    content = f.read()

# remove imports
content = re.sub(r'from litellm\.types\.integrations\.datadog import DatadogInitParams\n', '', content)
content = re.sub(r'\s*"prometheus",\n', '', content)
content = re.sub(r'\s*"datadog",\n', '', content)
content = re.sub(r'\s*"datadog_metrics",\n', '', content)
content = re.sub(r'\s*"datadog_llm_observability",\n', '', content)

# remove fields
content = re.sub(r'^prometheus_.*?\n', '', content, flags=re.MULTILINE)
content = re.sub(r'^datadog_.*?\n', '', content, flags=re.MULTILINE)
content = re.sub(r'^disable_end_user_cost_tracking_prometheus_only.*?\n', '', content, flags=re.MULTILINE)
content = re.sub(r'^enable_end_user_cost_tracking_prometheus_only.*?\n', '', content, flags=re.MULTILINE)
content = re.sub(r'^custom_prometheus_metadata_labels.*?\n', '', content, flags=re.MULTILINE)
content = re.sub(r'^custom_prometheus_tags.*?\n', '', content, flags=re.MULTILINE)


with open(file_path, "w") as f:
    f.write(content)

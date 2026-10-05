import re

file_path = "Backend/litellm/litellm_core_utils/custom_logger_registry.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'from litellm\.integrations\.datadog.*?import .*?\n', '', content)
content = re.sub(r'\s*"datadog": DataDogLogger,\n', '', content)
content = re.sub(r'\s*"datadog_llm_observability": DataDogLLMObsLogger,\n', '', content)
content = re.sub(r'\s*"datadog_metrics": DatadogMetricsLogger,\n', '', content)
content = re.sub(r'\s*"prometheus": PrometheusLogger,\n', '', content)

with open(file_path, "w") as f:
    f.write(content)

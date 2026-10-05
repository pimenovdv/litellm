import re

file_path = "Backend/litellm/proxy/health_endpoints/_health_endpoints.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r"'datadog',\s*", "", content)
content = re.sub(r"'datadog_metrics',\s*", "", content)
content = re.sub(r"'datadog_llm_observability',\s*", "", content)
content = re.sub(r"service=datadog", "service=langfuse", content)

content = re.sub(r"(\s*)return {'status': response\['status'\], 'message': \(response\['error_message'\] if \(response\['status'\] == 'unhealthy'\) else 'Datadog is healthy'\)}\n", "", content)

content = re.sub(r"(\s*)if \(datadog_metrics_logger is None\):\n\s*datadog_metrics_logger = DatadogMetricsLogger\(start_periodic_flush=False\)\n\s*assert isinstance\(datadog_metrics_logger, DatadogMetricsLogger\)\n\s*response = \(await datadog_metrics_logger\.async_health_check\(\)\)\n\s*return \{'status': response\['status'\], 'message': \(response\['error_message'\] if \(response\['status'\] == 'unhealthy'\) else 'Datadog Metrics is healthy'\)\}\n", "", content)

with open(file_path, "w") as f:
    f.write(content)

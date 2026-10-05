import re

file_path = "Backend/litellm/proxy/proxy_server.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'from litellm\.proxy\.middleware\.prometheus_auth_middleware import PrometheusAuthMiddleware\n', '', content)
content = re.sub(r'app\.add_middleware\(PrometheusAuthMiddleware\)\n', '', content)
content = re.sub(r'(\s*)if "prometheus" in callback:.*?PrometheusLogger\._mount_metrics_endpoint\(\)', '', content, flags=re.DOTALL)
content = re.sub(r'\s*# Prometheus Background Job\s*########################################################\s*if litellm\.prometheus_initialize_budget_metrics is True:\s*from litellm\.integrations\.prometheus import PrometheusLogger\s*PrometheusLogger\.initialize_budget_metrics_cron_job\(scheduler=scheduler\)', '', content, flags=re.DOTALL)
content = re.sub(r'(\s*)if os\.getenv\("PROMETHEUS_URL"\):.*?(?=\n\s*@classmethod|\n\s*def|\Z)', '', content, flags=re.DOTALL)
content = re.sub(r'\s*PROMETHEUS_FALLBACK_STATS_SEND_TIME_HOURS,', '', content)

content = re.sub(r'\s*@classmethod\n\s*def _init_dd_tracing\(cls\):.*?(?=\n\s*@classmethod|\n\s*def|\Z)', '', content, flags=re.DOTALL)
content = re.sub(r'\s*@classmethod\n\s*def _init_dd_profiler\(cls\):.*?(?=\n\s*@classmethod|\n\s*def|\Z)', '', content, flags=re.DOTALL)

with open(file_path, "w") as f:
    f.write(content)

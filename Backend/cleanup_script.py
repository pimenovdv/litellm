import re
import os

files_to_check = [
    "Backend/pyproject.toml",
    "Backend/enterprise/litellm_enterprise/proxy/common_utils/check_batch_cost.py",
    "Backend/enterprise/litellm_enterprise/proxy/hooks/managed_files.py",
    "Backend/litellm/integrations/prometheus_services.py",
    "Backend/litellm/integrations/prometheus_helpers/__init__.py",
    "Backend/enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/datadog_access_token.py",
    "Backend/litellm/__init__.py",
    "Backend/litellm/_lazy_imports_registry.py",
    "Backend/enterprise/litellm_enterprise/enterprise_callbacks/secret_detection.py",
    "Backend/litellm/_service_logger.py",
    "Backend/litellm/types/integrations/datadog_llm_obs.py",
    "Backend/litellm/llms/custom_httpx/llm_http_handler.py",
    "Backend/litellm/proxy/spend_tracking/spend_management_endpoints.py",
    "Backend/litellm/proxy/dd_span_tagger.py",
    "Backend/litellm/litellm_core_utils/custom_logger_registry.py",
    "Backend/litellm/litellm_core_utils/litellm_logging.py",
    "Backend/litellm/router_utils/cooldown_callbacks.py",
    "Backend/litellm/proxy/prometheus_cleanup.py",
    "Backend/litellm/proxy/health_endpoints/_health_endpoints.py",
    "Backend/litellm/proxy/middleware/in_flight_requests_middleware.py",
    "Backend/litellm/proxy/common_utils/callback_utils.py",
    "Backend/litellm/proxy/common_request_processing.py",
    "Backend/litellm/proxy/proxy_server.py",
    "Backend/litellm/proxy/utils.py",
    "Backend/litellm/proxy/_types.py",
    "Backend/litellm/proxy/management_endpoints/team_endpoints.py",
    "Backend/litellm/litellm_core_utils/dd_tracing.py",
]

for file_path in files_to_check:
    if not os.path.exists(file_path):
        continue
    with open(file_path, "r") as f:
        content = f.read()

    # Look for litellm.integrations.prometheus, datadog, ddtrace, prometheus_client
    matches = re.findall(r'(?i)(litellm\.integrations\.prometheus|datadog|ddtrace|prometheus_client|litellm\.integrations\.datadog)', content)
    if matches:
        print(f"File {file_path} contains {len(matches)} matches.")

import re

file_path = "Backend/litellm/proxy/middleware/in_flight_requests_middleware.py"
with open(file_path, "r") as f:
    content = f.read()

content = re.sub(r'(\s*)def _get_gauge\(self\) -> Optional\[Any\]:.*?(?=\n\s*def|\Z)', '', content, flags=re.DOTALL)
content = re.sub(r'(\s*)@staticmethod\n\s*def _get_gauge\(\) -> Optional\[Any\]:.*?(?=\n\s*def|\Z)', '', content, flags=re.DOTALL)

content = re.sub(r'\s*_gauge: Optional\[Any\] = None\n\s*_gauge_init_attempted: bool = False', '', content)
content = re.sub(r'\s*gauge = InFlightRequestsMiddleware\._get_gauge\(\)\n\s*if gauge is not None:\n\s*gauge\.inc\(\)\s*# type: ignore', '', content)
content = re.sub(r'\s*if gauge is not None:\n\s*gauge\.dec\(\)\s*# type: ignore', '', content)
content = re.sub(r'(\s*)Also updates the `litellm_in_flight_requests` Prometheus gauge if\n\s*prometheus_client is installed\. The gauge is lazily initialised on the\n\s*first request so that PROMETHEUS_MULTIPROC_DIR is already set by the time\n\s*we register the metric\. Initialisation is attempted only once — if\n\s*prometheus_client is absent the class remembers and never retries\.', '', content)
content = re.sub(r'(\s*)Prometheus gauge `litellm_in_flight_requests`\.', '', content)

with open(file_path, "w") as f:
    f.write(content)

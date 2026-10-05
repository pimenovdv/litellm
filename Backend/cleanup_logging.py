import re
import os

file_path = "Backend/litellm/litellm_core_utils/litellm_logging.py"
with open(file_path, "r") as f:
    content = f.read()

# remove ddtrace
content = re.sub(r'from ddtrace import tracer\s*\n', '', content)
content = re.sub(r'import ddtrace\n', '', content)
content = re.sub(r'from litellm\.proxy\.dd_span_tagger import tag_datadog_span\n', '', content)


with open(file_path, "w") as f:
    f.write(content)

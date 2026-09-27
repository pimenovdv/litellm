with open("Backend/litellm/llms/custom_httpx/llm_http_handler.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "from litellm.litellm_core_utils.litellm_logging import Logging as _LiteLLMLoggingObj" in line:
        if "AnthropicMessagesStreamingResponse" in lines[i+1]:
            lines.pop(i+1)
            lines.pop(i+1)

with open("Backend/litellm/llms/custom_httpx/llm_http_handler.py", "w") as f:
    f.writelines(lines)

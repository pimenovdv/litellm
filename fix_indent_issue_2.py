with open("Backend/litellm/llms/custom_httpx/llm_http_handler.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "AnthropicMessagesStreamingResponse," in line and "stream:" in lines[i-1] and "anthropic_messages_stream_hidden_params," in lines[i+1]:
        continue
    if "anthropic_messages_stream_hidden_params," in line and "AnthropicMessagesStreamingResponse," in lines[i-1]:
        continue
    if "            )" in line and "anthropic_messages_stream_hidden_params," in lines[i-1]:
        continue
    new_lines.append(line)

with open("Backend/litellm/llms/custom_httpx/llm_http_handler.py", "w") as f:
    f.writelines(new_lines)

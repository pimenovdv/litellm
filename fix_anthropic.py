with open("Backend/litellm/proxy/pass_through_endpoints/llm_provider_handlers/anthropic_passthrough_logging_handler.py", "r") as f:
    lines = f.readlines()
with open("Backend/litellm/proxy/pass_through_endpoints/llm_provider_handlers/anthropic_passthrough_logging_handler.py", "w") as f:
    for i, line in enumerate(lines):
        if "ModelResponseIterator as AnthropicModelResponseIterator," in line:
            f.write("from litellm.llms.anthropic.chat.transformation import (\n")
            f.write(line)
        else:
            f.write(line)

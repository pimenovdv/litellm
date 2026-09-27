with open("Backend/litellm/proxy/pass_through_endpoints/llm_provider_handlers/anthropic_passthrough_logging_handler.py", "r") as f:
    lines = f.readlines()
with open("Backend/litellm/proxy/pass_through_endpoints/llm_provider_handlers/anthropic_passthrough_logging_handler.py", "w") as f:
    for line in lines:
        if "from litellm.types.utils import Choices, SpecialEnums" in line:
            f.write("        from litellm.types.utils import Choices, SpecialEnums\n")
        else:
            f.write(line)

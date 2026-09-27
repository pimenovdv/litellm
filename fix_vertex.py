with open("Backend/litellm/proxy/pass_through_endpoints/llm_provider_handlers/vertex_passthrough_logging_handler.py", "r") as f:
    lines = f.readlines()
with open("Backend/litellm/proxy/pass_through_endpoints/llm_provider_handlers/vertex_passthrough_logging_handler.py", "w") as f:
    for line in lines:
        if "from litellm.llms.base_llm.base_model_iterator import (" in line:
            f.write("            from litellm.llms.base_llm.base_model_iterator import (\n")
        elif "BaseModelResponseIterator," in line:
            f.write("                BaseModelResponseIterator,\n")
        elif "            )" in line:
            f.write("            )\n")
        else:
            f.write(line)

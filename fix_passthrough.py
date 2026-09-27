with open("Backend/litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py", "r") as f:
    lines = f.readlines()
with open("Backend/litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py", "w") as f:
    for line in lines:
        if line.strip() == "litellm.LITELLM_ROUTING = True":
            f.write(" " * 12 + "litellm.LITELLM_ROUTING = True\n")
        else:
            f.write(line)

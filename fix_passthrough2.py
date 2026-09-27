with open("Backend/litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py", "r") as f:
    lines = f.readlines()
with open("Backend/litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py", "w") as f:
    for line in lines:
        if line.strip() == "construct_target_url,":
            f.write(" " * 4 + "construct_target_url,\n")
        else:
            f.write(line)

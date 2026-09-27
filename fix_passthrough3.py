with open("Backend/litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py", "r") as f:
    lines = f.readlines()
with open("Backend/litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py", "w") as f:
    for line in lines:
        if line.strip() in ["get_vertex_location_from_url,", "get_vertex_model_id_from_url,", "get_vertex_project_id_from_url,"]:
            f.write(" " * 4 + line.strip() + "\n")
        else:
            f.write(line)

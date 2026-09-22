with open("Backend/litellm/proxy/common_utils/callback_utils.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.strip() == "elif isinstance(callback, str) and callback == \"presidio\":":
        new_lines.append(line)
        new_lines.append("                from litellm.proxy.guardrails.init_guardrails import _OPTIONAL_PresidioPIIMasking\n")
        skip = True
    elif line.strip() == "elif isinstance(callback, str) and callback == \"lakera_prompt_injection\":":
        new_lines.append(line)
        new_lines.append("                from litellm.proxy.guardrails.init_guardrails import lakeraAI_Moderation\n")
        skip = True
    elif line.strip() == "elif isinstance(callback, str) and callback == \"aporia_prompt_injection\":":
        new_lines.append(line)
        new_lines.append("                from litellm.proxy.guardrails.init_guardrails import AporiaGuardrail\n")
        skip = True
    elif skip and line.strip() == "":
        skip = False
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open("Backend/litellm/proxy/common_utils/callback_utils.py", "w") as f:
    f.writelines(new_lines)

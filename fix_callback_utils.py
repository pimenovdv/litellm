import re

with open("Backend/litellm/proxy/common_utils/callback_utils.py", "r") as f:
    content = f.read()

# Fix presidio import
content = re.sub(
    r'(\s+)((?:from litellm\.proxy\.guardrails\.guardrail_hooks\.presidio import )?_OPTIONAL_PresidioPIIMasking,\n\s+\))',
    r'\1from litellm.proxy.guardrails.guardrail_hooks.presidio import (\n\1    _OPTIONAL_PresidioPIIMasking,\n\1)',
    content
)

# Fix lakera_prompt_injection import
content = re.sub(
    r'(\s+)((?:from litellm\.proxy\.guardrails\.guardrail_hooks\.lakera_ai import )?lakeraAI_Moderation,\n\s+\))',
    r'\1from litellm.proxy.guardrails.guardrail_hooks.lakera_ai import (\n\1    lakeraAI_Moderation,\n\1)',
    content
)

# Fix aporia_prompt_injection import
content = re.sub(
    r'(\s+)((?:from litellm\.proxy\.guardrails\.guardrail_hooks\.aporia import )?AporiaGuardrail,\n\s+\))',
    r'\1from litellm.proxy.guardrails.guardrail_hooks.aporia import (\n\1    AporiaGuardrail,\n\1)',
    content
)

# Fix pangea_prompt_injection import
content = re.sub(
    r'(\s+)((?:from litellm\.proxy\.guardrails\.guardrail_hooks\.pangea_ai import )?PangeaAModeration,\n\s+\))',
    r'\1from litellm.proxy.guardrails.guardrail_hooks.pangea_ai import (\n\1    PangeaAModeration,\n\1)',
    content
)

# Fix prompt_injection import
content = re.sub(
    r'(\s+)((?:from litellm\.proxy\.guardrails\.guardrail_hooks\.prompt_injection_detection import )?_OPTIONAL_PromptInjectionDetection,\n\s+\))',
    r'\1from litellm.proxy.guardrails.guardrail_hooks.prompt_injection_detection import (\n\1    _OPTIONAL_PromptInjectionDetection,\n\1)',
    content
)

# Fix hide_secrets import
content = re.sub(
    r'(\s+)((?:from litellm\.proxy\.guardrails\.guardrail_hooks\.hide_secrets import )?_OPTIONAL_HideSecrets,\n\s+\))',
    r'\1from litellm.proxy.guardrails.guardrail_hooks.hide_secrets import (\n\1    _OPTIONAL_HideSecrets,\n\1)',
    content
)

# Fix pii_masking import
content = re.sub(
    r'(\s+)((?:from litellm\.proxy\.guardrails\.guardrail_hooks\.pii_masking import )?_OPTIONAL_PIIMasking,\n\s+\))',
    r'\1from litellm.proxy.guardrails.guardrail_hooks.pii_masking import (\n\1    _OPTIONAL_PIIMasking,\n\1)',
    content
)

with open("Backend/litellm/proxy/common_utils/callback_utils.py", "w") as f:
    f.write(content)

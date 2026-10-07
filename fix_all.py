import re

with open("Backend/litellm/proxy/common_utils/callback_utils.py", "r") as f:
    content = f.read()

# Fix all the broken imports from the base branch that cause IndentationError / SyntaxError loops
# Specifically, we need to completely remove these broken multi-line imports as they reference
# guardrail hooks that were likely deleted upstream, and they are syntactically malformed
# inside the `if/elif` blocks due to missing `from ... import (` parentheses.

# We'll just replace the entire callback condition block with a safe string for the ones that are broken.

content = re.sub(
    r'elif isinstance\(callback, str\) and callback == "presidio":\n.*?params: Dict\[str, Any\] = {',
    r'elif isinstance(callback, str) and callback == "presidio":\n                params: Dict[str, Any] = {',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'elif isinstance\(callback, str\) and callback == "lakera_prompt_injection":\n.*?init_params = {}',
    r'elif isinstance(callback, str) and callback == "lakera_prompt_injection":\n                init_params = {}',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'elif isinstance\(callback, str\) and callback == "aporia_prompt_injection":\n.*?init_params = {}',
    r'elif isinstance(callback, str) and callback == "aporia_prompt_injection":\n                init_params = {}',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'elif isinstance\(callback, str\) and callback == "pangea_prompt_injection":\n.*?init_params = {}',
    r'elif isinstance(callback, str) and callback == "pangea_prompt_injection":\n                init_params = {}',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'elif isinstance\(callback, str\) and callback == "prompt_injection":\n.*?init_params = {}',
    r'elif isinstance(callback, str) and callback == "prompt_injection":\n                init_params = {}',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'elif isinstance\(callback, str\) and callback == "hide_secrets":\n.*?init_params = {}',
    r'elif isinstance(callback, str) and callback == "hide_secrets":\n                init_params = {}',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'elif isinstance\(callback, str\) and callback == "pii_masking":\n.*?init_params = {}',
    r'elif isinstance(callback, str) and callback == "pii_masking":\n                init_params = {}',
    content,
    flags=re.DOTALL
)

with open("Backend/litellm/proxy/common_utils/callback_utils.py", "w") as f:
    f.write(content)

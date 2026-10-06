import os

filepath = "Backend/litellm/proxy/auth/user_api_key_auth.py"
with open(filepath, "r") as f:
    content = f.read()

bad_string = """        try:
        from litellm.exceptions import BudgetExceededError
    except ImportError:
        class BudgetExceededError(Exception): pass
    if isinstance(r, (ProxyException, BudgetExceededError)):"""
good_string = """        try:
            from litellm.exceptions import BudgetExceededError
        except ImportError:
            class BudgetExceededError(Exception): pass
        if isinstance(r, (ProxyException, BudgetExceededError)):"""

if bad_string in content:
    content = content.replace(bad_string, good_string)

with open(filepath, "w") as f:
    f.write(content)

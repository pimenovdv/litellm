import os

filepath = "Backend/litellm/__init__.py"
with open(filepath, "r") as f:
    content = f.read()

bad_string = "    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')"

good_string_2 = """    if name == 'BudgetExceededError':
        from litellm.exceptions import BudgetExceededError
        return BudgetExceededError
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')"""

if bad_string in content:
    content = content.replace(bad_string, good_string_2)

with open(filepath, "w") as f:
    f.write(content)

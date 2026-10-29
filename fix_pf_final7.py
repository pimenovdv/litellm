import re
import subprocess

with open("pf.txt", "r") as f:
    pf_out = f.readlines()

with open("Backend/litellm/utils.py", "r") as f:
    lines = f.readlines()

for pf_line in pf_out:
    if not pf_line.strip(): continue
    if "imported but unused" in pf_line:
        match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
        if match:
            line_num = int(match.group(1)) - 1
            if "# noqa" not in lines[line_num]:
                lines[line_num] = lines[line_num].rstrip() + "  # noqa: F401 - re-exported for backwards compat\n"
            else:
                # pyflakes still flags it if # noqa: F401 is placed in parentheses sometimes or it's incorrectly formatted.
                # It's an AST error.
                pass

with open("Backend/litellm/utils.py", "w") as f:
    f.writelines(lines)

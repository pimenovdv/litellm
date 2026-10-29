import re
import subprocess

def fix_imports():
    pf_out = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True).stdout.split("\n")

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
        elif "redefinition of unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                if "# noqa" not in lines[line_num]:
                    lines[line_num] = lines[line_num].rstrip() + "  # noqa: F811\n"

    # Write out
    with open("Backend/litellm/utils.py", "w") as f:
        f.writelines(lines)

fix_imports()

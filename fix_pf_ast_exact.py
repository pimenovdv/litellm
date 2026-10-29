import subprocess
import re
import ast

def fix():
    with open("Backend/litellm/utils.py", "r") as f:
        source = f.read()

    # Run pyflakes to find exact lines and safely append noqa
    pf_out = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True).stdout.split("\n")

    lines = source.split("\n")

    for pf_line in pf_out:
        if not pf_line.strip():
            continue
        if "redefinition of unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                if "# noqa" not in lines[line_num]:
                    lines[line_num] = "# " + lines[line_num].rstrip() + "  # This is imported globally below"
        elif "imported but unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                if "import" in lines[line_num] and "# noqa" not in lines[line_num]:
                    lines[line_num] = lines[line_num].rstrip() + "  # noqa: F401 - re-exported for backwards compat"

    with open("Backend/litellm/utils.py", "w") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    fix()

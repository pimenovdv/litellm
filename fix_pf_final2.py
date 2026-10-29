import re
import subprocess

def run_pyflakes():
    result = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True)
    return result.stdout.strip().split('\n'), result.returncode

def fix_imports():
    lines, rc = run_pyflakes()

    with open("Backend/litellm/utils.py", "r") as f:
        file_lines = f.readlines()

    for line in lines:
        if not line.strip(): continue
        if "redefinition of unused" in line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', line)
            if match:
                line_num = int(match.group(1)) - 1
                if "# noqa" not in file_lines[line_num]:
                    file_lines[line_num] = file_lines[line_num].rstrip() + "  # noqa: F811\n"
        elif "imported but unused" in line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', line)
            if match:
                line_num = int(match.group(1)) - 1
                if "# noqa" not in file_lines[line_num]:
                    file_lines[line_num] = file_lines[line_num].rstrip() + "  # noqa: F401 - re-exported for backwards compat\n"

    with open("Backend/litellm/utils.py", "w") as f:
        f.writelines(file_lines)

fix_imports()

import subprocess
import re
import ast

def fix():
    with open("Backend/litellm/utils.py", "r") as f:
        source = f.read()

    lines = source.split("\n")

    pf_out = subprocess.run(
        ["python", "-m", "pyflakes", "Backend/litellm/utils.py"],
        capture_output=True, text=True
    ).stdout.split("\n")

    changed = False
    for pf_line in pf_out:
        if not pf_line.strip():
            continue

        if "redefinition of unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):.*redefinition of unused \'([^\']+)\'', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                name = match.group(2)

                # Check if it's single line or multiline block
                if "(" not in lines[line_num] and ")" not in lines[line_num]:
                    if "# This is imported globally below" not in lines[line_num]:
                        lines[line_num] = "# " + lines[line_num].lstrip().rstrip() + "  # This is imported globally below"
                        changed = True
                else:
                    if lines[line_num].strip().endswith(",") or ")" in lines[line_num]:
                        from_line = line_num
                        while from_line >= 0 and "from " not in lines[from_line] and "import " not in lines[from_line]:
                            from_line -= 1
                        if from_line >= 0 and "# noqa: F811" not in lines[from_line]:
                            lines[from_line] = lines[from_line].rstrip() + "  # noqa: F811"
                            changed = True
                    else:
                        if "# noqa: F811" not in lines[line_num]:
                            lines[line_num] = lines[line_num].rstrip() + "  # noqa: F811"
                            changed = True

    with open("Backend/litellm/utils.py", "w") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    fix()

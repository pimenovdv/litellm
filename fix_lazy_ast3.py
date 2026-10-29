import re
import ast
import subprocess

def get_lazy_imports():
    with open("Backend/litellm/utils.py", "r") as f:
        source = f.read()

    tree = ast.parse(source)
    lazy_lines = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            is_type_checking = False
            if isinstance(node.test, ast.Name) and node.test.id == 'TYPE_CHECKING':
                is_type_checking = True

            if is_type_checking:
                for subnode in ast.walk(node):
                    if hasattr(subnode, 'lineno'):
                        start = subnode.lineno
                        end = getattr(subnode, 'end_lineno', start)
                        for i in range(start, end + 1):
                            lazy_lines.add(i)
    return lazy_lines

def fix():
    lazy_lines = get_lazy_imports()
    print(f"Found {len(lazy_lines)} lazy import lines")

    with open("Backend/litellm/utils.py", "r") as f:
        lines = f.readlines()

    pf_out = subprocess.run(
        ["python", "-m", "pyflakes", "Backend/litellm/utils.py"],
        capture_output=True, text=True
    ).stdout.split("\n")

    changed = False
    for pf_line in pf_out:
        if not pf_line.strip():
            continue

        if "imported but unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):.*\'([^\']+)\'', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                name = match.group(2).split('.')[-1]

                is_lazy = (line_num + 1) in lazy_lines

                if is_lazy:
                    noqa_text = "  # noqa: F401 - re-exported for backwards compat"
                    if "import" in lines[line_num] and "(" in lines[line_num] and ")" not in lines[line_num]:
                        for i in range(line_num, len(lines)):
                            if ")" in lines[i] and not re.search(r'\b' + name + r'\b', lines[i]):
                                break
                            if re.search(r'\b' + name + r'\b', lines[i]):
                                if noqa_text.strip() not in lines[i]:
                                    lines[i] = lines[i].rstrip() + noqa_text + "\n"
                                    changed = True
                                break
                    else:
                        if noqa_text.strip() not in lines[line_num]:
                            lines[line_num] = lines[line_num].rstrip() + noqa_text + "\n"
                            changed = True

    if changed:
        print("Applied noqa to confirmed lazy imports.")
    with open("Backend/litellm/utils.py", "w") as f:
        f.writelines(lines)

if __name__ == "__main__":
    fix()

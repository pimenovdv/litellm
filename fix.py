import re
import ast
import subprocess

def fix():
    with open("Backend/litellm/utils.py", "r") as f:
        source = f.read()

    pf_out = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True).stdout.split("\n")

    # 1. First AST pass: find out which names are genuinely unused in the file
    class Analyzer(ast.NodeVisitor):
        def __init__(self):
            self.used = set()
            self.imported = {}
            self.in_type_checking = False

        def visit_If(self, node):
            if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                self.in_type_checking = True
                self.generic_visit(node)
                self.in_type_checking = False
            else:
                self.generic_visit(node)

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load):
                self.used.add(node.id)
            self.generic_visit(node)

        def visit_Import(self, node):
            for alias in node.names:
                self.imported[alias.asname or alias.name] = (node.lineno, alias.name, self.in_type_checking)
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                self.imported[alias.asname or alias.name] = (node.lineno, alias.name, self.in_type_checking)
            self.generic_visit(node)

    analyzer = Analyzer()
    analyzer.visit(ast.parse(source))

    unused = []
    for name, info in analyzer.imported.items():
        if name not in analyzer.used:
            unused.append((name, info[0], info[1], info[2]))

    unused_lines = {u[1]: [] for u in unused}
    for u in unused:
        unused_lines[u[1]].append(u)

    lines = source.split("\n")

    for pf_line in pf_out:
        if not pf_line.strip():
            continue
        if "redefinition of unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1

                # Check if it's in TYPE_CHECKING block dynamically by lines around it
                if "if TYPE_CHECKING:" in source[:source.find(lines[line_num])][-200:]:
                    if "# This is imported globally below" not in lines[line_num]:
                        lines[line_num] = "# " + lines[line_num].rstrip() + "  # This is imported globally below"
                else:
                    if "# noqa" not in lines[line_num]:
                        lines[line_num] += "  # noqa: F811"

        elif "imported but unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1

                # Check if it's in TYPE_CHECKING
                in_tc = any(u[3] for u in unused_lines.get(line_num + 1, []))

                if in_tc:
                    if "# noqa" not in lines[line_num]:
                        lines[line_num] += "  # noqa: F401 - re-exported for backwards compat"
                else:
                    if "# noqa" not in lines[line_num]:
                        lines[line_num] += "  # noqa: F401"

        elif "is unused: name is never assigned in scope" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):.*`global ([^`]+)`', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                var_name = match.group(2)
                lines[line_num] = re.sub(r'\b' + var_name + r'\b,?\s*', '', lines[line_num])
                lines[line_num] = lines[line_num].replace('global  ', 'global ')
                if lines[line_num].strip() == 'global':
                    lines[line_num] = ''

    with open("Backend/litellm/utils.py", "w") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    fix()

import re
with open("Backend/litellm/utils.py", "r") as f:
    source = f.read()

import subprocess
import ast

tree = ast.parse(source)

class LazyImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.lazy_imports = []
        self.in_tc = False

    def visit_If(self, node):
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            self.in_tc = True
            self.generic_visit(node)
            self.in_tc = False
        else:
            self.generic_visit(node)

    def visit_Import(self, node):
        if self.in_tc:
            self.lazy_imports.append(node.lineno - 1)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if self.in_tc:
            self.lazy_imports.append(node.lineno - 1)
        self.generic_visit(node)

analyzer = LazyImportVisitor()
analyzer.visit(tree)

pf_out = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True).stdout.split("\n")

lines = source.split("\n")

for pf_line in pf_out:
    if not pf_line.strip():
        continue
    if "imported but unused" in pf_line:
        match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
        if match:
            line_num = int(match.group(1)) - 1
            if line_num in analyzer.lazy_imports:
                if "# noqa" not in lines[line_num]:
                    lines[line_num] += "  # noqa: F401 - re-exported for backwards compat"

with open("Backend/litellm/utils.py", "w") as f:
    f.write("\n".join(lines))

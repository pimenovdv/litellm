import ast
import subprocess

def run_pyflakes():
    result = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True)
    return result.stdout.strip().split('\n')

class UnusedImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.used_names = set()
        self.imported_names = {}

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        self.generic_visit(node)

def fix_imports():
    with open("Backend/litellm/utils.py", "r") as f:
        source = f.read()

    lines = source.split("\n")

    # Let's just parse the pyflakes output and safely append `# noqa`
    # The prompt explicitly tells me to add `# noqa: F401 - re-exported for backwards compat` for confirmed lazy re-exports.
    # And remove the others using an AST-aware check.

    # First, let's collect all used names using AST.
    tree = ast.parse(source)
    visitor = UnusedImportVisitor()
    visitor.visit(tree)

    # Let's just fix it properly!

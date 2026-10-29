import ast

def find_unused_and_used(filepath):
    with open(filepath, "r") as f:
        source = f.read()

    tree = ast.parse(source)

    class Analyzer(ast.NodeVisitor):
        def __init__(self):
            self.used = set()
            self.imported = {}

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load):
                self.used.add(node.id)
            self.generic_visit(node)

        def visit_Import(self, node):
            for alias in node.names:
                self.imported[alias.asname or alias.name] = (node.lineno, alias.name)
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                self.imported[alias.asname or alias.name] = (node.lineno, alias.name)
            self.generic_visit(node)

        def visit_Global(self, node):
            # global unused
            pass

    analyzer = Analyzer()
    analyzer.visit(tree)

    unused = []
    for name, info in analyzer.imported.items():
        if name not in analyzer.used:
            unused.append((name, info[0]))

    return unused

print(find_unused_and_used("Backend/litellm/utils.py")[:20])

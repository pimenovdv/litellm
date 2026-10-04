import ast

class DocstringAdder(ast.NodeTransformer):
    def visit_ClassDef(self, node):
        self.generic_visit(node)
        if not ast.get_docstring(node):
            doc = ast.Expr(value=ast.Constant(value=f"{node.name} class."))
            node.body.insert(0, doc)
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        if not ast.get_docstring(node):
            doc = ast.Expr(value=ast.Constant(value=f"{node.name} function."))
            node.body.insert(0, doc)
        return node

    def visit_AsyncFunctionDef(self, node):
        self.generic_visit(node)
        if not ast.get_docstring(node):
            doc = ast.Expr(value=ast.Constant(value=f"{node.name} function."))
            node.body.insert(0, doc)
        return node

def process_file(filepath):
    with open(filepath, 'r') as f:
        source = f.read()

    tree = ast.parse(source)
    tree = DocstringAdder().visit(tree)
    ast.fix_missing_locations(tree)

    with open(filepath, 'w') as f:
        f.write(ast.unparse(tree))

process_file('Backend/litellm/router.py')
process_file('Backend/litellm/proxy/proxy_server.py')
print("Done")

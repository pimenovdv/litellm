import ast
import astunparse

file_path = "Backend/litellm/proxy/health_endpoints/_health_endpoints.py"
with open(file_path, "r") as f:
    source = f.read()

class Transformer(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        if node.module == "litellm.proxy.dd_span_tagger":
            return None
        return node

    def visit_If(self, node):
        self.generic_visit(node)

        # Check if node is checking for datadog in health_check_services
        if isinstance(node.test, ast.Compare):
            if isinstance(node.test.left, ast.Name) and node.test.left.id == "service":
                if isinstance(node.test.comparators[0], ast.Constant) and isinstance(node.test.comparators[0].value, str) and "datadog" in node.test.comparators[0].value:
                    return None
        return node

tree = ast.parse(source)
transformer = Transformer()
new_tree = transformer.visit(tree)
ast.fix_missing_locations(new_tree)

new_source = astunparse.unparse(new_tree)
with open(file_path, "w") as f:
    f.write(new_source)

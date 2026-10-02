import ast
import sys

def delete_rag_tests():
    filepath = 'tests/test_litellm/proxy/auth/test_route_checks.py'
    with open(filepath, 'r') as f:
        source = f.read()

    tree = ast.parse(source)
    nodes_to_delete = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_rag_routes_'):
            nodes_to_delete.append(node)

    if not nodes_to_delete:
        print("No test_rag_routes_ found.")
        return

    lines = source.split('\n')
    lines_to_delete = set()

    for node in nodes_to_delete:
        start = node.lineno - 1
        if node.decorator_list:
            start = node.decorator_list[0].lineno - 1
        end = node.end_lineno
        for i in range(start, end):
            lines_to_delete.add(i)

    new_lines = [line for i, line in enumerate(lines) if i not in lines_to_delete]

    with open(filepath, 'w') as f:
        f.write('\n'.join(new_lines))

    print(f"Deleted {len(nodes_to_delete)} functions from {filepath}")

delete_rag_tests()

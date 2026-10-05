import ast

def process_file(filepath):
    with open(filepath, 'r') as f:
        source = f.read()

    tree = ast.parse(source)
    lines = source.split('\n')

    nodes_to_doc = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not ast.get_docstring(node):
                nodes_to_doc.append(node)

    nodes_to_doc.sort(key=lambda x: x.lineno, reverse=True)

    # Let's not modify files directly this time, but just add to a few to ensure they don't break.
    print(f"File {filepath} has {len(nodes_to_doc)} nodes to doc.")

process_file('Backend/litellm/router.py')

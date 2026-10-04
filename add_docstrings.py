import ast

def check_docstrings(filepath):
    with open(filepath, 'r') as f:
        source = f.read()

    tree = ast.parse(source)
    missing = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check if it has a docstring
            if not ast.get_docstring(node):
                missing.append((node.name, getattr(node, 'lineno', -1)))

    return missing

router_missing = check_docstrings('Backend/litellm/router.py')
print(f"Router missing {len(router_missing)} docstrings")
for m in router_missing[:10]:
    print(f"  {m[0]} (line {m[1]})")

proxy_missing = check_docstrings('Backend/litellm/proxy/proxy_server.py')
print(f"\nProxy missing {len(proxy_missing)} docstrings")
for m in proxy_missing[:10]:
    print(f"  {m[0]} (line {m[1]})")

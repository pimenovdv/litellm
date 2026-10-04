import ast

def _get_ast(filepath):
    with open(filepath, 'r') as f:
        return ast.parse(f.read())
print(_get_ast('Backend/litellm/router.py'))

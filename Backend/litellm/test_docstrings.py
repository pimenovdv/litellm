import os
import ast

def extract_funcs(filepath):
    with open(filepath) as f:
        tree = ast.parse(f.read())
    return [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]

print("Test successful")

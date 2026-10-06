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

    nodes_to_doc.sort(key=lambda x: getattr(x, 'lineno', 0), reverse=True)

    for node in nodes_to_doc:
        if hasattr(node, 'body') and len(node.body) > 0:

            # Find the line that actually contains the `def ` or `class ` declaration
            # This handles ignoring decorators which might be multiple lines above
            start_idx = node.lineno - 1
            if hasattr(node, 'decorator_list') and node.decorator_list:
                start_idx = node.decorator_list[-1].end_lineno

            # Make sure start_idx actually points to the `def ` or `class `
            while start_idx < len(lines):
                line_str = lines[start_idx].strip()
                if line_str.startswith('def ') or line_str.startswith('async def ') or line_str.startswith('class '):
                    break
                start_idx += 1

            if start_idx >= len(lines):
                start_idx = node.lineno - 1

            # Now find the trailing ':'
            end_sig_idx = start_idx
            while end_sig_idx < len(lines):
                if ':' in lines[end_sig_idx]:
                    text = '\n'.join(lines[start_idx:end_sig_idx+1])
                    if text.count('(') == text.count(')'):
                        break
                end_sig_idx += 1

            insert_idx = end_sig_idx + 1

            def_line = lines[start_idx]
            base_indent = len(def_line) - len(def_line.lstrip())
            indent = base_indent + 4

            if isinstance(node, ast.ClassDef):
                doc_str = f'{" " * indent}"""{node.name} class."""'
            else:
                doc_str = f'{" " * indent}"""{node.name} function."""'

            lines.insert(insert_idx, doc_str)

    with open(filepath, 'w') as f:
        f.write('\n'.join(lines))

process_file('Backend/litellm/router.py')
process_file('Backend/litellm/proxy/proxy_server.py')
print("Done")

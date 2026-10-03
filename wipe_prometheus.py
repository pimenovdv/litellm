import ast

def process_prometheus_cleanup(filepath):
    with open(filepath, 'r') as f:
        code = f.read()

    tree = ast.parse(code)
    lines = code.splitlines()

    lines_to_keep = []
    in_try = False
    try_start = -1

    for i, line in enumerate(lines):
        if 'try:' in line and 'from prometheus_client import multiprocess' in '\n'.join(lines[i:]):
            in_try = True
            try_start = i
            continue

        if in_try:
            if 'except Exception' in line:
                in_try = False
                # Skip the except block
                continue
            continue

        if 'except Exception' in line and try_start != -1:
            in_try = False
            continue

        if try_start != -1 and not in_try and line.strip().startswith('verbose_proxy_logger.warning'):
             try_start = -1
             continue

        lines_to_keep.append(line)

    # Simplified approach for mark_worker_exit
    new_lines = []
    skip = False
    for i, line in enumerate(lines):
        if "try:" in line and "from prometheus_client import multiprocess" in "".join(lines[i:i+3]):
             skip = True
             continue
        if skip and "except Exception as e:" in line:
             continue
        if skip and "verbose_proxy_logger.warning" in line:
             skip = False
             continue
        if not skip:
             new_lines.append(line)

    # Let's just sed it. It's safer.
    pass

process_prometheus_cleanup('Backend/litellm/proxy/prometheus_cleanup.py')

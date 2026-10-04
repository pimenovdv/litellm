with open("Backend/uv.lock", "r") as f:
    lines = f.readlines()

to_remove = [
    "prometheus-client",
    "opentelemetry-api",
    "opentelemetry-sdk",
    "opentelemetry-exporter-otlp",
    "opentelemetry-instrumentation-fastapi",
    "ddtrace"
]

new_lines = []
skip_next = False
for i, line in enumerate(lines):
    if line.startswith('    { name = '):
        name = line.split('"')[1]
        if name in to_remove:
            # wait, we shouldn't blindly delete these from anywhere, but actually only if they are dependencies of litellm.
            pass

    new_lines.append(line)

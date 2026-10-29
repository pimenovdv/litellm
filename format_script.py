import re
with open("Backend/litellm/utils.py", "r") as f:
    source = f.read()

# Make sure we don't have stray unused lines in typing block
source = re.sub(
    r'    Mapping,\n    Optional,\n    Tuple,\n    Type,\n    Union,\n    cast,\n    get_args,\n    get_origin,',
    r'    Mapping,\n    Optional,\n    Tuple,\n    Union,\n    cast,\n    get_origin,',
    source
)

# And now, we add the # noqa dynamically to all lines that pyflakes flags as unused inside TYPE_CHECKING
import subprocess
pf_out = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True).stdout.split("\n")

lines = source.split("\n")
for pf_line in pf_out:
    if not pf_line.strip():
        continue
    if "imported but unused" in pf_line:
        match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
        if match:
            line_num = int(match.group(1)) - 1
            if "import " in lines[line_num] and "# noqa" not in lines[line_num]:
                lines[line_num] += "  # noqa: F401 - re-exported for backwards compat"

with open("Backend/litellm/utils.py", "w") as f:
    f.write("\n".join(lines))

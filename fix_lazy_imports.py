import re
with open("Backend/litellm/utils.py", "r") as f:
    content = f.read()

lines = content.split('\n')
in_type_checking = False
for i, line in enumerate(lines):
    if "if TYPE_CHECKING:" in line:
        in_type_checking = True
    elif line and not line.startswith(" ") and not line.startswith("if "):
        in_type_checking = False

    if in_type_checking:
        if "from litellm" in line and "import" in line and "# noqa" not in line:
            lines[i] = line + "  # noqa: F401 - re-exported for backwards compat"
        elif "import " in line and "from " not in line and "# noqa" not in line:
            lines[i] = line + "  # noqa: F401 - re-exported for backwards compat"

with open("Backend/litellm/utils.py", "w") as f:
    f.write("\n".join(lines))

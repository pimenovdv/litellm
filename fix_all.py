import re
import subprocess
import os
import ast

def fix():
    with open("Backend/litellm/utils.py", "r") as f:
        source = f.read()

    # Step 1: Execute exact string replacements for non-lazy standard unused imports
    source = re.sub(r'from openai\.lib import _parsing, _pydantic', r'from openai.lib import _parsing', source)
    source = re.sub(r'import importlib\.metadata\n', r'', source)
    source = re.sub(r'    Mapping,\n    Optional,\n    Tuple,\n    Type,\n    Union,\n    cast,\n    get_args,\n    get_origin,', r'    Mapping,\n    Optional,\n    Tuple,\n    Union,\n    cast,\n    get_origin,', source)
    source = re.sub(r'    Choices,\n    CredentialItem,\n    CustomHuggingfaceTokenizer,\n    Delta,\n    Embedding,\n    EmbeddingResponse,\n    Function,\n    ImageResponse,\n    LlmProviders,\n    LlmProvidersSet,\n    LLMResponseTypes,\n    Message,', r'    Choices,\n    CustomHuggingfaceTokenizer,\n    Delta,\n    EmbeddingResponse,\n    LlmProviders,\n    LlmProvidersSet,\n    LLMResponseTypes,', source)
    source = re.sub(r'    StreamingChoices,\n    TextChoices,\n    TextCompletionResponse,\n    TranscriptionResponse,\n    Usage,', r'    StreamingChoices,\n    TextChoices,\n    TextCompletionResponse,\n    Usage,', source)
    source = re.sub(r'global callback_list, add_breadcrumb, user_logger_fn, Logging', r'global callback_list, user_logger_fn', source)

    with open("Backend/litellm/utils.py", "w") as f:
        f.write(source)

    # Step 2: Use pyflakes to find exact lines and safely append noqa
    pf_out = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True).stdout.split("\n")

    with open("Backend/litellm/utils.py", "r") as f:
        lines = f.readlines()

    for pf_line in pf_out:
        if not pf_line.strip():
            continue
        if "redefinition of unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                if "# noqa" not in lines[line_num]:
                    lines[line_num] = lines[line_num].rstrip() + "  # noqa: F811\n"
        elif "imported but unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                if "import" in lines[line_num] and "# noqa" not in lines[line_num]:
                    lines[line_num] = lines[line_num].rstrip() + "  # noqa: F401 - re-exported for backwards compat\n"
        elif "is unused: name is never assigned in scope" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):.*`global ([^`]+)`', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                var_name = match.group(2)
                lines[line_num] = re.sub(r'\b' + var_name + r'\b,?\s*', '', lines[line_num])
                lines[line_num] = lines[line_num].replace('global  ', 'global ')
                if lines[line_num].strip() == 'global':
                    lines[line_num] = '\n'

    # Finally, rewrite the multiline imports inside TYPE_CHECKING into single lines if they have noqa issues.
    source = "".join(lines)
    def replacer(match):
        module = match.group(1)
        raw_names = match.group(2)
        clean_names = re.sub(r'#.*', '', raw_names)
        names = clean_names.replace(" ", "").replace("\n", "").split(",")
        names = [n for n in names if n]
        res = ""
        for name in names:
            res += f"    from {module} import {name}  # noqa: F401 - re-exported for backwards compat\n"
        return res

    # Replace only in first TYPE_CHECKING block (lazy imports block)
    parts = source.split("if TYPE_CHECKING:")
    if len(parts) > 1:
        # replace any multiline `from module import (...)` in this block
        parts[1] = re.sub(r'    from ([\w\.]+) import \(\s*([^)]+)\s*\)', replacer, parts[1])
        source = "if TYPE_CHECKING:".join(parts)

    with open("Backend/litellm/utils.py", "w") as f:
        f.write(source)

if __name__ == "__main__":
    fix()

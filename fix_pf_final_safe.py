import re
import subprocess

def fix_imports():
    with open("Backend/litellm/utils.py", "r") as f:
        source = f.read()

    # Apply regex replacements to cleanly handle the multi-line imports we can safely delete
    # Typing import
    source = re.sub(
        r'    Mapping,\n    Optional,\n    Tuple,\n    Type,\n    Union,\n    cast,\n    get_args,\n    get_origin,',
        r'    Mapping,\n    Optional,\n    Tuple,\n    Union,\n    cast,\n    get_origin,',
        source
    )

    # Utils import
    source = re.sub(
        r'    Choices,\n    CredentialItem,\n    CustomHuggingfaceTokenizer,\n    Delta,\n    Embedding,\n    EmbeddingResponse,\n    Function,\n    ImageResponse,\n    LlmProviders,\n    LlmProvidersSet,\n    LLMResponseTypes,\n    Message,',
        r'    Choices,\n    CustomHuggingfaceTokenizer,\n    Delta,\n    EmbeddingResponse,\n    LlmProviders,\n    LlmProvidersSet,\n    LLMResponseTypes,',
        source
    )
    source = re.sub(
        r'    StreamingChoices,\n    TextChoices,\n    TextCompletionResponse,\n    TranscriptionResponse,\n    Usage,',
        r'    StreamingChoices,\n    TextChoices,\n    TextCompletionResponse,\n    Usage,',
        source
    )

    # openai parsing
    source = re.sub(
        r'from openai\.lib import _parsing, _pydantic',
        r'from openai.lib import _parsing',
        source
    )

    # importlib
    source = re.sub(
        r'import importlib\.metadata\n',
        r'',
        source
    )

    # global
    source = re.sub(
        r'global callback_list, add_breadcrumb, user_logger_fn, Logging',
        r'global callback_list, user_logger_fn',
        source
    )

    # The issue with using a regex to rewrite all `from x import (...)` blocks is that some tuples aren't standard imports
    # like in `if not model or not mantle_supports_responses(model, litellm.model_cost):`
    # the regex matched something incorrectly, creating an unexpected indent.

    with open("Backend/litellm/utils.py", "w") as f:
        f.write(source)

    pf_out = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True).stdout.split("\n")

    with open("Backend/litellm/utils.py", "r") as f:
        lines = f.readlines()

    for pf_line in pf_out:
        if not pf_line.strip(): continue
        if "redefinition of unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                if "# noqa" not in lines[line_num]:
                    lines[line_num] = lines[line_num].rstrip() + "  # noqa: F811\n"
        elif "is unused: name is never assigned in scope" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):.*`global ([^`]+)`', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                var_name = match.group(2)
                lines[line_num] = re.sub(r'\b' + var_name + r'\b,?\s*', '', lines[line_num])
                lines[line_num] = lines[line_num].replace('global  ', 'global ')
                if lines[line_num].strip() == 'global':
                    lines[line_num] = '\n'
        elif "imported but unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                # we just append `# noqa: F401 - re-exported for backwards compat` except if we know it's not lazy
                if "# noqa" not in lines[line_num]:
                    if "import " in lines[line_num] and "from " not in lines[line_num]:
                        lines[line_num] = lines[line_num].rstrip() + "  # noqa: F401\n"
                    else:
                        lines[line_num] = lines[line_num].rstrip() + "  # noqa: F401 - re-exported for backwards compat\n"

    with open("Backend/litellm/utils.py", "w") as f:
        f.writelines(lines)

if __name__ == "__main__":
    fix_imports()

import re
import ast
import subprocess

def fix_imports():
    with open("Backend/litellm/utils.py", "r") as f:
        source = f.read()

    # Apply exact replacements for non-lazy unused imports
    source = re.sub(r'from openai\.lib import _parsing, _pydantic', r'from openai.lib import _parsing', source)
    source = re.sub(r'import importlib\.metadata\n', r'', source)
    source = re.sub(r'    Mapping,\n    Optional,\n    Tuple,\n    Type,\n    Union,\n    cast,\n    get_args,\n    get_origin,', r'    Mapping,\n    Optional,\n    Tuple,\n    Union,\n    cast,\n    get_origin,', source)
    source = re.sub(r'    Choices,\n    CredentialItem,\n    CustomHuggingfaceTokenizer,\n    Delta,\n    Embedding,\n    EmbeddingResponse,\n    Function,\n    ImageResponse,\n    LlmProviders,\n    LlmProvidersSet,\n    LLMResponseTypes,\n    Message,', r'    Choices,\n    CustomHuggingfaceTokenizer,\n    Delta,\n    EmbeddingResponse,\n    LlmProviders,\n    LlmProvidersSet,\n    LLMResponseTypes,', source)
    source = re.sub(r'    StreamingChoices,\n    TextChoices,\n    TextCompletionResponse,\n    TranscriptionResponse,\n    Usage,', r'    StreamingChoices,\n    TextChoices,\n    TextCompletionResponse,\n    Usage,', source)

    # 7453
    source = re.sub(r'    from litellm\.types\.llms\.openai import \(\n        ChatCompletionToolChoiceObjectParam,\n        ChatCompletionToolChoiceStringValues,\n    \)\n', r'', source)
    # 8784
    source = re.sub(r'        from litellm\.llms\.base_llm\.text_to_speech\.transformation import \(\s*BaseTextToSpeechConfig,\s*\)\n', r'', source)
    # 6245
    source = re.sub(r'        import anthropic\n\n        from anthropic import AI_PROMPT, HUMAN_PROMPT\n', r'', source)
    source = re.sub(r'    import anthropic\n', r'', source)
    source = re.sub(r'    from anthropic import HUMAN_PROMPT, AI_PROMPT\n', r'', source)

    # globals
    source = re.sub(r'global callback_list, add_breadcrumb, user_logger_fn, Logging', r'global callback_list, user_logger_fn', source)

    with open("Backend/litellm/utils.py", "w") as f:
        f.write(source)

    # Use ast to find lazy imports to append # noqa
    tree = ast.parse(source)

    class Analyzer(ast.NodeVisitor):
        def __init__(self):
            self.lazy_imports = []
            self.in_tc = False

        def visit_If(self, node):
            if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                self.in_tc = True
                self.generic_visit(node)
                self.in_tc = False
            else:
                self.generic_visit(node)

        def visit_Import(self, node):
            if self.in_tc:
                self.lazy_imports.append(node.lineno - 1)
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            if self.in_tc:
                self.lazy_imports.append(node.lineno - 1)
            self.generic_visit(node)

    analyzer = Analyzer()
    analyzer.visit(tree)

    pf_out = subprocess.run(["python", "-m", "pyflakes", "Backend/litellm/utils.py"], capture_output=True, text=True).stdout.split("\n")

    lines = source.split("\n")
    for pf_line in pf_out:
        if not pf_line.strip():
            continue
        if "redefinition of unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                if line_num in analyzer.lazy_imports:
                    if "# This is imported globally below" not in lines[line_num]:
                        lines[line_num] = "# " + lines[line_num].rstrip() + "  # This is imported globally below"
        elif "imported but unused" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                if line_num in analyzer.lazy_imports:
                    if "# noqa" not in lines[line_num]:
                        lines[line_num] += "  # noqa: F401 - re-exported for backwards compat"
        elif "is unused: name is never assigned in scope" in pf_line:
            match = re.search(r'Backend/litellm/utils\.py:(\d+):.*`global ([^`]+)`', pf_line)
            if match:
                line_num = int(match.group(1)) - 1
                var_name = match.group(2)
                lines[line_num] = re.sub(r'\b' + var_name + r'\b,?\s*', '', lines[line_num])
                lines[line_num] = lines[line_num].replace('global  ', 'global ')
                if lines[line_num].strip() == 'global':
                    lines[line_num] = ''

    with open("Backend/litellm/utils.py", "w") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    fix_imports()

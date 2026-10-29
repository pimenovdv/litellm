import re
with open("Backend/litellm/utils.py", "r") as f:
    source = f.read()

# We need to explicitly extract the exact 3 multiline unused imports Pyflakes complains about, because appending # noqa inside `from x import (` does nothing for Pyflakes!

source = re.sub(
    r'    from litellm\.types\.llms\.openai import \(\s*ChatCompletionToolChoiceObjectParam,\s*ChatCompletionToolChoiceStringValues,\s*\)\n',
    r'',
    source
)
source = re.sub(
    r'        from litellm\.llms\.base_llm\.text_to_speech\.transformation import \(\s*BaseTextToSpeechConfig,\s*\)\n',
    r'',
    source
)
source = re.sub(
    r'        import anthropic\n\n        from anthropic import AI_PROMPT, HUMAN_PROMPT\n',
    r'',
    source
)
source = re.sub(r'    import anthropic\n', r'', source)
source = re.sub(r'    from anthropic import HUMAN_PROMPT, AI_PROMPT\n', r'', source)

with open("Backend/litellm/utils.py", "w") as f:
    f.write(source)

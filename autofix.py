import re
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

    # 7453
    source = re.sub(
        r'    from litellm\.types\.llms\.openai import \(\n        ChatCompletionToolChoiceObjectParam,\n        ChatCompletionToolChoiceStringValues,\n    \)\n',
        r'',
        source
    )
    # 8784
    source = re.sub(
        r'        from litellm\.llms\.base_llm\.text_to_speech\.transformation import \(\n            BaseTextToSpeechConfig,\n        \)\n',
        r'',
        source
    )
    # 6245
    source = re.sub(r'        import anthropic\n\n        from anthropic import AI_PROMPT, HUMAN_PROMPT\n', r'', source)
    source = re.sub(r'    import anthropic\n', r'', source)
    source = re.sub(r'    from anthropic import HUMAN_PROMPT, AI_PROMPT\n', r'', source)

    with open("Backend/litellm/utils.py", "w") as f:
        f.write(source)

if __name__ == "__main__":
    fix()

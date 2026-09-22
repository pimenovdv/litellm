import re

# Fix main.py
filepath = "Backend/litellm/main.py"
with open(filepath, "r") as f:
    content = f.read()

content = content.replace("    get_args,\n\nfrom litellm._logging import _redact_string", "    get_args,\n)\n\nfrom litellm._logging import _redact_string")
content = content.replace("    strip_reasoning_summary_aliases_from_optional_params,\n\n# Logging is imported lazily", "    strip_reasoning_summary_aliases_from_optional_params,\n)\n\n# Logging is imported lazily")
content = content.replace("    DEFAULT_MOCK_RESPONSE_PROMPT_TOKEN_COUNT,\nfrom litellm.exceptions", "    DEFAULT_MOCK_RESPONSE_PROMPT_TOKEN_COUNT,\n)\nfrom litellm.exceptions")
content = content.replace("    get_audio_file_for_health_check,\nfrom litellm.litellm_core_utils.chat_completion_agentic_loop", "    get_audio_file_for_health_check,\n)\nfrom litellm.litellm_core_utils.chat_completion_agentic_loop")
content = content.replace("    VertexAIModelRoute,\n    get_vertex_ai_model_route,\n)\n", "from litellm.llms.vertex_ai.common_utils import VertexAIModelRoute, get_vertex_ai_model_route\n")
content = content.replace("                    VertexAgentEngineConfig,\n        )", "        from litellm.llms.vertex_ai.vertex_agent_engine.transformation import (\n            VertexAgentEngineConfig,\n        )")
content = content.replace("                    SonioxAudioTranscriptionHandler,\n        )", "        from litellm.llms.soniox.audio_transcription.handler import (\n            SonioxAudioTranscriptionHandler,\n        )")
content = content.replace("                    ElevenLabsTextToSpeechConfig,\n        )", "        from litellm.llms.elevenlabs.text_to_speech.transformation import (\n            ElevenLabsTextToSpeechConfig,\n        )")
content = content.replace("                    VertexAITextToSpeechConfig,\n        )", "        from litellm.llms.vertex_ai.text_to_speech.transformation import (\n            VertexAITextToSpeechConfig,\n        )")
content = content.replace("                    MinimaxTextToSpeechConfig,\n        )", "        from litellm.llms.minimax.text_to_speech.transformation import (\n            MinimaxTextToSpeechConfig,\n        )")
content = content.replace("                    AWSPollyTextToSpeechConfig,\n        )", "        from litellm.llms.aws_polly.text_to_speech.transformation import (\n            AWSPollyTextToSpeechConfig,\n        )")

with open(filepath, "w") as f:
    f.write(content)

# Fix llm_http_handler.py
filepath_handler = "Backend/litellm/llms/custom_httpx/llm_http_handler.py"
with open(filepath_handler, "r") as f:
    content_handler = f.read()

content_handler = content_handler.replace("    AnthropicMessagesStreamingResponse,\n", "")
content_handler = content_handler.replace("    )\n\n    try:", "    try:")
content_handler = content_handler.replace("    from litellm.litellm_core_utils.litellm_logging import Logging as _LiteLLMLoggingObj\n            )\n    from litellm.llms.base_llm.passthrough.transformation import BasePassthroughConfig", "    from litellm.litellm_core_utils.litellm_logging import Logging as _LiteLLMLoggingObj\n    from litellm.llms.base_llm.passthrough.transformation import BasePassthroughConfig")
content_handler = content_handler.replace("        if stream:\n                                        anthropic_messages_stream_hidden_params,\n            )", "        if stream:\n            from litellm.llms.anthropic.chat.transformation import anthropic_messages_stream_hidden_params")
content_handler = content_handler.replace("                            AgenticAnthropicStreamingIterator,\n            )", "            from litellm.llms.anthropic.chat.transformation import AgenticAnthropicStreamingIterator")
content_handler = content_handler.replace("                    FakeAnthropicMessagesStreamIterator,\n        )", "        from litellm.llms.anthropic.chat.transformation import FakeAnthropicMessagesStreamIterator")
content_handler = content_handler.replace("                    AnthropicMessagesStreamHiddenParams,\n                )", "        from litellm.llms.anthropic.chat.transformation import AnthropicMessagesStreamHiddenParams\n        from litellm.llms.anthropic.chat.transformation import AnthropicMessagesStreamingResponse")
content_handler = content_handler.replace("                            FakeAnthropicMessagesStreamIterator,\n            )", "            from litellm.llms.anthropic.chat.transformation import FakeAnthropicMessagesStreamIterator")

with open(filepath_handler, "w") as f:
    f.write(content_handler)

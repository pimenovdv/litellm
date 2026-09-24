import sys

# Read main.py
with open("Backend/litellm/main.py", "r") as f:
    main_lines = f.readlines()

new_main = []
for i, line in enumerate(main_lines):
    if "from litellm.llms.vertex_ai.vertex_agent_engine.transformation import VertexAgentEngineConfig" in line:
        continue
    if "VertexAgentEngineConfig" in line and "import" not in line:
        continue
    if "vertex_agent_engine_config" in line:
        continue
    if line.strip() == ")" and main_lines[i-1].strip() == "# Vertex AI Agent Engine (Reasoning Engines)":
        continue
    if "VertexAIModelRoute," in line and main_lines[i-1].strip() == "from litellm.llms.openai_like.json_loader import JSONProviderRegistry":
        line = "from litellm.llms.vertex_ai.common_utils import (\n    VertexAIModelRoute,\n    get_vertex_ai_model_route,\n)\n"
    if "get_vertex_ai_model_route," in line or ")\n" in line and main_lines[i-2].strip() == "from litellm.llms.openai_like.json_loader import JSONProviderRegistry":
        continue

    new_main.append(line)

with open("Backend/litellm/main.py", "w") as f:
    f.writelines(new_main)

# Read llm_http_handler.py
with open("Backend/litellm/llms/custom_httpx/llm_http_handler.py", "r") as f:
    handler_lines = f.readlines()

new_handler = []
for i, line in enumerate(handler_lines):
    if "from litellm.llms.anthropic.agentic_anthropic_iterator import AgenticAnthropicStreamingIterator" in line:
        continue
    if "AnthropicMessagesStreamingResponse," in line and handler_lines[i-1].strip() == "from litellm.llms.anthropic.chat.transformation import AnthropicConfig":
        line = "from litellm.llms.anthropic.common_utils import (\n    AnthropicMessagesStreamingResponse,\n)\n"
    if ")\n" in line and handler_lines[i-2].strip() == "from litellm.llms.anthropic.chat.transformation import AnthropicConfig":
        continue
    new_handler.append(line)

with open("Backend/litellm/llms/custom_httpx/llm_http_handler.py", "w") as f:
    f.writelines(new_handler)

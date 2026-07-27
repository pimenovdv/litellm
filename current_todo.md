# Текущая задача: Очистка директории `litellm/llms/` от всех провайдеров, кроме `openai`

- [ ] Удалить первую группу директорий провайдеров из `litellm/llms/` (например, `anthropic`, `gemini`, `bedrock`, `bedrock_mantle`, `aws_polly`, `ai21`, `aiml`, `cloudflare`).
- [ ] Удалить вторую группу директорий провайдеров из `litellm/llms/` (например, `azure`, `azure_ai`, `vertex_ai`, `vllm`, `huggingface`, `cohere`, `mistral`).
- [ ] Удалить третью группу директорий провайдеров из `litellm/llms/` (например, `groq`, `databricks`, `watsonx`, `xai`, `together_ai`, `openrouter`).
- [ ] Удалить оставшиеся нецелевые директории и файлы провайдеров из `litellm/llms/`, оставив только `openai`, `openai_like`, `custom_httpx`, `base_llm` и базовые файлы (например, `base.py`, `custom_llm.py`).
- [ ] Очистить `litellm/llms/__init__.py` от специфичного для удаленных провайдеров кода (например, расчета стоимости web search для gemini, anthropic, vertex_ai, xai, perplexity).

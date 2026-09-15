# Текущие задачи (Удаление поддержки сторонних LLM-провайдеров)
- [x] Вырезать все импорты и ссылки, связанные с `anthropic_messages` / `Anthropic` из `Backend/litellm/router.py` и `Backend/litellm/llms/__init__.py`.
- [x] Удалить папку `Backend/litellm/llms/base_llm/google_genai` и связанные с ней импорты/логику из `router.py`.
- [x] Удалить папку `Backend/litellm/llms/base_llm/anthropic_messages` и связанные с ней импорты.
- [x] Очистить другие LLM-провайдеры (Cohere, Vertex, и т.д.) из `Backend/litellm/llms/base_llm/` и `router.py`.

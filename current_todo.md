## Удалить Guardrails (директория Backend/litellm/proxy/guardrails, ссылки в коде)

- [x] Шаг 1: Удалить основные директории Guardrails (`Backend/litellm/proxy/guardrails`, `Backend/litellm/types/proxy/guardrails`, `Backend/litellm/types/guardrails.py`) и обновить `todo.md`.
- [x] Шаг 2: Удалить директории `guardrail_translation` во всех подпапках LLM провайдеров (`Backend/litellm/llms/**/guardrail_translation`) и удалить интеграцию `Backend/litellm/integrations/custom_guardrail.py`.
- [ ] Шаг 3: Удалить связанные тесты Guardrails (`tests/e2e/guardrails`, `tests/guardrails_tests`, `tests/test_litellm/proxy/guardrails`, и другие `*guardrail*` тесты).
- [ ] Шаг 4: Очистить остаточные импорты и ссылки на `guardrails` в `Backend/litellm/proxy/proxy_server.py`, `Backend/litellm/router.py` и `Backend/litellm/utils.py`.

# Текущие задачи (Очистка от RAG, Guardrails, Secret Managers, Telemetry)
- [x] Удалить тесты и CI ссылки RAG (`tests/test_litellm/proxy/rag_endpoints`, `.github/workflows/test-unit-proxy-endpoints.yml`).
- [ ] Удалить исходные файлы RAG (`Backend/litellm/proxy/rag_endpoints`, `Backend/litellm/types/rag.py`, `Backend/litellm/types/integrations/rag`).
- [ ] Удалить файлы Guardrails (директории `Backend/litellm/proxy/guardrails`, `Backend/litellm/types/proxy/guardrails`, `Backend/litellm/types/guardrails.py`, `Backend/litellm/proxy/pass_through_endpoints/passthrough_guardrails.py`).
- [ ] Удалить менеджеры секретов (директория `Backend/litellm/secret_managers`, `Backend/litellm/types/secret_managers`, `Backend/litellm/integrations/custom_secret_manager.py`).
- [ ] Вырезать функционал Telemetry / OpenTelemetry, если таковой еще остался.
- [ ] Проверить и очистить `Backend/litellm/proxy/proxy_server.py` и `Backend/litellm/__init__.py` от импортов и инициализаций удаленных модулей (RAG, Guardrails, Secret Managers).

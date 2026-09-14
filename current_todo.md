# Текущие задачи (Вырезать лишний функционал из ядра системы)
- [x] Вырезать функционал RAG из `Backend/litellm`.
- [ ] Удалить директорию `Backend/litellm/proxy/guardrails/`.
- [ ] Удалить типы `Backend/litellm/types/guardrails.py`, `Backend/litellm/types/proxy/guardrails/` и `Backend/litellm/types/proxy/policy_engine/`.
- [ ] Очистить `Backend/litellm/proxy/proxy_server.py` и `Backend/litellm/router.py` от импортов и логики Guardrails.
- [ ] Отметить удаление Guardrails в `todo.md`.
- [ ] Вырезать сторонние менеджеры секретов из `Backend/litellm`.
- [ ] Вырезать телеметрию из `Backend/litellm`.

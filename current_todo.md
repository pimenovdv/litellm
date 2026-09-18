# Текущие задачи (Вырезание лишнего функционала)
- [x] Найти и проанализировать модули, связанные с RAG, Guardrails, сторонними менеджерами секретов и телеметрией, используя `grep`.
- [x] Найти все оставшиеся ссылки на удалённые модули (`IBMGuardrailsBaseConfigModel`, `IBMDetectorGuardrailConfigModel`, `MCPEndUserPermissionGuardrailConfigModel`) во всём коде с помощью `grep`, проверить, что `mcp_end_user_permission.py` действительно нужно было удалять (удаление отменено, переходим к полному удалению).
- [x] Удалить часть 3 файлов Guardrails (`Backend/litellm/types/proxy/guardrails/guardrail_hooks/azure`, `mcp_jwt_signer`).
- [x] Удалить часть 4 файлов Guardrails (`Backend/litellm/types/proxy/guardrails/guardrail_hooks/ibm`, `mcp_end_user_permission`).
- [ ] Удалить файлы и директории, связанные с RAG, сторонними секретами и телеметрией, проверив ссылки в кодовой базе.
- [ ] Очистить код от импортов и вызовов удаленных модулей, чтобы избежать `ModuleNotFoundError`.

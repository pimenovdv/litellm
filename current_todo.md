# Текущие задачи (Удаление неиспользуемых интеграций)
- [ ] Найти и удалить модули `langfuse` и `datadog` из `Backend/litellm/integrations/`.
- [ ] Удалить поддержку `sentry` и `slack` из системы логирования/интеграций.
- [ ] Очистить ссылки на удаленные модули в `utils.py` и `_lazy_imports_registry.py`.
- [ ] Удалить оставшиеся неиспользуемые скрипты интеграций (lunary, helicone, athina, prometheus, openmeter, supabase и др.) из `Backend/litellm/integrations/`.

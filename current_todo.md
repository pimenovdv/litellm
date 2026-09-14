# Текущие задачи (Очистка репозитория от мусора - интеграции)
- [x] Список файлов и папок в Backend/litellm/integrations/, которые относятся к Langfuse, Datadog и Sentry и могут быть неиспользуемыми (не удалять):
  - Backend/litellm/integrations/callback_configs.json (содержит конфигурации datadog, datadog_metrics, datadog_cost_management, langfuse, langfuse_otel)
  - Backend/litellm/integrations/litellm_agent/litellm_agent_model_resolver.py (содержит упоминание langfuse в комментариях/документации)
  - Backend/litellm/integrations/generic_api/generic_api_callback.py (содержит комментарий-ссылку на langfuse.py)
  - Backend/litellm/integrations/opentelemetry/ (папка, потенциально неиспользуемая)
  - Backend/litellm/integrations/prometheus_helpers/ (папка, потенциально неиспользуемая)
- [x] Удалить файлы интеграций из Backend/litellm/types/integrations/ (langfuse.py, langfuse_otel.py, datadog.py, datadog_cost_management.py, datadog_llm_obs.py, datadog_metrics.py, slack_alerting.py и т.д.)

# Текущие задачи (Очистка репозитория от мусора - интеграции)
- [ ] Список файлов и папок в Backend/litellm/integrations/, которые относятся к Langfuse, Datadog и Sentry и могут быть неиспользуемыми (не удалять):
  - Backend/litellm/integrations/callback_configs.json (содержит конфигурации datadog, datadog_metrics, datadog_cost_management, langfuse, langfuse_otel)
  - Backend/litellm/integrations/litellm_agent/litellm_agent_model_resolver.py (содержит упоминание langfuse в комментариях/документации)
  - Backend/litellm/integrations/generic_api/generic_api_callback.py (содержит комментарий-ссылку на langfuse.py)
  - Backend/litellm/integrations/opentelemetry/ (папка, потенциально неиспользуемая)
  - Backend/litellm/integrations/prometheus_helpers/ (папка, потенциально неиспользуемая)

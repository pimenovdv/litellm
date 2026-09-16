# Текущие задачи (Удаление неиспользуемых интеграций)
- [x] Delete `langfuse.py`, `langfuse_otel.py`, `datadog.py`, `datadog_llm_obs.py`, `datadog_metrics.py`, `datadog_cost_management.py`, `slack_alerting.py` from `Backend/litellm/types/integrations/`.
- [x] Remove references in `Backend/litellm/router.py`, `Backend/litellm/proxy/proxy_server.py`, `Backend/litellm/__init__.py`, and `Backend/litellm/_lazy_imports_registry.py`.
- [x] Refactor `Backend/enterprise/litellm_enterprise/enterprise_callbacks/pagerduty/pagerduty.py` to remove inheritance from `SlackAlerting`.
- [x] Remove mentions from `Backend/litellm/integrations/custom_guardrail.py` and `Backend/litellm/integrations/mock_client_factory.py`.

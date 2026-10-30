# Maintenance Tasks

## Performance Optimization
- [x] Optimize import times in `Backend/litellm/__init__.py` and `Backend/litellm/utils.py` by deferring lazy imports.
- [x] Reduce redundant Prisma queries in proxy authentication middleware `Backend/litellm/proxy/auth/`.

## Refactoring & Typing
- [x] Add rigorous generic type definitions in `Backend/litellm/types/` for all Pydantic models. (проверен/чист)
- [x] Refactor redundant logic in `Backend/litellm/router.py` handling fallback execution loops. (проверен/чист)
- [x] Standardize logging formatting across `Backend/litellm/_logging.py` and `Backend/litellm/_service_logger.py`.
- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/openai.py`.

## Dead Code & Dependencies Cleanup
- [x] Clean up redundant helper scripts from `Backend/litellm/scripts/` if they are fully superseded by CLI. (directory does not exist, zero files to remove)
- [x] Remove unused mock test fixtures in `tests/` that are not referenced in the refactored test suite.

## Additional Maintenance
- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/anthropic.py`.
- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/bedrock.py`.
- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/vertex_ai.py`.
- [x] Replace `dict` with `Dict[str, Any]` in `Backend/litellm/types/llms/cohere.py` to improve type safety.
- [x] Remove unused typing imports across `Backend/litellm/types/llms/` after refactoring.

- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/databricks.py`.
- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/mistral.py`.
- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/gemini.py`.
- [x] Remove unused mock test fixtures in `tests/local_testing/` that are not referenced in the refactored test suite. (zero unused mock fixtures to remove)

- [x] Replace `dict` and `list` with `Dict[str, Any]` and `List` in `Backend/litellm/types/llms/oci.py`, `Backend/litellm/types/llms/ollama.py`, and `Backend/litellm/types/llms/vertex_ai_speech_to_text.py` to improve type safety.
- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/openai_evals.py` to improve type safety. (already typed correctly)

- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/proxy/utils.py` to improve type safety.

- [x] Replace `dict` and `list` with `Dict[str, Any]` and `List[Any]` in `Backend/litellm/caching/caching.py` to improve type safety.

- [x] Replace `dict` and `list` with `Dict[str, Any]` and `List[Any]` in `Backend/litellm/caching/caching_handler.py`, `Backend/litellm/caching/base_cache.py`, `Backend/litellm/caching/_embedding_router.py`, `Backend/litellm/caching/valkey_semantic_cache.py`, and `Backend/litellm/caching/qdrant_semantic_cache.py` to improve type safety.

- [x] Replace `dict` and `list` with `Dict[str, Any]` and `List[Any]` in `Backend/litellm/caching/redis_cache.py` and `Backend/litellm/caching/redis_semantic_cache.py` to improve type safety. (redis_semantic_cache.py already typed correctly with modern annotations)
- [x] Replace `dict` and `list` with `Dict[str, Any]` and `List[Any]` in `Backend/litellm/caching/in_memory_cache.py` and `Backend/litellm/caching/disk_cache.py` to improve type safety.
- [x] Replace `dict` and `list` with `Dict[str, Any]` and `List[Any]` in `Backend/litellm/caching/gcs_cache.py`, `Backend/litellm/caching/s3_cache.py`, and `Backend/litellm/caching/azure_blob_cache.py` to improve type safety.
- [x] Replace `dict` with `Dict[str, Any]` in `Backend/litellm/utils.py` to improve type safety.
- [x] Remove unused variables and imports in `Backend/litellm/proxy/auth/` using autoflake.

- [x] Remove unused variables and imports in `Backend/litellm/proxy/management_endpoints/` using autoflake.
- [x] Fix unused globals and indentation errors in `Backend/litellm/proxy/common_utils/` and `Backend/litellm/proxy/guardrails/`.
- [x] Remove unused variables and imports in `Backend/litellm/proxy/hooks/` using autoflake.

- [x] Fix unused variables and imports in `Backend/litellm/proxy/pass_through_endpoints/` using pyflakes. (проверен/чист)
- [x] Fix unused variables and imports in `Backend/litellm/proxy/ui_crud_endpoints/` using pyflakes. (проверен/чист)

- [x] Fix unused variables and imports in `Backend/litellm/proxy/agent_endpoints/` and `Backend/litellm/proxy/management_helpers/` using pyflakes. (проверен/чист)
- [x] Fix unused variables and imports in `Backend/litellm/proxy/proxy_server.py` using pyflakes.
- [x] Fix unused variables and imports in `Backend/litellm/proxy/utils.py` using pyflakes.
- [x] Fix syntax errors and unused variables in `Backend/litellm/llms/custom_httpx/llm_http_handler.py`.

- [x] Fix unused variables and imports in `Backend/litellm/router_strategy/` using pyflakes. (проверен/чист - re-exported import in config.py kept)
- [x] Fix unused variables and imports in `Backend/litellm/realtime_api/` using pyflakes.
 (проверен/чист)
- [x] Fix unused variables and imports in `Backend/litellm/caching/` using pyflakes.
 (проверен/чист)
- [x] Fix unused variables and imports in `Backend/litellm/` using pyflakes.
 (проверен/чист)
- [x] Fix unused variables and imports in `Backend/litellm/utils.py` using pyflakes.
 (проверен/чист)
- [x] Fix unused variables and imports in `Backend/litellm/llms/` using pyflakes.

- [x] Fix unused variables and imports in `Backend/litellm/router.py` using pyflakes. (проверен/чист)
- [x] Fix unused variables and imports in `Backend/litellm/main.py` using autoflake and pyflakes.
- [x] Restore missing imports for undefined functions in `Backend/litellm/cost_calculator.py`. (проверен/чист)
- [x] Fix unexpected indents in Backend/litellm/anthropic_interface/messages/__init__.py and Backend/litellm/proxy/anthropic_endpoints/endpoints.py. (проверен/чист)
- [x] Fix unused variables and imports in `Backend/litellm/litellm_core_utils/` using pyflakes. (проверен/чист)

- [x] Fix unused variables and imports in `Backend/litellm/_service_logger.py` using pyflakes.
- [x] Fix incorrect generic types (List[Any][Any] -> List[Any] and Dict[str, Any][str, Any] -> Dict[str, Any]) and missing typing imports in `Backend/litellm/types/caching.py` and `Backend/litellm/types/embedding.py`.
- [x] Fix unused variables and imports in `Backend/litellm/interactions/` using pyflakes.
- [x] Fix untyped list and dict collections in Backend/litellm/types/ (lar1.py, object_permission.py, integrations/prometheus.py, guardrails.py) by replacing them with typing.List and typing.Dict.
- [x] Fix unused variables and imports in `Backend/litellm/types/utils.py`, `Backend/litellm/types/llms/openai.py`, and `Backend/litellm/types/responses/main.py` using pyflakes.
- [x] Fix unused variables and imports in `Backend/litellm/types/proxy/` using pyflakes.
- [x] Fix unused variables and imports in `Backend/litellm/types/` (excluding `proxy`) using pyflakes.
- [x] Fix unused variables and imports in Backend/litellm/responses/ using pyflakes.
- [x] Fix unused variables and star imports in proxy auth and assistant files.
- [x] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/completion.py` and `Backend/litellm/types/search.py` to improve type safety.
- [x] Clean up unused variables and imports in Backend/litellm/caching/ using pyflakes and autoflake.
- [x] Clean up unused variables and imports in Backend/litellm/integrations/ using pyflakes.
- [x] Remove unused variables and imports in `Backend/enterprise/litellm_enterprise/proxy/` using pyflakes.
- [x] Remove unused variables and imports in Backend/enterprise/enterprise_hooks/ and Backend/enterprise/litellm_enterprise/ using pyflakes.
- [x] Fix unused variables and star imports in `Backend/litellm/proxy/auth/` and `Backend/litellm/proxy/google_endpoints/` using pyflakes.
- [x] Fix unused variables and imports in `Backend/litellm/types/utils.py` using pyflakes. (проверен/чист - intentionally re-exported for backwards compat)
- [x] Fix unused globals and imports in `Backend/litellm/proxy/proxy_server.py` using pyflakes.
- [x] Clean up unused variables and imports in `Backend/litellm/litellm_core_utils/get_model_cost_map.py` using pyflakes.
- [x] Fix unused variables and imports in `Backend/litellm/proxy/management_endpoints/` using autoflake. (проверен/чист)
- [x] Fix unused variables and imports in Backend/litellm/proxy/management_endpoints/ using pyflakes. (проверен/чист)
- [x] Fix unused variables and imports in `Backend/litellm/_service_logger.py` using pyflakes. (проверен/чист)
- [x] Remove unused variables and imports in Backend/litellm/llms/custom_httpx/http_handler.py using pyflakes. (проверен/чист)
- [x] Fix unused variables and imports in Backend/litellm/__init__.py and Backend/litellm/utils.py using pyflakes. (проверен/чист - intentionally re-exported for backwards compat)
- [x] Fix unused variables and imports in Backend/litellm/a2a_protocol/main.py using pyflakes. (проверен/чист)
- [x] Remove unused variables in Backend/litellm/proxy/auth/auth_checks.py
- [x] Fix redefined unused import RedisPipelineIncrementOperation in Backend/litellm/proxy/hooks/parallel_request_limiter_v3.py
- [x] Fix unused variables and imports in `Backend/litellm/proxy/spend_tracking/spend_management_endpoints.py` using pyflakes. (проверен/чист)
- [x] Remove unused typing imports across `Backend/litellm/types/utils.py`. (проверен/чист - intentionally re-exported)
- [x] Fix redefined unused imports in Backend/litellm/completion_extras/litellm_responses_transformation/transformation.py (проверен/чист)

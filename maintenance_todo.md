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

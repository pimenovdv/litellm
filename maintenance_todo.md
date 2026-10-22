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
- [ ] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/bedrock.py`.
- [ ] Add explicit `typing.Dict` and `typing.List` generic types to replace untyped collections in `Backend/litellm/types/llms/vertex_ai.py`.
- [ ] Replace `dict` with `Dict[str, Any]` in `Backend/litellm/types/llms/cohere.py` to improve type safety.
- [ ] Remove unused typing imports across `Backend/litellm/types/llms/` after refactoring.

import asyncio
import copy
import enum
import importlib
import inspect
import io
import os
import random
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import warnings
from collections.abc import AsyncGenerator, Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    TypedDict,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

import anyio
import websockets
import websockets.exceptions
from pydantic import BaseModel, Json, JsonValue
from typing_extensions import NotRequired, assert_never

from litellm._uuid import uuid
from litellm.constants import (
    AIOHTTP_CONNECTOR_LIMIT,
    AIOHTTP_CONNECTOR_LIMIT_PER_HOST,
    AIOHTTP_KEEPALIVE_TIMEOUT,
    AIOHTTP_NEEDS_CLEANUP_CLOSED,
    AIOHTTP_TTL_DNS_CACHE,
    AUDIO_SPEECH_CHUNK_SIZE,
    BASE_MCP_ROUTE,
    DAILY_TAG_SPEND_BATCH_MULTIPLIER,
    DEFAULT_MAX_RECURSE_DEPTH,
    DEFAULT_SHARED_HEALTH_CHECK_LOCK_TTL,
    DEFAULT_SHARED_HEALTH_CHECK_TTL,
    DEFAULT_SLACK_ALERTING_THRESHOLD,
    LITELLM_EMBEDDING_PROVIDERS_SUPPORTING_INPUT_ARRAY_OF_TOKENS,
    LITELLM_SETTINGS_SAFE_DB_OVERRIDES,
    LITELLM_UI_ALLOW_HEADERS,
    LITELLM_UI_SESSION_DURATION,
)
from litellm.litellm_core_utils.litellm_logging import (
    _init_custom_logger_compatible_class,
)
from litellm.litellm_core_utils.safe_json_dumps import safe_dumps
from litellm.litellm_core_utils.safe_json_loads import safe_json_loads
from litellm.proxy._types import (
    UI_TEAM_ID,
    CallbackDelete,
    CallInfo,
    CommonProxyErrors,
    ConfigFieldDelete,
    ConfigFieldInfo,
    ConfigFieldUpdate,
    ConfigGeneralSettings,
    ConfigList,
    ConfigYAML,
    CoordinationRedisParams,
    EnterpriseLicenseData,
    FieldDetail,
    InvitationClaim,
    InvitationDelete,
    InvitationModel,
    InvitationNew,
    InvitationUpdate,
    LiteLLM_EndUserTable,
    Litellm_EntityType,
    LiteLLM_JWTAuth,
    LiteLLM_TagTable,
    LiteLLM_TeamTable,
    LiteLLM_TeamTableCachedObj,
    LiteLLM_UserTable,
    LitellmUserRoles,
    PassThroughGenericEndpoint,
    ProxyErrorTypes,
    ProxyException,
    RoleBasedPermissions,
    SpecialModelNames,
    SupportedDBObjectType,
    TeamDefaultSettings,
    TokenCountRequest,
    TransformRequestBody,
    UserAPIKeyAuth,
)
from litellm.proxy.common_utils.cache_pydantic_utils import CacheCodec
from litellm.proxy.common_utils.callback_utils import (
    is_sensitive_callback_key,
    normalize_callback_names,
    process_callback,
)
from litellm.proxy.common_utils.realtime_utils import _realtime_request_body
from litellm.router_utils.add_retry_fallback_headers import (
    get_fallback_errors_from_headers,
    get_hidden_params_dict,
)
from litellm.types.utils import (
    ModelResponse,
    ModelResponseStream,
    TextCompletionResponse,
    TokenCountResponse,
)
from litellm.utils import (
    _invalidate_model_cost_lowercase_map,
    load_credentials_from_list,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from opentelemetry.trace import Span as _Span

    OpenTelemetry = Any

    Span = Union[_Span, Any]
else:
    Span = Any
    OpenTelemetry = Any

REALTIME_REQUEST_SCOPE_TEMPLATE: dict[str, Any] = {
    "type": "http",
    "method": "POST",
    "path": "/v1/realtime",
}


def showwarning(message, category, filename, lineno, file=None, line=None):
    traceback_info = f"{filename}:{lineno}: {category.__name__}: {message}\n"
    if file is not None:
        file.write(traceback_info)


warnings.showwarning = showwarning
warnings.filterwarnings("default", category=UserWarning)

# Your client code here


messages: list = []
sys.path.insert(0, os.path.abspath("../.."))  # Adds the parent directory to the system path - for litellm local dev

build_billing_metrics_recorder = None
shutdown_billing_metrics_recorder = None
from litellm.proxy.middleware.in_flight_requests_middleware import (
    InFlightRequestsMiddleware,
)
from litellm.proxy.middleware.prometheus_auth_middleware import PrometheusAuthMiddleware
from litellm.proxy.middleware.request_size_limit_middleware import (
    RequestSizeLimitMiddleware,
)
from litellm.proxy.middleware.security_headers_middleware import (
    SecurityHeadersMiddleware,
)
from litellm.proxy.ocr_endpoints.endpoints import router as ocr_router
from litellm.proxy.openai_files_endpoints.files_endpoints import (
    router as openai_files_router,
)
from litellm.proxy.openai_files_endpoints.files_endpoints import (
    set_files_config,
)
from litellm.proxy.pass_through_endpoints.llm_passthrough_endpoints import (
    router as llm_passthrough_router,
)
from litellm.proxy.pass_through_endpoints.llm_passthrough_endpoints import (
    vertex_ai_live_websocket_passthrough,
)
from litellm.proxy.pass_through_endpoints.pass_through_endpoints import (
    initialize_pass_through_endpoints,
)
from litellm.proxy.pass_through_endpoints.pass_through_endpoints import (
    router as pass_through_router,
)
from litellm.proxy.public_endpoints import router as public_endpoints_router
from litellm.proxy.rerank_endpoints.endpoints import router as rerank_router
from litellm.proxy.response_api_endpoints.endpoints import router as response_router
from litellm.proxy.route_llm_request import route_request
from litellm.proxy.search_endpoints.endpoints import router as search_router
from litellm.proxy.shutdown.graceful_shutdown_manager import GracefulShutdownManager
from litellm.proxy.spend_tracking.budget_reservation import get_budget_window_start
from litellm.proxy.spend_tracking.spend_management_endpoints import (
    router as spend_management_router,
)
from litellm.proxy.spend_tracking.spend_tracking_utils import get_logging_payload
from litellm.proxy.types_utils.utils import get_instance_fn
from litellm.proxy.ui_crud_endpoints.proxy_setting_endpoints import (
    router as ui_crud_endpoints_router,
)
from litellm.proxy.utils import (
    PrismaClient,
    ProxyLogging,
    ProxyUpdateSpend,
    _cache_user_row,
    _get_docs_url,
    _get_openapi_url,
    _get_projected_spend_over_limit,
    _get_redoc_url,
    _is_projected_spend_over_limit,
    _is_valid_team_configs,
    get_config_param,
    get_custom_url,
    get_error_message_str,
    get_server_root_path,
    handle_exception_on_proxy,
    hash_password,
    hash_token,
    invalidate_config_param,
    litellm_config_cache,
    migrate_passwords_to_scrypt_async,
    model_dump_with_preserved_fields,
    prefetch_config_params,
    update_spend,
)
from litellm.proxy.video_endpoints.endpoints import router as video_router
from litellm.repositories.credentials_repository import CredentialsRepository
from litellm.router import (
    AssistantsTypedDict,
    Deployment,
    LiteLLM_Params,
    ModelGroupInfo,
)
from litellm.scheduler import FlowItem, Scheduler
from litellm.secret_managers.main import (
    get_secret,
    get_secret_bool,
    get_secret_str,
    normalize_nonempty_secret_str,
    str_to_bool,
)
from litellm.types.integrations.slack_alerting import SlackAlertingArgs
from litellm.types.llms.anthropic import (
    AnthropicMessagesRequest,
    AnthropicResponse,
    AnthropicResponseContentBlockText,
    AnthropicResponseUsageBlock,
)
from litellm.types.llms.openai import HttpxBinaryResponseContent
from litellm.types.proxy.control_plane_endpoints import WorkerRegistryEntry
from litellm.types.proxy.management_endpoints.model_management_endpoints import (
    ModelGroupInfoProxy,
)
from litellm.types.proxy.management_endpoints.ui_sso import (
    DefaultTeamSSOParams,
    LiteLLM_UpperboundKeyGenerateParams,
)
from litellm.types.realtime import RealtimeQueryParams
from litellm.types.router import (
    DeploymentTypedDict,
    RouterGeneralSettings,
    RoutingPlugin,
    SearchToolTypedDict,
    updateDeployment,
)
from litellm.types.router import ModelInfo as RouterModelInfo
from litellm.types.scheduler import DefaultPriorities
from litellm.types.secret_managers.main import (
    KeyManagementSettings,
    KeyManagementSystem,
)
from litellm.types.utils import CredentialItem, CustomHuggingfaceTokenizer, RawRequestTypedDict, StandardLoggingPayload
from litellm.types.utils import ModelInfo as ModelMapInfo
from litellm.utils import _add_custom_logger_callback_to_specific_event

enterprise_proxy_config = None
###################

server_root_path = get_server_root_path()
_license_check = LicenseCheck()
premium_user: bool = _license_check.is_premium()
premium_user_data: Optional["EnterpriseLicenseData"] = _license_check.airgapped_license_data
global_max_parallel_request_retries_env: str | None = os.getenv("LITELLM_GLOBAL_MAX_PARALLEL_REQUEST_RETRIES")
proxy_state = ProxyState()
SENSITIVE_DATA_MASKER = SensitiveDataMasker()


# Secret-bearing general_settings fields the segment masker does not match by
# name: database_url and database_extra_connection_params embed DB credentials,
# pass_through_endpoints carry upstream Authorization headers, and
# alert_to_webhook_url is itself a webhook secret
_EXTRA_SECRET_GENERAL_SETTINGS_FIELDS = frozenset(
    {
        "database_url",
        "database_extra_connection_params",
        "pass_through_endpoints",
        "alert_to_webhook_url",
    }
)


def _redact_worker_config_for_logging(worker_config: str | dict[str, JsonValue] | None) -> JsonValue:
    """Mask sensitive fields in the worker config before it enters a log record.

    `worker_config` reaches `proxy_startup_event` as either the JSON blob
    persisted by `save_worker_config` (a string) or the dict passed directly
    to `initialize`. Both shapes can carry `master_key`, `database_url`,
    provider API keys, etc.; passing the raw value to `verbose_proxy_logger`
    leaks them whenever the last-line-of-defense regex filter is bypassed
    (`LITELLM_DISABLE_REDACT_SECRETS=true`, an older log sink, a downstream
    handler that captures records pre-filter). Redact at the source.
    """
    if worker_config is None:
        return None
    if isinstance(worker_config, dict):
        return _redact_secret_values_in_obj(worker_config)
    parsed = safe_json_loads(worker_config, default=None)
    if isinstance(parsed, dict):
        return safe_dumps(_redact_secret_values_in_obj(parsed))
    return worker_config


if global_max_parallel_request_retries_env is None:
    global_max_parallel_request_retries: int = 3
else:
    global_max_parallel_request_retries = int(global_max_parallel_request_retries_env)

global_max_parallel_request_retry_timeout_env: str | None = os.getenv(
    "LITELLM_GLOBAL_MAX_PARALLEL_REQUEST_RETRY_TIMEOUT"
)
if global_max_parallel_request_retry_timeout_env is None:
    global_max_parallel_request_retry_timeout: float = 60.0
else:
    global_max_parallel_request_retry_timeout = float(global_max_parallel_request_retry_timeout_env)

ui_link = f"{server_root_path}/ui"
fallback_login_link = f"{server_root_path}/fallback/login"
model_hub_link = f"{server_root_path}/ui/model_hub_table"
ui_message = f"👉 [```LiteLLM Admin Panel on /ui```]({ui_link}). Create, Edit Keys with SSO. Having issues? Try [```Fallback Login```]({fallback_login_link})"
ui_message += "\n\n💸 [```LiteLLM Model Cost Map```](https://models.litellm.ai/)."

ui_message += f"\n\n🔎 [```LiteLLM Model Hub```]({model_hub_link}). See available models on the proxy. [**Docs**](https://docs.litellm.ai/docs/proxy/ai_hub)"

custom_swagger_message = (
    "[**Customize Swagger Docs**](https://docs.litellm.ai/docs/proxy/enterprise#swagger-docs---custom-routes--branding)"
)

### CUSTOM BRANDING [ENTERPRISE FEATURE] ###
_title = os.getenv("DOCS_TITLE", "LiteLLM API") if premium_user else "LiteLLM API"
_description = (
    os.getenv(
        "DOCS_DESCRIPTION",
        f"Enterprise Edition \n\nProxy Server to call 100+ LLMs in the OpenAI format. {custom_swagger_message}\n\n{ui_message}",
    )
    if premium_user
    else f"Proxy Server to call 100+ LLMs in the OpenAI format. {custom_swagger_message}\n\n{ui_message}"
)


def cleanup_router_config_variables():
    global \
        master_key, \
        user_config_file_path, \
        otel_logging, \
        user_custom_auth, \
        user_custom_auth_path, \
        user_custom_key_generate, \
        user_custom_key_update, \
        user_custom_sso, \
        user_custom_ui_sso_sign_in_handler, \
        use_background_health_checks, \
        use_shared_health_check, \
        health_check_interval, \
        health_check_concurrency, \
        prisma_client

    # Set all variables to None
    master_key = None
    user_config_file_path = None
    otel_logging = None
    user_custom_auth = None
    user_custom_auth_path = None
    user_custom_key_generate = None
    user_custom_key_update = None
    user_custom_sso = None
    user_custom_ui_sso_sign_in_handler = None
    use_background_health_checks = None
    use_shared_health_check = None
    health_check_interval = None
    health_check_concurrency = None
    prisma_client = None


async def proxy_shutdown_event():
    global prisma_client, master_key, user_custom_auth, user_custom_key_generate, user_custom_key_update
    verbose_proxy_logger.info("Shutting down LiteLLM Proxy Server")
    if prisma_client:
        verbose_proxy_logger.debug("Disconnecting from Prisma")
        await prisma_client.disconnect()

    if litellm.cache is not None:
        await litellm.cache.disconnect()

    await jwt_handler.close()

    if db_writer_client is not None:
        await db_writer_client.close()  # type: ignore[reportGeneralTypeIssues]

    # final flush of billable-request counts: without it, up to one export
    # interval of enterprise billing data is dropped on every restart
    if shutdown_billing_metrics_recorder is not None:
        shutdown_billing_metrics_recorder()

    # flush remaining langfuse logs
    if "langfuse" in litellm.success_callback:
            verbose_proxy_logger.warning(
                "LiteLLM: LITELLM_ENABLE_PYROSCOPE is set but the 'pyroscope-io' package is not installed. "
                "Pyroscope profiling will not run. Install with: pip install pyroscope-io"
            )


#### API ENDPOINTS ####
@router.get("/v1/models", dependencies=[Depends(user_api_key_auth)], tags=["model management"])
@router.get(
    "/models", dependencies=[Depends(user_api_key_auth)], tags=["model management"]
)  # if project requires model list
async def model_list(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    return_wildcard_routes: bool | None = False,
    team_id: str | None = None,
    include_model_access_groups: bool | None = False,
    only_model_access_groups: bool | None = False,
    include_metadata: bool | None = False,
    fallback_type: str | None = None,
    scope: str | None = None,
    healthy_only: bool | None = False,
):
    """
    Use `/model/info` - to get detailed model information, example - pricing, mode, etc.

    This is just for compatibility with openai projects like aider.

    Query Parameters:
    - include_metadata: Include additional metadata in the response with fallback information
    - fallback_type: Type of fallbacks to include ("general", "context_window", "content_policy")
                    Defaults to "general" when include_metadata=true
    - scope: Optional scope parameter. Currently only accepts "expand".
             When scope=expand is passed, proxy admins, team admins, and org admins
             will receive all proxy models as if they are a proxy admin.
    - healthy_only: When true, hide models whose backing deployments are all marked
                    unhealthy by background health checks. Requires
                    `background_health_checks: true` in general_settings; without
                    health state the listing is returned unfiltered (fail open).
                    Models expanded from wildcard routes (e.g. `openai/*`) are not
                    filtered, and nothing is hidden when `allowed_fails_policy` is
                    configured (cooldown remains the sole exclusion mechanism).
                    Hiding is presentation-only: a hidden model can still be
                    called directly.
    """
    global llm_model_list, general_settings, llm_router, prisma_client, user_api_key_cache, proxy_logging_obj

    settings = cast(dict[str, object], general_settings)  # any-ok: legacy settings

    from litellm.proxy.management_endpoints.common_utils import (
        _user_has_admin_privileges,
    )
    from litellm.proxy.utils import (
        create_model_info_response,
        get_available_models_for_user,
    )

    # Validate scope parameter if provided
    if scope is not None and scope != "expand":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scope parameter. Only 'expand' is currently supported. Received: {scope}",
        )

    # Check if scope=expand is requested and user has admin privileges
    should_expand_scope = False
    if scope == "expand":
        should_expand_scope = await _user_has_admin_privileges(
            user_api_key_dict=user_api_key_dict,
            prisma_client=prisma_client,
            user_api_key_cache=user_api_key_cache,
            proxy_logging_obj=proxy_logging_obj,
        )

    # Compute once — used in both branches below to hide paused models from the listing.
    blocked_names = llm_router.get_fully_blocked_model_names() if llm_router is not None else set()

    # Opt-in: also hide models whose deployments are all unhealthy per background
    # health checks. Empty when health state is unavailable or stale (fail open).
    unhealthy_names: set[str] = set()
    if healthy_only and llm_router is not None:
        unhealthy_names = await llm_router.async_get_fully_unhealthy_model_names()
        if not unhealthy_names:
            verbose_proxy_logger.debug(
                "healthy_only=true but no unhealthy deployment state is available "
                "(requires background_health_checks); returning unfiltered model list"
            )

    hidden_names = blocked_names | unhealthy_names

    # If scope=expand and user has admin privileges, return all proxy models
    if should_expand_scope:
        # Get all proxy models as if user is a proxy admin
        if llm_router is None:
            proxy_model_list = []
            model_access_groups = {}
        else:
            proxy_model_list = llm_router.get_model_names()
            model_access_groups = llm_router.get_model_access_groups()

        # Include model access groups if requested
        if include_model_access_groups:
            proxy_model_list = list(set(proxy_model_list + list(model_access_groups.keys())))

        # Get complete model list including wildcard routes if requested
        from litellm.proxy.auth.model_checks import get_complete_model_list

        all_models = get_complete_model_list(
            key_models=[],
            team_models=[],
            proxy_model_list=proxy_model_list,
            user_model=None,
            infer_model_from_keys=False,
            return_wildcard_routes=return_wildcard_routes or False,
            llm_router=llm_router,
            model_access_groups=model_access_groups,
            include_model_access_groups=include_model_access_groups or False,
            only_model_access_groups=only_model_access_groups or False,
        )

        # Hide paused/unhealthy models from the public listing
        if hidden_names:
            all_models = [m for m in all_models if m not in hidden_names]

        # Surface the public team name by default; legacy internal keys via flag.
        # The internal routing key drives the metadata/fallback lookup, while the
        # public name is what the client sees as the model id.
        model_data = []
        for response_id, lookup_id in TeamModelNameTranslator.listing_entries(all_models, llm_router, settings):
            model_info = create_model_info_response(
                model_id=lookup_id,
                provider="openai",
                include_metadata=include_metadata or False,
                fallback_type=fallback_type,
                llm_router=llm_router,
            )
            model_info["id"] = response_id
            model_data.append(model_info)

        return dict(
            data=model_data,
            object="list",
        )

    # Otherwise, use the normal behavior (current implementation)
    # Get available models for the user
    all_models = await get_available_models_for_user(
        user_api_key_dict=user_api_key_dict,
        llm_router=llm_router,
        general_settings=general_settings,
        user_model=user_model,
        prisma_client=prisma_client,
        proxy_logging_obj=proxy_logging_obj,
        team_id=team_id,
        include_model_access_groups=include_model_access_groups or False,
        only_model_access_groups=only_model_access_groups or False,
        return_wildcard_routes=return_wildcard_routes or False,
        user_api_key_cache=user_api_key_cache,
    )

    # Hide paused/unhealthy models from the public listing
    if hidden_names:
        all_models = [m for m in all_models if m not in hidden_names]

    # Surface the public team name by default; legacy internal keys via flag.
    # The internal routing key drives the metadata/fallback lookup, while the
    # public name is what the client sees as the model id.
    model_data = []
    for response_id, lookup_id in TeamModelNameTranslator.listing_entries(all_models, llm_router, settings):
        model_info = create_model_info_response(
            model_id=lookup_id,
            provider="openai",
            include_metadata=include_metadata or False,
            fallback_type=fallback_type,
            llm_router=llm_router,
        )
        model_info["id"] = response_id
        model_data.append(model_info)

    return dict(
        data=model_data,
        object="list",
    )


@router.get(
    "/v1/models/{model_id}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["model management"],
)
@router.get(
    "/models/{model_id}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["model management"],
)
async def model_info(
    model_id: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    team_id: str | None = None,
    healthy_only: bool | None = False,
):
    """
    Retrieve information about a specific model accessible to your API key.

    Returns model details only if the model is available to your API key/team.
    Returns 404 if the model doesn't exist or is not accessible.

    Follows OpenAI API specification for individual model retrieval.
    https://platform.openai.com/docs/api-reference/models/retrieve

    Query parameters mirror `/v1/models` so the same caller context (team
    scoping, health filtering, paused deployments) drives both endpoints; the
    listing's public id must resolve to the same internal deployment here.
    """
    global llm_model_list, general_settings, llm_router, prisma_client, user_api_key_cache, proxy_logging_obj

    settings = cast(dict[str, object], general_settings)  # any-ok: legacy settings

    from litellm.proxy.utils import (
        create_model_info_response,
        get_available_models_for_user,
        validate_model_access,
    )

    all_models = await get_available_models_for_user(
        user_api_key_dict=user_api_key_dict,
        llm_router=llm_router,
        general_settings=general_settings,
        user_model=user_model,
        prisma_client=prisma_client,
        proxy_logging_obj=proxy_logging_obj,
        team_id=team_id,
        include_model_access_groups=False,
        only_model_access_groups=False,
        return_wildcard_routes=False,
        user_api_key_cache=user_api_key_cache,
    )

    # Mirror /v1/models' visibility filter so first-occurrence resolution
    # cannot land on a deployment the listing had hidden.
    blocked_names = llm_router.get_fully_blocked_model_names() if llm_router is not None else set()
    unhealthy_names: set[str] = set()
    if healthy_only and llm_router is not None:
        unhealthy_names = await llm_router.async_get_fully_unhealthy_model_names()
    hidden_names = blocked_names | unhealthy_names
    if hidden_names:
        all_models = [m for m in all_models if m not in hidden_names]

    internal_to_public = TeamModelNameTranslator.build_internal_to_public_map(llm_router, settings)
    resolved_model_id = TeamModelNameTranslator.resolve_public_name(
        model_id=model_id,
        available_models=all_models,
        llm_router=llm_router,
        general_settings=settings,
    )

    # Validate that the requested model is accessible
    validate_model_access(model_id=resolved_model_id, available_models=all_models)

    # Get provider information from the router deployment
    if llm_router is None:
        raise HTTPException(status_code=500, detail="Router not initialized")

    deployment = llm_router.get_deployment_by_model_group_name(resolved_model_id)
    if deployment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_id}' not found in router configuration",
        )

    # Use the actual litellm model from the deployment to get provider info
    _, provider, _, _ = litellm.get_llm_provider(model=deployment.litellm_params.model)

    response_id = internal_to_public.get(resolved_model_id, model_id)
    return create_model_info_response(
        model_id=response_id,
        provider=provider,
        include_metadata=False,
        fallback_type=None,
        llm_router=llm_router,
    )


def _blocked_response_usage(original_response: Any | None) -> "litellm.Usage":
    """
    Token usage for a synthetic guardrail-blocked response.

    A post-call block replaces the LLM's response with the violation message,
    but the upstream call already consumed tokens -- report that real usage
    (carried on ``ModifyResponseException.original_response``) rather than
    discarding it. Pre-call blocks never invoked the LLM (no original_response),
    so usage is zero.
    """
    usage = getattr(original_response, "usage", None) if original_response is not None else None
    if isinstance(usage, litellm.Usage):
        return usage
    return litellm.Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)


@router.post(
    "/v1/chat/completions",
    dependencies=[Depends(user_api_key_auth)],
    tags=["chat/completions"],
)
@router.post(
    "/chat/completions",
    dependencies=[Depends(user_api_key_auth)],
    tags=["chat/completions"],
)
@router.post(
    "/engines/{model:path}/chat/completions",
    dependencies=[Depends(user_api_key_auth)],
    tags=["chat/completions"],
)
@router.post(
    "/openai/deployments/{model:path}/chat/completions",
    dependencies=[Depends(user_api_key_auth)],
    tags=["chat/completions"],
    responses={200: {"description": "Successful response"}, **ERROR_RESPONSES},
)  # azure compatible endpoint
async def chat_completion(
    request: Request,
    fastapi_response: Response,
    model: str | None = None,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """

    Follows the exact same API spec as `OpenAI's Chat API https://platform.openai.com/docs/api-reference/chat`

    ```bash
    curl -X POST http://localhost:4000/v1/chat/completions \

    -H "Content-Type: application/json" \

    -H "Authorization: Bearer sk-1234" \

    -d '{
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "Hello!"
            }
        ]
    }'
    ```

    """
    global general_settings, user_debug, proxy_logging_obj, llm_model_list
    global user_temperature, user_request_timeout, user_max_tokens, user_api_base
    data = await _read_request_body(request=request)
    if user_api_key_dict is not None:
        if not isinstance(data.get("metadata"), dict):
            # Covers both missing and JSON-string metadata (multipart /
            # extra_body); otherwise `data["metadata"][k] = v` below raises
            # TypeError on a string value and 500s the request.
            data["metadata"] = {}
        if hasattr(user_api_key_dict, "user_id") and user_api_key_dict.user_id is not None:
            data["metadata"]["user_api_key_user_id"] = user_api_key_dict.user_id
        if hasattr(user_api_key_dict, "team_id") and user_api_key_dict.team_id is not None:
            data["metadata"]["user_api_key_team_id"] = user_api_key_dict.team_id
        if hasattr(user_api_key_dict, "org_id") and user_api_key_dict.org_id is not None:
            data["metadata"]["user_api_key_org_id"] = user_api_key_dict.org_id
        if hasattr(user_api_key_dict, "organization_alias") and user_api_key_dict.organization_alias is not None:
            data["metadata"]["user_api_key_org_alias"] = user_api_key_dict.organization_alias
        if hasattr(user_api_key_dict, "agent_id") and user_api_key_dict.agent_id is not None:
            data["metadata"]["agent_id"] = user_api_key_dict.agent_id

    base_llm_response_processor = ProxyBaseLLMRequestProcessing(data=data)
    try:
        result = await base_llm_response_processor.base_process_llm_request(
            request=request,
            fastapi_response=fastapi_response,
            user_api_key_dict=user_api_key_dict,
            route_type="acompletion",
            proxy_logging_obj=proxy_logging_obj,
            llm_router=llm_router,
            general_settings=general_settings,
            proxy_config=proxy_config,
            select_data_generator=select_data_generator,
            model=model,
            user_model=user_model,
            user_temperature=user_temperature,
            user_request_timeout=user_request_timeout,
            user_max_tokens=user_max_tokens,
            user_api_base=user_api_base,
            version=version,
        )
        if isinstance(result, BaseModel):
            return model_dump_with_preserved_fields(result, exclude_unset=True)
        else:
            return result
    except ModifyResponseException as e:
        # Guardrail flagged content in passthrough mode - return 200 with violation message
        _data = e.request_data
        # Capture logging_obj before post_call_failure_hook pops it from _data.
        _logging_obj = _data.get("litellm_logging_obj")
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict,
            original_exception=e,
            request_data=_data,
        )
        _chat_response = litellm.ModelResponse()
        _chat_response.model = e.model  # type: ignore
        _chat_response.choices[0].message.content = e.message  # type: ignore
        _chat_response.choices[0].finish_reason = "content_filter"  # type: ignore
        # Report the blocked LLM response's real usage (set before the stream
        # branch so both paths carry it); zero for pre-call blocks.
        _chat_response.usage = _blocked_response_usage(e.original_response)  # type: ignore

        if data.get("stream", None) is not None and data["stream"] is True:
            _iterator = litellm.utils.ModelResponseIterator(model_response=_chat_response, convert_to_delta=True)
            _streaming_response = litellm.CustomStreamWrapper(
                completion_stream=_iterator,
                model=e.model,
                custom_llm_provider="cached_response",
                logging_obj=_logging_obj,
            )
            selected_data_generator = select_data_generator(
                response=_streaming_response,
                user_api_key_dict=user_api_key_dict,
                request_data=_data,
                request=request,
            )

            return StreamingResponse(
                selected_data_generator,
                media_type="text/event-stream",
                status_code=200,  # Return 200 for passthrough mode
            )
        return _chat_response
    except RejectedRequestError as e:
        _data = e.request_data
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict,
            original_exception=e,
            request_data=_data,
        )
        _chat_response = litellm.ModelResponse()
        _chat_response.choices[0].message.content = e.message  # type: ignore

        if data.get("stream", None) is not None and data["stream"] is True:
            _iterator = litellm.utils.ModelResponseIterator(model_response=_chat_response, convert_to_delta=True)
            _streaming_response = litellm.CustomStreamWrapper(
                completion_stream=_iterator,
                model=data.get("model", ""),
                custom_llm_provider="cached_response",
                logging_obj=_data.get("litellm_logging_obj", None),
            )
            selected_data_generator = select_data_generator(
                response=_streaming_response,
                user_api_key_dict=user_api_key_dict,
                request_data=_data,
                request=request,
            )

            return StreamingResponse(
                selected_data_generator,
                media_type="text/event-stream",
                status_code=(e.status_code if hasattr(e, "status_code") else status.HTTP_400_BAD_REQUEST),
            )
        _usage = litellm.Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        _chat_response.usage = _usage  # type: ignore
        return _chat_response
    except Exception as e:
        raise await base_llm_response_processor._handle_llm_api_exception(
            e=e,
            user_api_key_dict=user_api_key_dict,
            proxy_logging_obj=proxy_logging_obj,
        )


@router.post("/v1/completions", dependencies=[Depends(user_api_key_auth)], tags=["completions"])
@router.post("/completions", dependencies=[Depends(user_api_key_auth)], tags=["completions"])
@router.post(
    "/engines/{model:path}/completions",
    dependencies=[Depends(user_api_key_auth)],
    tags=["completions"],
)
@router.post(
    "/openai/deployments/{model:path}/completions",
    dependencies=[Depends(user_api_key_auth)],
    tags=["completions"],
)
async def completion(
    request: Request,
    fastapi_response: Response,
    model: str | None = None,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Follows the exact same API spec as `OpenAI's Completions API https://platform.openai.com/docs/api-reference/completions`

    ```bash
    curl -X POST http://localhost:4000/v1/completions \

    -H "Content-Type: application/json" \

    -H "Authorization: Bearer sk-1234" \

    -d '{
        "model": "gpt-3.5-turbo-instruct",
        "prompt": "Once upon a time",
        "max_tokens": 50,
        "temperature": 0.7
    }'
    ```
    """
    global user_temperature, user_request_timeout, user_max_tokens, user_api_base
    data = {}
    try:
        data = await _read_request_body(request=request)
        if user_api_key_dict is not None:
            if data.get("metadata") is None:
                data["metadata"] = {}
            if hasattr(user_api_key_dict, "user_id") and user_api_key_dict.user_id is not None:
                data["metadata"]["user_api_key_user_id"] = user_api_key_dict.user_id
            if hasattr(user_api_key_dict, "team_id") and user_api_key_dict.team_id is not None:
                data["metadata"]["user_api_key_team_id"] = user_api_key_dict.team_id
            if hasattr(user_api_key_dict, "org_id") and user_api_key_dict.org_id is not None:
                data["metadata"]["user_api_key_org_id"] = user_api_key_dict.org_id
            if hasattr(user_api_key_dict, "organization_alias") and user_api_key_dict.organization_alias is not None:
                data["metadata"]["user_api_key_org_alias"] = user_api_key_dict.organization_alias
            if hasattr(user_api_key_dict, "agent_id") and user_api_key_dict.agent_id is not None:
                data["metadata"]["agent_id"] = user_api_key_dict.agent_id
        base_llm_response_processor = ProxyBaseLLMRequestProcessing(data=data)
        return await base_llm_response_processor.base_process_llm_request(
            request=request,
            fastapi_response=fastapi_response,
            user_api_key_dict=user_api_key_dict,
            route_type="atext_completion",
            proxy_logging_obj=proxy_logging_obj,
            llm_router=llm_router,
            general_settings=general_settings,
            proxy_config=proxy_config,
            select_data_generator=select_data_generator,
            model=model,
            user_model=user_model,
            user_temperature=user_temperature,
            user_request_timeout=user_request_timeout,
            user_max_tokens=user_max_tokens,
            user_api_base=user_api_base,
            version=version,
        )
    except ModifyResponseException as e:
        # Guardrail flagged content in passthrough mode - return 200 with violation message
        _data = e.request_data
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict,
            original_exception=e,
            request_data=_data,
        )

        if _data.get("stream", None) is not None and _data["stream"] is True:
            _text_response = litellm.ModelResponse()
            # Set text attribute dynamically for text completion format
            _text_response.choices[0].text = e.message
            _text_response.model = e.model  # type: ignore[assignment]
            _usage = _blocked_response_usage(e.original_response)
            # Set usage attribute dynamically (ModelResponse accepts usage in __init__ but it's not in type definition)
            _text_response.usage = _usage
            _iterator = litellm.utils.ModelResponseIterator(model_response=_text_response, convert_to_delta=True)
            _streaming_response = litellm.TextCompletionStreamWrapper(
                completion_stream=_iterator,
                model=e.model,
            )

            selected_data_generator = select_data_generator(
                response=_streaming_response,
                user_api_key_dict=user_api_key_dict,
                request_data=_data,
                request=request,
            )

            return StreamingResponse(
                selected_data_generator,
                media_type="text/event-stream",
                status_code=200,  # Return 200 for passthrough mode
            )
        else:
            _response = litellm.TextCompletionResponse()
            _response.choices[0].text = e.message
            _response.model = e.model  # type: ignore
            _usage = _blocked_response_usage(e.original_response)
            _response.usage = _usage  # type: ignore
            return _response
    except RejectedRequestError as e:
        _data = e.request_data
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict,
            original_exception=e,
            request_data=_data,
        )
        if _data.get("stream", None) is not None and _data["stream"] is True:
            _chat_response = litellm.ModelResponse()
            _usage = litellm.Usage(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            )
            _chat_response.usage = _usage  # type: ignore
            _chat_response.choices[0].message.content = e.message  # type: ignore
            _iterator = litellm.utils.ModelResponseIterator(model_response=_chat_response, convert_to_delta=True)
            _streaming_response = litellm.TextCompletionStreamWrapper(
                completion_stream=_iterator,
                model=_data.get("model", ""),
            )

            selected_data_generator = select_data_generator(
                response=_streaming_response,
                user_api_key_dict=user_api_key_dict,
                request_data=data,
                request=request,
            )

            return StreamingResponse(
                selected_data_generator,
                media_type="text/event-stream",
                headers={},
                status_code=(e.status_code if hasattr(e, "status_code") else status.HTTP_400_BAD_REQUEST),
            )
        else:
            _response = litellm.TextCompletionResponse()
            _response.choices[0].text = e.message
            return _response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.exception(f"litellm.proxy.proxy_server.completion(): Exception occured - {e!s}")
        error_msg = f"{e!s}"
        raise ProxyException(
            message=getattr(e, "message", error_msg),
            type=getattr(e, "type", "None"),
            param=getattr(e, "param", "None"),
            openai_code=getattr(e, "code", None),
            code=getattr(e, "status_code", 500),
        )


@router.post(
    "/v1/embeddings",
    dependencies=[Depends(user_api_key_auth)],
    response_class=ORJSONResponse,
    tags=["embeddings"],
)
@router.post(
    "/embeddings",
    dependencies=[Depends(user_api_key_auth)],
    response_class=ORJSONResponse,
    tags=["embeddings"],
)
@router.post(
    "/engines/{model:path}/embeddings",
    dependencies=[Depends(user_api_key_auth)],
    response_class=ORJSONResponse,
    tags=["embeddings"],
)  # azure compatible endpoint
@router.post(
    "/openai/deployments/{model:path}/embeddings",
    dependencies=[Depends(user_api_key_auth)],
    response_class=ORJSONResponse,
    tags=["embeddings"],
)  # azure compatible endpoint
async def embeddings(
    request: Request,
    fastapi_response: Response,
    model: str | None = None,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Follows the exact same API spec as `OpenAI's Embeddings API https://platform.openai.com/docs/api-reference/embeddings`

    ```bash
    curl -X POST http://localhost:4000/v1/embeddings \

    -H "Content-Type: application/json" \

    -H "Authorization: Bearer sk-1234" \

    -d '{
        "model": "text-embedding-ada-002",
        "input": "The quick brown fox jumps over the lazy dog"
    }'
    ```

"""
    global proxy_logging_obj
    data: Any = {}
    try:
        # Use shared request body reading helper (same as chat/completions)
        data = await _read_request_body(request=request)

        ### HANDLE TOKEN ARRAY INPUT DECODING ###
        # This must happen BEFORE base_process_llm_request() since it modifies the input
        router_model_names = llm_router.model_names if llm_router is not None else []
        if (
            "input" in data
            and isinstance(data["input"], list)
            and len(data["input"]) > 0
            and isinstance(data["input"][0], list)
            and isinstance(data["input"][0][0], int)
        ):  # check if array of tokens passed in
            # check if provider accept list of tokens as input - e.g. for langchain integration
            if llm_router is not None and data.get("model") in router_model_names:
                # Use router's O(1) lookup instead of O(N) iteration through llm_model_list
                deployment = llm_router.get_deployment_by_model_group_name(model_group_name=data["model"])
                if deployment is not None:
                    litellm_params = deployment.get("litellm_params", {}) or {}
                    litellm_model = litellm_params.get("model", "")
                    # Check if this provider supports token arrays
                    supports_token_arrays = litellm_model in litellm.open_ai_embedding_models or any(
                        litellm_model.startswith(provider)
                        for provider in LITELLM_EMBEDDING_PROVIDERS_SUPPORTING_INPUT_ARRAY_OF_TOKENS
                    )
                    if not supports_token_arrays:
                        # non-openai/azure embedding model called with token input - decode tokens
                        input_list = []
                        for i in data["input"]:
                            input_list.append(litellm.decode(model="gpt-3.5-turbo", tokens=i))
                        data["input"] = input_list

        if user_api_key_dict is not None:
            if data.get("metadata") is None:
                data["metadata"] = {}
            if hasattr(user_api_key_dict, "user_id") and user_api_key_dict.user_id is not None:
                data["metadata"]["user_api_key_user_id"] = user_api_key_dict.user_id
            if hasattr(user_api_key_dict, "team_id") and user_api_key_dict.team_id is not None:
                data["metadata"]["user_api_key_team_id"] = user_api_key_dict.team_id
            if hasattr(user_api_key_dict, "org_id") and user_api_key_dict.org_id is not None:
                data["metadata"]["user_api_key_org_id"] = user_api_key_dict.org_id
            if hasattr(user_api_key_dict, "organization_alias") and user_api_key_dict.organization_alias is not None:
                data["metadata"]["user_api_key_org_alias"] = user_api_key_dict.organization_alias
            if hasattr(user_api_key_dict, "agent_id") and user_api_key_dict.agent_id is not None:
                data["metadata"]["agent_id"] = user_api_key_dict.agent_id

        # Use unified request processor (same as chat/completions and responses)
        base_llm_response_processor = ProxyBaseLLMRequestProcessing(data=data)

        # Process the request with all optimizations (shared sessions, network tuning, etc.)
        response = await base_llm_response_processor.base_process_llm_request(
            request=request,
            fastapi_response=fastapi_response,
            user_api_key_dict=user_api_key_dict,
            route_type="aembedding",
            proxy_logging_obj=proxy_logging_obj,
            llm_router=llm_router,
            general_settings=general_settings,
            proxy_config=proxy_config,
            select_data_generator=select_data_generator,
            model=model,
            user_model=user_model,
            user_temperature=user_temperature,
            user_request_timeout=user_request_timeout,
            user_max_tokens=user_max_tokens,
            user_api_base=user_api_base,
            version=version,
        )

        return response
    except Exception as e:
        # Use unified error handler
        base_llm_response_processor = ProxyBaseLLMRequestProcessing(data=data)
        raise await base_llm_response_processor._handle_llm_api_exception(
            e=e,
            user_api_key_dict=user_api_key_dict,
            proxy_logging_obj=proxy_logging_obj,
            version=version,
        )


@router.post(
    "/v1/moderations",
    dependencies=[Depends(user_api_key_auth)],
    response_class=ORJSONResponse,
    tags=["moderations"],
)
@router.post(
    "/moderations",
    dependencies=[Depends(user_api_key_auth)],
    response_class=ORJSONResponse,
    tags=["moderations"],
)
async def moderations(
    request: Request,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    The moderations endpoint is a tool you can use to check whether content complies with an LLM Providers policies.
    Quick Start
    ```
    curl --location 'http://0.0.0.0:4000/moderations' \
    --header 'Content-Type: application/json' \
    --header 'Authorization: Bearer sk-1234' \
    --data '{"input": "Sample text goes here", "model": "text-moderation-stable"}'
    ```
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        # Use orjson to parse JSON data, orjson speeds up requests significantly
        body = await request.body()
        data = orjson.loads(body)

        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        data["model"] = (
            general_settings.get("moderation_model", None)  # server default
            or user_model  # model name passed via cli args
            or data.get("model")  # default passed in http request
        )
        if user_model:
            data["model"] = user_model

        ### CALL HOOKS ### - modify incoming data / reject request before calling the model
        data = await proxy_logging_obj.pre_call_hook(
            user_api_key_dict=user_api_key_dict, data=data, call_type="moderation"
        )

        time.time()

        ## ROUTE TO CORRECT ENDPOINT ##
        llm_call = await route_request(
            data=data,
            route_type="amoderation",
            llm_router=llm_router,
            user_model=user_model,
        )
        response = await llm_call

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                request_data=data,
                hidden_params=hidden_params,
            )
        )

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.exception(
            f"litellm.proxy.proxy_server.moderations(): Exception occured - {e!s}"
        )
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", 500),
            )


async def _audio_speech_chunk_generator(
    _response: HttpxBinaryResponseContent,
) -> AsyncGenerator[bytes, None]:
    # chunk_size has a big impact on latency, it can't be too small or too large
    # too small: latency is high
    # too large: latency is low, but memory usage is high
    # 8192 is a good compromise
    _generator = await _response.aiter_bytes(chunk_size=AUDIO_SPEECH_CHUNK_SIZE)
    async for chunk in _generator:
        yield chunk


@router.post(
    "/v1/audio/speech",
    dependencies=[Depends(user_api_key_auth)],
    tags=["audio"],
)
@router.post(
    "/audio/speech",
    dependencies=[Depends(user_api_key_auth)],
    tags=["audio"],
)
async def audio_speech(
    request: Request,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Same params as:

    https://platform.openai.com/docs/api-reference/audio/createSpeech
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        # Use orjson to parse JSON data, orjson speeds up requests significantly
        body = await request.body()
        data = orjson.loads(body)

        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        if data.get("user", None) is None and user_api_key_dict.user_id is not None:
            data["user"] = user_api_key_dict.user_id

        if user_model:
            data["model"] = user_model

        ### CALL HOOKS ### - modify incoming data / reject request before calling the model
        data = await proxy_logging_obj.pre_call_hook(
            user_api_key_dict=user_api_key_dict, data=data, call_type="aspeech"
        )

        ## ROUTE TO CORRECT ENDPOINT ##
        llm_call = await route_request(
            data=data,
            route_type="aspeech",
            llm_router=llm_router,
            user_model=user_model,
        )
        response = await llm_call

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""
        response_cost = hidden_params.get("response_cost", None) or ""
        litellm_call_id = hidden_params.get("litellm_call_id", None) or ""

        custom_headers = ProxyBaseLLMRequestProcessing.get_custom_headers(
            user_api_key_dict=user_api_key_dict,
            model_id=model_id,
            cache_key=cache_key,
            api_base=api_base,
            version=version,
            response_cost=response_cost,
            model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
            fastest_response_batch_completion=None,
            call_id=litellm_call_id,
            request_data=data,
            hidden_params=hidden_params,
        )

        # Call response headers hook (matches audio_transcription behavior)
        callback_headers = await proxy_logging_obj.post_call_response_headers_hook(
            data=data,
            user_api_key_dict=user_api_key_dict,
            response=response,
            request_headers=dict(request.headers),
        )
        if callback_headers:
            custom_headers.update(callback_headers)

        # Determine media type based on model type
        media_type = "audio/mpeg"  # Default for OpenAI TTS
        request_model = data.get("model", "")
        if request_model:
            request_model_lower = request_model.lower()
            if "gemini" in request_model_lower and (
                "tts" in request_model_lower or "preview-tts" in request_model_lower
            ):
                media_type = "audio/wav"  # Gemini TTS returns WAV format after conversion

        return StreamingResponse(
            _audio_speech_chunk_generator(response),  # type: ignore[arg-type]
            media_type=media_type,
            headers=custom_headers,  # type: ignore
        )

    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict,
            original_exception=e,
            request_data=data,
        )
        verbose_proxy_logger.error(f"litellm.proxy.proxy_server.audio_speech(): Exception occured - {e!s}")
        verbose_proxy_logger.debug(traceback.format_exc())
        raise e


@router.post(
    "/v1/audio/transcriptions",
    dependencies=[Depends(user_api_key_auth)],
    tags=["audio"],
)
@router.post(
    "/audio/transcriptions",
    dependencies=[Depends(user_api_key_auth)],
    tags=["audio"],
)
async def audio_transcriptions(
    request: Request,
    fastapi_response: Response,
    file: UploadFile = File(...),
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Same params as:

    https://platform.openai.com/docs/api-reference/audio/createTranscription?lang=curl
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        # Use orjson to parse JSON data, orjson speeds up requests significantly
        form_data = await get_form_data(request)
        data = {key: value for key, value in form_data.items() if key != "file"}

        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        if data.get("user", None) is None and user_api_key_dict.user_id is not None:
            data["user"] = user_api_key_dict.user_id

        data["model"] = (
            general_settings.get("moderation_model", None)  # server default
            or user_model  # model name passed via cli args
            or data.get("model", None)  # default passed in http request
        )
        if user_model:
            data["model"] = user_model

        router_model_names = llm_router.model_names if llm_router is not None else []

        if file.filename is None:
            raise ProxyException(
                message="File name is None. Please check your file name",
                code=status.HTTP_400_BAD_REQUEST,
                type="bad_request",
                param="file",
            )

        # Check if File can be read in memory before reading
        check_file_size_under_limit(
            request_data=data,
            file=file,
            router_model_names=router_model_names,
        )

        file_content = await file.read()
        file_object = io.BytesIO(file_content)
        file_object.name = file.filename
        data["file"] = file_object

        try:
            ### CALL HOOKS ### - modify incoming data / reject request before calling the model
            data = await proxy_logging_obj.pre_call_hook(
                user_api_key_dict=user_api_key_dict,
                data=data,
                call_type="transcription",
            )

            ## ROUTE TO CORRECT ENDPOINT ##
            llm_call = await route_request(
                data=data,
                route_type="atranscription",
                llm_router=llm_router,
                user_model=user_model,
            )
            response = await llm_call
        except Exception as e:
            raise e
        finally:
            file_object.close()  # close the file read in by io library

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""
        response_cost = hidden_params.get("response_cost", None) or ""
        litellm_call_id = hidden_params.get("litellm_call_id", None) or ""
        additional_headers: dict = hidden_params.get("additional_headers", {}) or {}

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                response_cost=response_cost,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                call_id=litellm_call_id,
                request_data=data,
                hidden_params=hidden_params,
                **additional_headers,
            )
        )

        # Call response headers hook (matches base_process_llm_request behavior)
        callback_headers = await proxy_logging_obj.post_call_response_headers_hook(
            data=data,
            user_api_key_dict=user_api_key_dict,
            response=response,
            request_headers=dict(request.headers),
        )
        if callback_headers:
            fastapi_response.headers.update(callback_headers)

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.exception(
            f"litellm.proxy.proxy_server.audio_transcription(): Exception occured - {e!s}"
        )
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e.detail)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                openai_code=getattr(e, "code", None),
                code=getattr(e, "status_code", 500),
            )


######################################################################

#                 Vertex AI Live API WebSocket Pass-through

######################################################################


@app.websocket("/vertex_ai/live")
async def vertex_ai_live_passthrough_endpoint(
    websocket: WebSocket,
    model: str | None = fastapi.Query(
        None,
        description="Optional model name, used to determine Vertex region for global models.",
    ),
    vertex_project: str | None = fastapi.Query(
        None,
        description="Override the Vertex AI project id used for the upstream connection.",
    ),
    vertex_location: str | None = fastapi.Query(
        None,
        description="Override the Vertex AI region (for example, 'us-central1').",
    ),
    user_api_key_dict=Depends(user_api_key_auth_websocket),
):
    """
    Vertex AI Live API WebSocket Pass-through Endpoint

    This endpoint delegates to the WebSocket function defined in llm_passthrough_endpoints.py
    """
    return await vertex_ai_live_websocket_passthrough(
        websocket=websocket,
        model=model,
        vertex_project=vertex_project,
        vertex_location=vertex_location,
        user_api_key_dict=user_api_key_dict,
    )


######################################################################

#                          /v1/realtime Endpoints

######################################################################


@lru_cache(maxsize=_REALTIME_BODY_CACHE_SIZE)
def _realtime_query_params_template(model: str | None, intent: str | None) -> tuple[tuple[str, str], ...]:
    """
    Build a hashable representation of the realtime query params so we can cache
    the repetitive model/intent combinations.
    """
    params: list[tuple[str, str]] = []
    if model is not None:
        params.append(("model", model))
    if intent is not None:
        params.append(("intent", intent))
    return tuple(params)


@app.websocket("/openai/v1/realtime")
@app.websocket("/v1/realtime")
@app.websocket("/realtime")
async def realtime_websocket_endpoint(
    websocket: WebSocket,
    model: str | None = fastapi.Query(None, description="The model to use for the websocket connection."),
    intent: str | None = fastapi.Query(None, description="The intent of the websocket connection."),
    guardrails: str | None = fastapi.Query(
        None,
        description="Comma-separated list of guardrail names to apply to this request.",
    ),
    user_api_key_dict=Depends(user_api_key_auth_websocket),
):
    requested_protocols = [
        p.strip() for p in (websocket.headers.get("sec-websocket-protocol") or "").split(",") if p.strip()
    ]
    accept_kwargs: dict = {}
    if requested_protocols:
        accept_kwargs["subprotocol"] = requested_protocols[0]

    route_model = model
    if route_model is None:
        if intent == "transcription":
            route_model = "gpt-realtime-whisper"
        else:
            await websocket.close(code=1008, reason="model query parameter is required")
            return
    assert route_model is not None
    try:
        await can_key_call_resolved_model(
            model=route_model,
            llm_model_list=llm_model_list,
            valid_token=user_api_key_dict,
            llm_router=llm_router,
        )
    except ProxyException as e:
        await websocket.close(code=1008, reason=e.message[:120])
        return
    await websocket.accept(**accept_kwargs)

    # Only use explicit parameters, not all query params
    query_params = cast(RealtimeQueryParams, dict(_realtime_query_params_template(model, intent)))

    data: dict[str, Any] = {
        "model": route_model,
        "websocket": websocket,
        "query_params": query_params,  # Only explicit params
    }

    # Pass guardrails into data so pre-call guardrail processing picks them up
    if guardrails:
        data["guardrails"] = [g.strip() for g in guardrails.split(",") if g.strip()]

    # Use raw ASGI headers (already lowercase bytes) to avoid extra work
    headers_list = list(websocket.scope.get("headers") or [])

    scope = REALTIME_REQUEST_SCOPE_TEMPLATE.copy()
    scope["headers"] = headers_list

    request = Request(scope=scope)

    request._url = websocket.url

    async def return_body():
        return _realtime_request_body(route_model)

    request.body = return_body  # type: ignore

    ### ROUTE THE REQUEST ###
    base_llm_response_processor = ProxyBaseLLMRequestProcessing(data=data)

    # Phase 1: pre-call processing (auth, guardrails, rate limits).
    # Errors here (e.g. guardrail block) are sent back to the client as an
    # error event before closing, so the caller knows what happened.
    try:
        (
            data,
            litellm_logging_obj,
        ) = await base_llm_response_processor.common_processing_pre_call_logic(
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_logging_obj=proxy_logging_obj,
            proxy_config=proxy_config,
            user_model=user_model,
            user_temperature=user_temperature,
            user_request_timeout=user_request_timeout,
            user_max_tokens=user_max_tokens,
            user_api_base=user_api_base,
            model=route_model,
            route_type="_arealtime",
        )
    except Exception as e:
        verbose_proxy_logger.exception("Realtime pre-call error")
        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "error": {
                            "type": "guardrail_error",
                            "message": str(e),
                        },
                    }
                )
            )
        except Exception:
            pass
        await websocket.close(code=1011, reason="Pre-call error")
        return

    # Phase 2: route to upstream LLM.
    try:
        data["user_api_key_dict"] = user_api_key_dict
        llm_call = await route_request(
            data=data,
            route_type="_arealtime",
            llm_router=llm_router,
            user_model=user_model,
        )
        await llm_call
    except websockets.exceptions.InvalidStatusCode as e:  # type: ignore
        verbose_proxy_logger.exception("Invalid status code")
        await websocket.close(code=e.status_code, reason="Invalid status code")
    except Exception:
        verbose_proxy_logger.exception("Internal server error")
        await websocket.close(code=1011, reason="Internal server error")


######################################################################

#                          /v1/assistant Endpoints


######################################################################


@router.get(
    "/v1/assistants",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
@router.get(
    "/assistants",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
async def get_assistants(
    request: Request,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Returns a list of assistants.

    API Reference docs - https://platform.openai.com/docs/api-reference/assistants/listAssistants
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        # Use orjson to parse JSON data, orjson speeds up requests significantly
        await request.body()

        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        # for now use custom_llm_provider=="openai" -> this will change as LiteLLM adds more providers for acreate_batch
        if llm_router is None:
            raise HTTPException(status_code=500, detail={"error": CommonProxyErrors.no_llm_router.value})
        response = await llm_router.aget_assistants(**data)

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                request_data=data,
                hidden_params=hidden_params,
            )
        )

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.error(f"litellm.proxy.proxy_server.get_assistants(): Exception occured - {e!s}")
        verbose_proxy_logger.debug(traceback.format_exc())
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e.detail)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                openai_code=getattr(e, "code", None),
                code=getattr(e, "status_code", 500),
            )


@router.post(
    "/v1/assistants",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
@router.post(
    "/assistants",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
async def create_assistant(
    request: Request,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Create assistant

    API Reference docs - https://platform.openai.com/docs/api-reference/assistants/createAssistant
    """
    global proxy_logging_obj
    data = {}  # ensure data always dict
    try:
        # Use orjson to parse JSON data, orjson speeds up requests significantly
        body = await request.body()
        data = orjson.loads(body)

        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        # for now use custom_llm_provider=="openai" -> this will change as LiteLLM adds more providers for acreate_batch
        if llm_router is None:
            raise HTTPException(status_code=500, detail={"error": CommonProxyErrors.no_llm_router.value})
        response = await llm_router.acreate_assistants(**data)

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                request_data=data,
                hidden_params=hidden_params,
            )
        )

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.error(
            f"litellm.proxy.proxy_server.create_assistant(): Exception occured - {e!s}"
        )
        verbose_proxy_logger.debug(traceback.format_exc())
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e.detail)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "code", getattr(e, "status_code", 500)),
            )


@router.delete(
    "/v1/assistants/{assistant_id:path}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
@router.delete(
    "/assistants/{assistant_id:path}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
async def delete_assistant(
    request: Request,
    assistant_id: str,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Delete assistant

    API Reference docs - https://platform.openai.com/docs/api-reference/assistants/createAssistant
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        # Use orjson to parse JSON data, orjson speeds up requests significantly

        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        # for now use custom_llm_provider=="openai" -> this will change as LiteLLM adds more providers for acreate_batch
        if llm_router is None:
            raise HTTPException(status_code=500, detail={"error": CommonProxyErrors.no_llm_router.value})
        response = await llm_router.adelete_assistant(assistant_id=assistant_id, **data)

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                request_data=data,
                hidden_params=hidden_params,
            )
        )

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.error(
            f"litellm.proxy.proxy_server.delete_assistant(): Exception occured - {e!s}"
        )
        verbose_proxy_logger.debug(traceback.format_exc())
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e.detail)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "code", getattr(e, "status_code", 500)),
            )


@router.post(
    "/v1/threads",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
@router.post(
    "/threads",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
async def create_threads(
    request: Request,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Create a thread.

    API Reference - https://platform.openai.com/docs/api-reference/threads/createThread
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        # Use orjson to parse JSON data, orjson speeds up requests significantly
        await request.body()

        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        # for now use custom_llm_provider=="openai" -> this will change as LiteLLM adds more providers for acreate_batch
        if llm_router is None:
            raise HTTPException(status_code=500, detail={"error": CommonProxyErrors.no_llm_router.value})
        response = await llm_router.acreate_thread(**data)

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                request_data=data,
                hidden_params=hidden_params,
            )
        )

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.error(f"litellm.proxy.proxy_server.create_threads(): Exception occured - {e!s}")
        verbose_proxy_logger.debug(traceback.format_exc())
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e.detail)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "code", getattr(e, "status_code", 500)),
            )


@router.get(
    "/v1/threads/{thread_id}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
@router.get(
    "/threads/{thread_id}",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
async def get_thread(
    request: Request,
    thread_id: str,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Retrieves a thread.

    API Reference - https://platform.openai.com/docs/api-reference/threads/getThread
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        # for now use custom_llm_provider=="openai" -> this will change as LiteLLM adds more providers for acreate_batch
        if llm_router is None:
            raise HTTPException(status_code=500, detail={"error": CommonProxyErrors.no_llm_router.value})
        response = await llm_router.aget_thread(thread_id=thread_id, **data)

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                request_data=data,
                hidden_params=hidden_params,
            )
        )

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.error(f"litellm.proxy.proxy_server.get_thread(): Exception occured - {e!s}")
        verbose_proxy_logger.debug(traceback.format_exc())
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e.detail)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "code", getattr(e, "status_code", 500)),
            )


@router.post(
    "/v1/threads/{thread_id}/messages",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
@router.post(
    "/threads/{thread_id}/messages",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
async def add_messages(
    request: Request,
    thread_id: str,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Create a message.

    API Reference - https://platform.openai.com/docs/api-reference/messages/createMessage
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        # Use orjson to parse JSON data, orjson speeds up requests significantly
        body = await request.body()
        data = orjson.loads(body)

        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        # for now use custom_llm_provider=="openai" -> this will change as LiteLLM adds more providers for acreate_batch
        if llm_router is None:
            raise HTTPException(status_code=500, detail={"error": CommonProxyErrors.no_llm_router.value})
        response = await llm_router.a_add_message(thread_id=thread_id, **data)

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                request_data=data,
                hidden_params=hidden_params,
            )
        )

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.error(f"litellm.proxy.proxy_server.add_messages(): Exception occured - {e!s}")
        verbose_proxy_logger.debug(traceback.format_exc())
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e.detail)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "code", getattr(e, "status_code", 500)),
            )


@router.get(
    "/v1/threads/{thread_id}/messages",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
@router.get(
    "/threads/{thread_id}/messages",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
async def get_messages(
    request: Request,
    thread_id: str,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Returns a list of messages for a given thread.

    API Reference - https://platform.openai.com/docs/api-reference/messages/listMessages
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        # for now use custom_llm_provider=="openai" -> this will change as LiteLLM adds more providers for acreate_batch
        if llm_router is None:
            raise HTTPException(status_code=500, detail={"error": CommonProxyErrors.no_llm_router.value})
        response = await llm_router.aget_messages(thread_id=thread_id, **data)

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                request_data=data,
                hidden_params=hidden_params,
            )
        )

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.error(f"litellm.proxy.proxy_server.get_messages(): Exception occured - {e!s}")
        verbose_proxy_logger.debug(traceback.format_exc())
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e.detail)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "code", getattr(e, "status_code", 500)),
            )


@router.post(
    "/v1/threads/{thread_id}/runs",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
@router.post(
    "/threads/{thread_id}/runs",
    dependencies=[Depends(user_api_key_auth)],
    tags=["assistants"],
)
async def run_thread(
    request: Request,
    thread_id: str,
    fastapi_response: Response,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Create a run.

    API Reference: https://platform.openai.com/docs/api-reference/runs/createRun
    """
    global proxy_logging_obj
    data: dict = {}
    try:
        body = await request.body()
        data = orjson.loads(body)
        # Include original request and headers in the data
        data = await add_litellm_data_to_request(
            data=data,
            request=request,
            general_settings=general_settings,
            user_api_key_dict=user_api_key_dict,
            version=version,
            proxy_config=proxy_config,
        )

        # for now use custom_llm_provider=="openai" -> this will change as LiteLLM adds more providers for acreate_batch
        if llm_router is None:
            raise HTTPException(status_code=500, detail={"error": CommonProxyErrors.no_llm_router.value})
        response = await llm_router.arun_thread(thread_id=thread_id, **data)

        if "stream" in data and data["stream"] is True:  # use generate_responses to stream responses
            return await create_response(
                generator=async_assistants_data_generator(
                    user_api_key_dict=user_api_key_dict,
                    response=response,
                    request_data=data,
                ),
                media_type="text/event-stream",
                headers={},  # Added empty headers dict, original call missed this argument
                request=request,
            )

        ### ALERTING ###
        asyncio.create_task(
            proxy_logging_obj.update_request_status(litellm_call_id=data.get("litellm_call_id", ""), status="success")
        )

        ### RESPONSE HEADERS ###
        hidden_params = getattr(response, "_hidden_params", {}) or {}
        model_id = hidden_params.get("model_id", None) or ""
        cache_key = hidden_params.get("cache_key", None) or ""
        api_base = hidden_params.get("api_base", None) or ""

        fastapi_response.headers.update(
            ProxyBaseLLMRequestProcessing.get_custom_headers(
                user_api_key_dict=user_api_key_dict,
                model_id=model_id,
                cache_key=cache_key,
                api_base=api_base,
                version=version,
                model_region=getattr(user_api_key_dict, "allowed_model_region", ""),
                request_data=data,
                hidden_params=hidden_params,
            )
        )

        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        verbose_proxy_logger.error(f"litellm.proxy.proxy_server.run_thread(): Exception occured - {e!s}")
        verbose_proxy_logger.debug(traceback.format_exc())
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "message", str(e.detail)),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=getattr(e, "message", error_msg),
                type=getattr(e, "type", "None"),
                param=getattr(e, "param", "None"),
                code=getattr(e, "code", getattr(e, "status_code", 500)),
            )


#### DEV UTILS ####

# @router.get(
#     "/utils/available_routes",
#     tags=["llm utils"],
#     dependencies=[Depends(user_api_key_auth)],
# )
# async def get_available_routes(user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)):
from litellm.llms.base_llm.base_utils import BaseTokenCounter
from litellm.repositories.config_repository import ConfigRepository
from litellm.repositories.model_repository import ModelRepository
from litellm.repositories.table_repositories import (
    AccessGroupRepository,
    ConfigOverridesRepository,
    InvitationLinkRepository,
    PromptRepository,
    SSOConfigRepository,
    UISettingsRepository,
)
from litellm.repositories.team_repository import TeamRepository
from litellm.repositories.user_repository import UserRepository


def _get_provider_token_counter(
    deployment: dict, model_to_use: str
) -> tuple[BaseTokenCounter | None, str | None, str | None]:
    """
    Auto-route to the correct provider's token counter based on model/deployment.
    Uses the existing get_provider_model_info infrastructure with switch-case pattern.
    """
    if deployment is None:
        return None

    from litellm.litellm_core_utils.get_llm_provider_logic import get_llm_provider

    full_model = deployment.get("litellm_params", {}).get("model", "")
    model: str | None = None
    custom_llm_provider: str | None = None

    try:
        # Use existing LiteLLM logic to determine provider
        model, custom_llm_provider, dynamic_api_key, api_base = get_llm_provider(
            model=full_model,
            custom_llm_provider=deployment.get("litellm_params", {}).get("custom_llm_provider"),
            api_base=deployment.get("litellm_params", {}).get("api_base"),
            api_key=deployment.get("litellm_params", {}).get("api_key"),
        )

        # Switch case pattern using existing get_provider_model_info
        from litellm.types.utils import LlmProviders
        from litellm.utils import ProviderConfigManager

        # Convert string provider to LlmProviders enum
        llm_provider_enum = LlmProviders(custom_llm_provider)
        # Add more provider mappings as needed

        if llm_provider_enum:
            provider_model_info = ProviderConfigManager.get_provider_model_info(
                model=full_model, provider=llm_provider_enum
            )
            if provider_model_info is not None:
                return (
                    provider_model_info.get_token_counter(),
                    model,
                    custom_llm_provider,
                )

    except Exception:
        # If provider detection fails, fall back to manual checks
        if full_model.startswith("anthropic/") or "anthropic" in full_model.lower():
            anthropic_model_info = AnthropicModelInfo()
            return anthropic_model_info.get_token_counter(), model, custom_llm_provider

    return None, None, None


async def _try_provider_token_count(
    provider_counter: "BaseTokenCounter",
    custom_llm_provider: str | None,
    model_to_use: str,
    messages: list | None,
    contents: list | None,
    deployment: dict[str, Any] | None,
    request_model: str,
    tools: list | None = None,
    system: str | None = None,
) -> Optional["TokenCountResponse"]:
    """Attempt provider-specific token counting. Returns result on success, None to fall through to local counting."""
    if not provider_counter.should_use_token_counting_api(custom_llm_provider=custom_llm_provider):
        return None
    try:
        result = await provider_counter.count_tokens(
            model_to_use=model_to_use or "",
            messages=messages,  # type: ignore
            contents=contents,
            deployment=deployment,
            request_model=request_model,
            tools=tools,
            system=system,
        )
    except httpx.HTTPStatusError as e:
        error_message = getattr(e, "message", None) or str(e)
        status_code = getattr(e, "status_code", None) or e.response.status_code
        raise ProxyException(
            message=error_message,
            type="token_counting_error",
            param="model",
            code=status_code,
        )
    if result is not None and result.error is True:
        if litellm.disable_token_counter is True:
            raise ProxyException(
                message=result.error_message or "Token counting failed",
                type="token_counting_error",
                param="model",
                code=result.status_code or 500,
            )
        verbose_proxy_logger.warning(
            f"Provider token counting failed ({result.status_code}): {result.error_message}. "
            "Falling back to local tokenizer."
        )
        return None
    return result


@router.post(
    "/utils/token_counter",
    tags=["llm utils"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=TokenCountResponse,
)
async def token_counter(request: TokenCountRequest, call_endpoint: bool = False):
    """
    Args:
        request: TokenCountRequest
        call_endpoint: bool - When set to "True" it will call the token counting endpoint - e.g Anthropic or Google AI Studio Token Counting APIs.

    Returns:
        TokenCountResponse
    """
    from litellm import token_counter

    global llm_router

    prompt = request.prompt
    messages = request.messages
    contents = request.contents
    tools = request.tools
    system = request.system

    #########################################################
    # Validate request
    #########################################################
    if prompt is None and messages is None and contents is None:
        raise HTTPException(status_code=400, detail="prompt or messages or contents must be provided")

    deployment: dict[str, Any] | None = None
    litellm_model_name = None
    model_info: ModelMapInfo | None = None
    if llm_router is not None:
        # get 1 deployment corresponding to the model
        try:
            deployment = await llm_router.async_get_available_deployment(
                model=request.model,
                request_kwargs={},
            )
        except Exception:
            verbose_proxy_logger.exception(
                "litellm.proxy.proxy_server.token_counter(): Exception occured while getting deployment"
            )
    if deployment is not None:
        litellm_model_name = deployment.get("litellm_params", {}).get("model")
        model_info = deployment.get("model_info", {})
        load_credentials_from_list(deployment.get("litellm_params", {}))
        # remove the custom_llm_provider_prefix in the litellm_model_name
        if "/" in litellm_model_name:
            litellm_model_name = litellm_model_name.split("/", 1)[1]

    model_to_use: str = (
        litellm_model_name or request.model
    )  # use litellm model name, if it's not avalable then fallback to request.model

    # Try provider-specific token counting first - only for non-direct requests (from provider endpoints)
    provider_counter: BaseTokenCounter | None = None
    custom_llm_provider: str | None = None
    if call_endpoint is True and deployment is not None:
        # Auto-route to the correct provider based on model
        provider_counter, _model, custom_llm_provider = _get_provider_token_counter(deployment, model_to_use)
        if _model is not None:
            model_to_use = _model

    if provider_counter is not None:
        result = await _try_provider_token_count(
            provider_counter=provider_counter,
            custom_llm_provider=custom_llm_provider,
            model_to_use=model_to_use,
            messages=messages,
            contents=contents,
            deployment=deployment,
            request_model=request.model,
            tools=tools,
            system=system,
        )
        if result is not None:
            return result

    # Check if token counter is disabled before fallback
    if litellm.disable_token_counter is True:
        raise ProxyException(
            message="Token counting is disabled and no provider API result available",
            type="token_counting_disabled",
            param="model",
            code=503,
        )

    # Default LiteLLM token counting
    custom_tokenizer: CustomHuggingfaceTokenizer | None = None
    if model_info is not None:
        custom_tokenizer = cast(
            CustomHuggingfaceTokenizer | None,
            model_info.get("custom_tokenizer", None),
        )
    _tokenizer_used = litellm.utils._select_tokenizer(model=model_to_use, custom_tokenizer=custom_tokenizer)

    tokenizer_used = str(_tokenizer_used["type"])
    total_tokens = token_counter(
        model=model_to_use,
        text=prompt,
        messages=messages,
        custom_tokenizer=_tokenizer_used,  # type: ignore
    )
    return TokenCountResponse(
        total_tokens=total_tokens,
        request_model=request.model,
        model_used=model_to_use,
        tokenizer_type=tokenizer_used,
    )


@router.get(
    "/utils/supported_openai_params",
    tags=["llm utils"],
    dependencies=[Depends(user_api_key_auth)],
)
async def supported_openai_params(model: str):
    """
    Returns supported openai params for a given litellm model name

    e.g. `gpt-4` vs `gpt-3.5-turbo`

    Example curl:
    ```
    curl -X GET --location 'http://localhost:4000/utils/supported_openai_params?model=gpt-3.5-turbo-16k' \
        --header 'Authorization: Bearer sk-1234'
    ```
    """
    try:
        model, custom_llm_provider, _, _ = litellm.get_llm_provider(model=model)
        return {
            "supported_openai_params": litellm.get_supported_openai_params(
                model=model, custom_llm_provider=custom_llm_provider
            )
        }
    except Exception:
        raise HTTPException(status_code=400, detail={"error": f"Could not map model={model}"})


@router.post(
    "/utils/transform_request",
    tags=["llm utils"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=RawRequestTypedDict,
)
async def transform_request(request: TransformRequestBody):
    from litellm.utils import return_raw_request

    try:
        is_request_body_safe(
            request_body=request.request_body,
            general_settings=general_settings,
            llm_router=llm_router,
            model=request.request_body.get("model", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})

    return return_raw_request(endpoint=request.call_type, kwargs=request.request_body)


async def _check_if_model_is_user_added(
    models: list[dict],
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: PrismaClient | None,
) -> list[dict]:
    """
    Check if model is in db

    Check if db model is 'created_by' == user_api_key_dict.user_id

    Only return models that match
    """
    if prisma_client is None:
        raise HTTPException(
            status_code=500,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )
    filtered_models = []
    for model in models:
        id = model.get("model_info", {}).get("id", None)
        if id is None:
            continue
        db_model = await ModelRepository(prisma_client).table.find_unique(where={"model_id": id})
        if db_model is not None:
            if db_model.created_by == user_api_key_dict.user_id:
                filtered_models.append(model)
    return filtered_models


def _check_if_model_is_team_model(models: list[DeploymentTypedDict], user_row: LiteLLM_UserTable) -> list[dict]:
    """
    Check if model is a team model

    Check if user is a member of the team that the model belongs to
    """

    user_team_models: list[dict] = []
    for model in models:
        model_team_id = model.get("model_info", {}).get("team_id", None)

        if model_team_id is not None:
            if model_team_id in user_row.teams:
                user_team_models.append(cast(dict, model))

    return user_team_models


async def non_admin_all_models(
    all_models: list[dict],
    llm_router: Router,
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: PrismaClient | None,
):
    """
    Check if model is in db

    Check if db model is 'created_by' == user_api_key_dict.user_id

    Only return models that match
    """
    if prisma_client is None:
        raise HTTPException(
            status_code=500,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    # Get all models that are user-added, when model created_by == user_api_key_dict.user_id
    all_models = await _check_if_model_is_user_added(
        models=all_models,
        user_api_key_dict=user_api_key_dict,
        prisma_client=prisma_client,
    )

    if user_api_key_dict.user_id:
        try:
            user_row = await UserRepository(prisma_client).table.find_unique(
                where={"user_id": user_api_key_dict.user_id}
            )
        except Exception:
            raise HTTPException(status_code=400, detail={"error": "User not found"})

        # Get all models that are team models, when model team_id == user_row.teams
        all_models += _check_if_model_is_team_model(
            models=llm_router.get_model_list() or [],
            user_row=user_row,
        )

    # de-duplicate models. Only return unique model ids
    unique_models = _deduplicate_litellm_router_models(models=all_models)
    return unique_models


def _add_team_models_to_all_models(
    team_db_objects_typed: list[LiteLLM_TeamTable],
    llm_router: Router,
) -> dict[str, set[str]]:
    """
    Add team models to all models
    """
    team_models: dict[str, set[str]] = {}

    for team_object in team_db_objects_typed:
        if (
            not team_object.models  # None or empty list = all model access
            or SpecialModelNames.all_proxy_models.value in team_object.models
        ):
            model_list = llm_router.get_model_list()
            if model_list is not None:
                for model in model_list:
                    model_id = model.get("model_info", {}).get("id", None)
                    if model_id is None:
                        continue
                    # if team model id set, check if team id in user_teams
                    team_model_id = model.get("model_info", {}).get("team_id", None)
                    can_add_model = False
                    if team_model_id is None or team_model_id in team_object.team_id:
                        can_add_model = True

                    if can_add_model:
                        team_models.setdefault(model_id, set()).add(team_object.team_id)
        else:
            for model_name in team_object.models:
                _models = llm_router.get_model_list(model_name=model_name, team_id=team_object.team_id)
                if _models is not None:
                    for model in _models:
                        model_id = model.get("model_info", {}).get("id", None)
                        if model_id is not None:
                            team_models.setdefault(model_id, set()).add(team_object.team_id)
    return team_models


async def _add_access_group_models_to_team_models(
    team_db_objects_typed: list[LiteLLM_TeamTable],
    llm_router: Router,
    prisma_client: PrismaClient,
    team_models: dict[str, set[str]],
) -> dict[str, set[str]]:
    """
    Resolve models reachable via team access groups and merge them into team_models.

    Batch-fetches all distinct access groups in a single DB query, then resolves
    each eligible team's access group models via the pre-fetched map.

    This ensures models associated with a team only through access groups
    (not directly in team.models) are included in the UI model listing.
    """
    # First pass: identify eligible teams and collect all distinct access group IDs
    eligible_teams: list[LiteLLM_TeamTable] = []
    all_access_group_ids: set[str] = set()

    for team_object in team_db_objects_typed:
        if not team_object.access_group_ids:
            continue

        # Skip teams with empty models list — they already have access to everything
        # (handled by _add_team_models_to_all_models)
        if not team_object.models or SpecialModelNames.all_proxy_models.value in team_object.models:
            continue

        eligible_teams.append(team_object)
        all_access_group_ids.update(team_object.access_group_ids)

    if not eligible_teams:
        return team_models

    # Single batch fetch for all access groups
    access_group_rows = await AccessGroupRepository(prisma_client).table.find_many(
        where={"access_group_id": {"in": list(all_access_group_ids)}}
    )
    ag_model_map: dict[str, list[str]] = {
        row.access_group_id: row.access_model_names or [] for row in access_group_rows
    }

    # Second pass: resolve deployments for each eligible team
    for team_object in eligible_teams:
        model_names: set[str] = set()
        for ag_id in team_object.access_group_ids or []:
            model_names.update(ag_model_map.get(ag_id, []))

        for model_name in model_names:
            deployments = llm_router.get_model_list(model_name=model_name, team_id=team_object.team_id)
            if deployments is not None:
                for deployment in deployments:
                    model_id = deployment.get("model_info", {}).get("id", None)
                    if model_id is not None:
                        team_models.setdefault(model_id, set()).add(team_object.team_id)

    return team_models


async def get_all_team_models(
    user_teams: list[str] | Literal["*"],
    prisma_client: PrismaClient,
    llm_router: Router,
) -> dict[str, list[str]]:
    """
    Get all models across all teams user is in.

    1. Get all teams user is in
    2. Get all models across all teams
    3. Return {"model_id": ["team_id1", "team_id2"]}
    """

    team_db_objects_typed: list[LiteLLM_TeamTable] = []

    if user_teams == "*":
        team_db_objects = await TeamRepository(prisma_client).table.find_many()
        team_db_objects_typed = [LiteLLM_TeamTable(**team_db_object.model_dump()) for team_db_object in team_db_objects]
    else:
        team_db_objects = await TeamRepository(prisma_client).table.find_many(where={"team_id": {"in": user_teams}})

        team_db_objects_typed = [LiteLLM_TeamTable(**team_db_object.model_dump()) for team_db_object in team_db_objects]

    team_models = _add_team_models_to_all_models(
        team_db_objects_typed=team_db_objects_typed,
        llm_router=llm_router,
    )

    # Also resolve models reachable via team access groups
    team_models = await _add_access_group_models_to_team_models(
        team_db_objects_typed=team_db_objects_typed,
        llm_router=llm_router,
        prisma_client=prisma_client,
        team_models=team_models,
    )

    # convert set to list
    returned_team_models: dict[str, list[str]] = {}
    for model_id, team_ids in team_models.items():
        returned_team_models[model_id] = list(team_ids)

    return returned_team_models


def get_direct_access_models(
    user_db_object: LiteLLM_UserTable,
    llm_router: Router,
) -> list[str]:
    """
    Get all models that user has direct access to.

    The 'all-proxy-models' sentinel grants direct access to every non-team
    deployment, mirroring how get_key_models expands it for the key/team path.
    """
    if SpecialModelNames.all_proxy_models.value in user_db_object.models:
        return llm_router.get_model_ids(exclude_team_models=True)

    return [
        model_id
        for model in user_db_object.models
        for deployment in (llm_router.get_model_list(model_name=model) or [])
        if (model_id := deployment.get("model_info", {}).get("id", None)) is not None
    ]


def _filter_models_to_user_accessible(all_models: list[dict]) -> list[dict]:
    """Keep only deployments the caller can use via direct access or team membership."""
    return [
        _model
        for _model in all_models
        if _model.get("model_info", {}).get("direct_access", False)
        or _model.get("model_info", {}).get("access_via_team_ids", [])
    ]


async def _populate_team_access_on_models(
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: PrismaClient,
    llm_router: Router,
    all_models: list[dict],
) -> list[dict]:
    """
    Populate `model_info.access_via_team_ids` and `model_info.direct_access`
    without filtering the model list.
    """
    user_teams: list[str] | Literal["*"] | None = None
    direct_access_models: list[str] = []
    if user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN:
        user_teams = "*"
        direct_access_models = llm_router.get_model_ids(exclude_team_models=True)  # has access to all models
    elif user_api_key_dict.user_id is not None:
        user_db_object = await UserRepository(prisma_client).table.find_unique(
            where={"user_id": user_api_key_dict.user_id}
        )
        if user_db_object is not None:
            user_object = LiteLLM_UserTable(**user_db_object.model_dump())
            user_teams = user_object.teams or []
            direct_access_models = get_direct_access_models(
                user_db_object=user_object,
                llm_router=llm_router,
            )
    if user_teams is not None:
        team_models = await get_all_team_models(
            user_teams=user_teams,
            prisma_client=prisma_client,
            llm_router=llm_router,
        )
        for _model in all_models:
            model_id = _model.get("model_info", {}).get("id", None)
            team_only_model_id = _model.get("model_info", {}).get("team_id", None)
            if model_id is not None:
                can_use_model = False
                if team_only_model_id is not None:
                    team_ids = team_models.get(model_id, [])
                    if team_ids and team_only_model_id in team_ids:
                        can_use_model = True
                else:
                    can_use_model = True
                if can_use_model:
                    _model["model_info"]["access_via_team_ids"] = team_models.get(model_id, [])

    direct_access_model_ids = set(direct_access_models)
    for _model in all_models:
        model_id = _model.get("model_info", {}).get("id", None)
        if model_id is not None:
            _model["model_info"]["direct_access"] = model_id in direct_access_model_ids

    return all_models


async def get_all_team_and_direct_access_models(
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: PrismaClient,
    llm_router: Router,
    all_models: list[dict],
) -> list[dict]:
    """
    Get all models across all teams user is in.
    """
    all_models = await _populate_team_access_on_models(
        user_api_key_dict=user_api_key_dict,
        prisma_client=prisma_client,
        llm_router=llm_router,
        all_models=all_models,
    )
    return _filter_models_to_user_accessible(all_models)


def _enrich_model_info_with_litellm_data(
    model: dict[str, Any], debug: bool = False, llm_router: Router | None = None
) -> dict[str, Any]:
    """
    Enrich a model dictionary with litellm model info (pricing, context window, etc.)
    and remove sensitive information.

    Args:
        model: Model dictionary to enrich
        debug: Whether to include debug information like openai_client
        llm_router: Optional router instance for debug info

    Returns:
        Enriched model dictionary with sensitive info removed
    """
    # provided model_info in config.yaml
    model_info = model.get("model_info", {})
    if debug is True:
        _openai_client = "None"
        if llm_router is not None:
            _openai_client = llm_router._get_client(deployment=model, kwargs={}, client_type="async") or "None"
        else:
            _openai_client = "llm_router_is_None"
        openai_client = str(_openai_client)
        model["openai_client"] = openai_client

    # read litellm model_prices_and_context_window.json to get the following:
    # input_cost_per_token, output_cost_per_token, max_tokens
    litellm_model_info = get_litellm_model_info(model=model)

    # 2nd pass on the model, try seeing if we can find model in litellm model_cost map
    if litellm_model_info == {}:
        # use litellm_param model_name to get model_info
        litellm_params = model.get("litellm_params", {})
        litellm_model = litellm_params.get("model", None)
        try:
            litellm_model_info = litellm.get_model_info(model=litellm_model)
        except Exception:
            litellm_model_info = {}
    # 3rd pass on the model, try seeing if we can find model but without the "/" in model cost map
    if litellm_model_info == {}:
        # use litellm_param model_name to get model_info
        litellm_params = model.get("litellm_params", {})
        litellm_model = litellm_params.get("model", None)
        if litellm_model:
            split_model = litellm_model.split("/")
            if len(split_model) > 0:
                litellm_model = split_model[-1]
            try:
                litellm_model_info = litellm.get_model_info(model=litellm_model, custom_llm_provider=split_model[0])
            except Exception:
                litellm_model_info = {}
    for k, v in litellm_model_info.items():
        if k not in model_info:
            model_info[k] = v
    model["model_info"] = model_info
    # don't return the api key / vertex credentials
    # don't return the llm credentials
    model = remove_sensitive_info_from_deployment(model, excluded_keys={"litellm_credential_name"})
    return model


async def _get_caller_byok_team_scope(
    user_api_key_dict: UserAPIKeyAuth | None,
    prisma_client: Any | None,
) -> set[str] | None:
    """
    Return the team IDs whose BYOK rows the caller is allowed to see via
    `/v2/model/info` search results.

    `None` means "no scoping" — used for admins and for callers/paths that
    have already been scoped upstream (or in tests that supply their own
    pre-filtered input set). A returned set (possibly empty) means BYOK rows
    must have `model_info.team_id` ∈ that set, otherwise they belong to a
    team the caller is not a member of and must be dropped.
    """
    if user_api_key_dict is None or prisma_client is None:
        return None
    if user_api_key_dict.user_role in (
        LitellmUserRoles.PROXY_ADMIN,
        LitellmUserRoles.PROXY_ADMIN_VIEW_ONLY,
    ):
        return None
    key_team_scope: set[str] = {user_api_key_dict.team_id} if user_api_key_dict.team_id else set()
    user_id = user_api_key_dict.user_id
    if user_id is None:
        return key_team_scope
    try:
        user_row = await UserRepository(prisma_client).table.find_unique(where={"user_id": user_id})
    except Exception:
        verbose_proxy_logger.exception(
            "Failed to look up caller teams while scoping BYOK search; defaulting to key team scope only."
        )
        return key_team_scope
    if user_row is None:
        return key_team_scope
    return key_team_scope | set(user_row.teams or [])


def _byok_row_outside_caller_teams(model_info_dict: dict[str, Any], allowed_team_ids: set[str] | None) -> bool:
    """Whether a team BYOK row belongs to a team the caller is not a member of.

    `team_id` is only set on team BYOK rows; non-team rows fall through
    unaffected. `allowed_team_ids is None` means no scoping (e.g. admins).
    """
    if allowed_team_ids is None:
        return False
    team_id = model_info_dict.get("team_id")
    if team_id is None:
        return False
    return team_id not in allowed_team_ids


# Hard cap on rows the DB-side BYOK search may pull when results need to be
# sorted across the full match set. Without this, an authenticated caller
# can hit `/v2/model/info?search=<broad>&sortBy=<field>` and force the
# proxy to materialize and decrypt every matching BYOK row on each request.
_SORTED_SEARCH_DB_FETCH_CAP = 500


async def _fetch_db_models_for_search(
    prisma_client: Any,
    proxy_config: Any,
    search_lower: str,
    db_model_ids_in_router: set[str],
    router_models_count: int,
    page: int,
    size: int,
    sort_by: str | None,
    is_byok_outside_caller_teams: Callable[[dict[str, Any]], bool],
) -> tuple[list[dict[str, Any]], int]:
    """
    Run the bounded DB query that backs `/v2/model/info?search=`. Returns
    `(decrypted_models, total_count)` where `total_count` is the cheap
    `count(...)` of rows matching `search` (not yet team-scoped) so the
    UI's pagination stays accurate without materializing every row.

    Earlier iterations also OR'd a JSON-path match on
    `model_info.team_public_model_name` to surface BYOK rows that live
    only in the DB. That branch fell back to `string_contains: ""`
    because Prisma's JSON `string_contains` is case-sensitive on
    Postgres, which let any authenticated caller force a full BYOK-table
    read via `/v2/model/info?search=x`. We rely on the router-side
    filter for `team_public_model_name` instead and keep the DB cost
    bounded by `search`.
    """
    db_where_condition: dict[str, Any] = {"model_name": {"contains": search_lower, "mode": "insensitive"}}
    if db_model_ids_in_router:
        db_where_condition["model_id"] = {"not": {"in": list(db_model_ids_in_router)}}

    # Unsorted searches only need enough DB rows to fill the current
    # page after counting router-side matches. Sorted searches need
    # ordering across the full match set, so fall back to a hard cap.
    if sort_by:
        take_limit = _SORTED_SEARCH_DB_FETCH_CAP
    else:
        take_limit = max(0, page * size - router_models_count)

    db_models_total_count = await ModelRepository(prisma_client).table.count(where=db_where_condition)

    db_models_raw: list = []
    if take_limit > 0:
        db_models_raw = await ModelRepository(prisma_client).table.find_many(
            where=db_where_condition,
            take=take_limit,
        )

    # Scope BYOK rows to the caller's allowed teams so non-admin callers
    # can't enumerate other teams' BYOK metadata via `?search=...`.
    matching_db_rows = [
        m
        for m in db_models_raw
        if not is_byok_outside_caller_teams(m.model_info if isinstance(m.model_info, dict) else {})
    ]

    decrypted: list[dict[str, Any]] = []
    for db_model in matching_db_rows:
        decrypted_models = proxy_config.decrypt_model_list_from_db([db_model])
        if decrypted_models:
            decrypted.extend(decrypted_models)

    return decrypted, db_models_total_count


async def _apply_search_filter_to_models(
    all_models: list[dict[str, Any]],
    search: str,
    prisma_client: Any | None,
    proxy_config: Any,
    user_api_key_dict: UserAPIKeyAuth | None = None,
    page: int = 1,
    size: int = 50,
    sort_by: str | None = None,
) -> tuple[list[dict[str, Any]], int | None]:
    """
    Apply search filter to models, querying database for additional matching models.

    Args:
        all_models: List of models to filter
        search: Search term (case-insensitive)
        prisma_client: Prisma client for database queries
        proxy_config: Proxy config for decrypting models
        user_api_key_dict: Caller identity used to scope BYOK matches to
            teams the caller belongs to. When omitted (None), no team
            scoping is applied — pass it from request handlers that expose
            this function to non-admin callers.
        page: Current page number (1-indexed). Used with ``size`` to bound
            the DB ``find_many(take=...)`` so a broad search term can't
            force a full table read + decrypt on every request.
        size: Page size. See ``page``.
        sort_by: Sort field. When set, results must be sorted across the
            full match set, so the DB fetch is capped at
            ``_SORTED_SEARCH_DB_FETCH_CAP`` instead of one page.

    Returns:
        Tuple of (filtered_models, total_count). total_count is None if not searching.
    """
    if not search or not search.strip():
        return all_models, None

    search_lower = search.lower().strip()

    allowed_team_ids = await _get_caller_byok_team_scope(
        user_api_key_dict=user_api_key_dict,
        prisma_client=prisma_client,
    )

    def _is_byok_outside_caller_teams(model_info_dict: dict[str, Any]) -> bool:
        return _byok_row_outside_caller_teams(model_info_dict, allowed_team_ids)

    def _model_matches_search(m: dict[str, Any]) -> bool:
        # Team BYOK models persist an internal `model_name`
        # (e.g. `model_name_{team_id}_{uuid}`) and expose the user-facing
        # name via `model_info.team_public_model_name`. Match both so the
        # name shown in the UI is searchable.
        if search_lower in (m.get("model_name") or "").lower():
            return True
        team_public_model_name = (m.get("model_info") or {}).get("team_public_model_name") or ""
        return search_lower in team_public_model_name.lower()

    # Filter models in router by search term, dropping BYOK rows that
    # belong to teams the caller is not a member of so search can't leak
    # other teams' models when the request omits `include_team_models` /
    # `teamId`.
    filtered_router_models = [
        m
        for m in all_models
        if _model_matches_search(m) and not _is_byok_outside_caller_teams(m.get("model_info") or {})
    ]

    # Separate filtered models into config vs db models, and track db model IDs
    filtered_config_models = []
    db_model_ids_in_router = set()

    for m in filtered_router_models:
        model_info = m.get("model_info", {})
        is_db_model = model_info.get("db_model", False)
        model_id = model_info.get("id")

        if is_db_model and model_id:
            db_model_ids_in_router.add(model_id)
        else:
            filtered_config_models.append(m)

    config_models_count = len(filtered_config_models)
    db_models_in_router_count = len(db_model_ids_in_router)
    router_models_count = config_models_count + db_models_in_router_count

    # Query database for additional models with search term
    db_models: list[dict[str, Any]] = []
    if prisma_client is not None:
        try:
            db_models, db_models_total_count = await _fetch_db_models_for_search(
                prisma_client=prisma_client,
                proxy_config=proxy_config,
                search_lower=search_lower,
                db_model_ids_in_router=db_model_ids_in_router,
                router_models_count=router_models_count,
                page=page,
                size=size,
                sort_by=sort_by,
                is_byok_outside_caller_teams=_is_byok_outside_caller_teams,
            )
            search_total_count = router_models_count + db_models_total_count
        except Exception as e:
            verbose_proxy_logger.exception(f"Error querying database models with search: {e!s}")
            search_total_count = router_models_count
    else:
        search_total_count = router_models_count

    return filtered_router_models + db_models, search_total_count


def _normalize_datetime_for_sorting(dt: Any) -> datetime | None:
    """
    Normalize a datetime value to a timezone-aware UTC datetime for sorting.

    This function handles:
    - None values: returns None
    - String values: parses ISO format strings and converts to UTC-aware datetime
    - Datetime objects: converts naive datetimes to UTC-aware, and aware datetimes to UTC

    Args:
        dt: Datetime value (None, str, or datetime object)

    Returns:
        UTC-aware datetime object, or None if input is None or cannot be parsed
    """
    if dt is None:
        return None

    if isinstance(dt, str):
        try:
            # Handle ISO format strings, including 'Z' suffix
            dt_str = dt.replace("Z", "+00:00") if dt.endswith("Z") else dt
            parsed_dt = datetime.fromisoformat(dt_str)
            # Ensure it's UTC-aware
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            else:
                parsed_dt = parsed_dt.astimezone(timezone.utc)
            return parsed_dt
        except (ValueError, AttributeError):
            return None

    if isinstance(dt, datetime):
        # If naive, assume UTC and make it aware
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        # If aware, convert to UTC
        return dt.astimezone(timezone.utc)

    return None


def _sort_models(
    all_models: list[dict[str, Any]],
    sort_by: str | None,
    sort_order: str = "asc",
) -> list[dict[str, Any]]:
    """
    Sort models by the specified field and order.

    Args:
        all_models: List of models to sort
        sort_by: Field to sort by (model_name, created_at, updated_at, costs, status)
        sort_order: Sort order (asc or desc)

    Returns:
        Sorted list of models
    """
    if not sort_by or sort_by not in [
        "model_name",
        "created_at",
        "updated_at",
        "costs",
        "status",
    ]:
        return all_models

    reverse = sort_order.lower() == "desc"

    def get_sort_key(model: dict[str, Any]) -> Any:
        model_info = model.get("model_info", {})

        if sort_by == "model_name":
            # Team BYOK models persist an internal `model_name` (e.g.
            # `model_name_{team_id}_{uuid}`) and expose the user-facing
            # name via `model_info.team_public_model_name` — same as the
            # UI's getDisplayModelName. Sort by the displayed name so
            # BYOK rows interleave alphabetically with non-BYOK rows
            # instead of clumping at the end on their opaque IDs.
            team_public_model_name = model_info.get("team_public_model_name")
            if team_public_model_name:
                return str(team_public_model_name).lower()
            return model.get("model_name", "").lower()

        elif sort_by == "created_at":
            created_at = model_info.get("created_at")
            normalized_dt = _normalize_datetime_for_sorting(created_at)
            if normalized_dt is None:
                # Put None values at the end for asc, at the start for desc
                return (
                    datetime.max.replace(tzinfo=timezone.utc)
                    if not reverse
                    else datetime.min.replace(tzinfo=timezone.utc)
                )
            return normalized_dt

        elif sort_by == "updated_at":
            updated_at = model_info.get("updated_at")
            normalized_dt = _normalize_datetime_for_sorting(updated_at)
            if normalized_dt is None:
                return (
                    datetime.max.replace(tzinfo=timezone.utc)
                    if not reverse
                    else datetime.min.replace(tzinfo=timezone.utc)
                )
            return normalized_dt

        elif sort_by == "costs":
            input_cost = model_info.get("input_cost_per_token", 0) or 0
            output_cost = model_info.get("output_cost_per_token", 0) or 0
            total_cost = input_cost + output_cost
            # Put 0 or None costs at the end for asc, at the start for desc
            if total_cost == 0:
                return float("inf") if not reverse else float("-inf")
            return total_cost

        elif sort_by == "status":
            # False (config) comes before True (db) for asc
            db_model = model_info.get("db_model", False)
            return db_model

        return None

    try:
        sorted_models = sorted(all_models, key=get_sort_key, reverse=reverse)
        return sorted_models
    except Exception as e:
        verbose_proxy_logger.exception(f"Error sorting models by {sort_by}: {e!s}")
        return all_models


def _paginate_models_response(
    all_models: list[dict[str, Any]],
    page: int,
    size: int,
    total_count: int | None,
    search: str | None,
) -> dict[str, Any]:
    """
    Paginate models and return response dictionary.

    Args:
        all_models: List of all models
        page: Current page number
        size: Page size
        total_count: Total count (if None, uses len(all_models))
        search: Search term (for logging)

    Returns:
        Paginated response dictionary
    """
    if total_count is None:
        total_count = len(all_models)

    skip = (page - 1) * size
    total_pages = -(-total_count // size) if total_count > 0 else 0
    paginated_models = all_models[skip : skip + size]

    verbose_proxy_logger.debug(
        f"Pagination: skip={skip}, take={size}, total_count={total_count}, total_pages={total_pages}, search={search}"
    )

    return {
        "data": paginated_models,
        "total_count": total_count,
        "current_page": page,
        "total_pages": total_pages,
        "size": size,
    }


def _team_models_resolve_to_names(team_models: list[str], access_groups: dict[str, Any]) -> list[str]:
    """Expand team model entries (including access group names) to concrete model names."""
    resolved: list[str] = []
    for name in team_models:
        if name in access_groups:
            resolved.extend(access_groups[name])
        else:
            resolved.append(name)
    return resolved


async def _load_team_object_for_model_filter(team_id: str, prisma_client: PrismaClient) -> LiteLLM_TeamTable | None:
    """Load team row from DB; returns None if missing or on error."""
    try:
        team_db_object = await TeamRepository(prisma_client).table.find_unique(where={"team_id": team_id})
        if team_db_object is None:
            verbose_proxy_logger.warning(f"Team {team_id} not found in database")
            return None
        return LiteLLM_TeamTable(**team_db_object.model_dump())
    except Exception as e:
        verbose_proxy_logger.exception(f"Error fetching team {team_id}: {e!s}")
        return None


async def _gather_team_accessible_model_ids(
    team_object: LiteLLM_TeamTable,
    team_id: str,
    prisma_client: PrismaClient,
    llm_router: Router,
) -> set[str]:
    """Collect model IDs the team can use from router config and DB."""
    team_accessible_model_ids: set[str] = set()
    access_groups = llm_router.get_model_access_groups() if llm_router else {}

    if not team_object.models or SpecialModelNames.all_proxy_models.value in team_object.models:
        model_list = llm_router.get_model_list() if llm_router else []
        if model_list is not None:
            for model in model_list:
                model_id = model.get("model_info", {}).get("id", None)
                if model_id is None:
                    continue
                team_model_id = model.get("model_info", {}).get("team_id", None)
                if team_model_id is None or team_model_id == team_id:
                    team_accessible_model_ids.add(model_id)
    else:
        resolved_model_names: set[str] = set()
        for model_name in team_object.models:
            if model_name in access_groups:
                resolved_model_names.update(access_groups[model_name])
            else:
                resolved_model_names.add(model_name)

        for model_name in resolved_model_names:
            _models = llm_router.get_model_list(model_name=model_name, team_id=team_id) if llm_router else []
            if _models is not None:
                for model in _models:
                    model_id = model.get("model_info", {}).get("id", None)
                    if model_id is not None:
                        team_accessible_model_ids.add(model_id)

    try:
        if team_object.models and SpecialModelNames.all_proxy_models.value not in team_object.models:
            _resolved_names = _team_models_resolve_to_names(team_object.models, access_groups)
            db_models = await ModelRepository(prisma_client).table.find_many(
                where={"model_name": {"in": _resolved_names}}
            )
            for db_model in db_models:
                if db_model.model_id:
                    team_accessible_model_ids.add(db_model.model_id)
    except Exception as e:
        verbose_proxy_logger.debug(f"Error querying database models for team {team_id}: {e!s}")

    return team_accessible_model_ids


async def _authorize_team_id_query(
    team_id: str,
    user_api_key_dict: UserAPIKeyAuth,
    prisma_client: PrismaClient,
) -> None:
    """
    `teamId` arrives untrusted via the /v2/model/info query string and the
    filter below includes BYOK rows solely on `model_info.team_id == team_id`.
    Without this guard, any authenticated user who knows (or guesses) another
    team's id could enumerate that team's BYOK model metadata. Allow only
    proxy admins or members of the requested team.
    """
    if user_api_key_dict.user_role in (
        LitellmUserRoles.PROXY_ADMIN,
        LitellmUserRoles.PROXY_ADMIN_VIEW_ONLY,
    ):
        return

    user_id = user_api_key_dict.user_id
    if user_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "Not authorized to view this team's models"},
        )
    try:
        user_row = await UserRepository(prisma_client).table.find_unique(where={"user_id": user_id})
    except Exception:
        verbose_proxy_logger.exception("Failed to look up caller teams while authorizing teamId filter")
        raise HTTPException(
            status_code=403,
            detail={"error": "Not authorized to view this team's models"},
        )

    if user_row is None or team_id not in (user_row.teams or []):
        raise HTTPException(
            status_code=403,
            detail={"error": "Not authorized to view this team's models"},
        )


async def _filter_models_by_team_id(
    all_models: list[dict[str, Any]],
    team_id: str,
    prisma_client: PrismaClient,
    llm_router: Router,
    user_api_key_dict: UserAPIKeyAuth | None = None,
) -> list[dict[str, Any]]:
    """
    Filter models by team ID. Returns models where:
    - team_id matches the model's BYOK team_id, OR
    - team_id is in access_via_team_ids, OR
    - model_id is reachable via team.models / access groups

    Args:
        all_models: List of models to filter
        team_id: Team ID to filter by
        prisma_client: Prisma client for database queries
        llm_router: Router instance for config queries
        user_api_key_dict: Caller auth context. When provided, the caller must
            be a proxy admin or a member of `team_id`; otherwise raises 403.

    Returns:
        Filtered list of models
    """
    if user_api_key_dict is not None:
        await _authorize_team_id_query(
            team_id=team_id,
            user_api_key_dict=user_api_key_dict,
            prisma_client=prisma_client,
        )

    team_object = await _load_team_object_for_model_filter(team_id, prisma_client)
    if team_object is None:
        return []

    team_accessible_model_ids = await _gather_team_accessible_model_ids(team_object, team_id, prisma_client, llm_router)

    # When filtering by a specific team we want exactly the models that team
    # can use: its BYOK rows and the deployments resolved from team.models /
    # access groups. `direct_access` describes the viewer's own permissions
    # (the admin path sets it on every non-team model) and must NOT widen the
    # team's visible set, otherwise selecting a team in the UI still shows
    # every public model the admin can call.
    filtered_models = []
    for _model in all_models:
        model_info = _model.get("model_info", {})
        model_id = model_info.get("id", None)

        # BYOK rows owned by this team are always accessible to it, even if
        # they haven't been re-added to team.models for some reason.
        if model_info.get("team_id") == team_id:
            filtered_models.append(_model)
            continue

        access_via_team_ids = model_info.get("access_via_team_ids", [])
        if isinstance(access_via_team_ids, list) and team_id in access_via_team_ids:
            filtered_models.append(_model)
            continue

        # Catches models resolved from team.models / access groups that
        # weren't enriched with access_via_team_ids upstream.
        if model_id and model_id in team_accessible_model_ids:
            filtered_models.append(_model)

    return filtered_models


async def _find_model_by_id(
    model_id: str,
    search: str | None,
    llm_router,
    prisma_client,
    proxy_config,
) -> tuple[list, int | None]:
    """Find a model by its ID and optionally filter by search term."""
    found_model = None

    # First, search in config
    if llm_router is not None:
        found_model = llm_router.get_model_info(id=model_id)
        if found_model:
            found_model = copy.deepcopy(found_model)

    # If not found in config, search in database
    if found_model is None:
        try:
            db_model = await ModelRepository(prisma_client).table.find_unique(where={"model_id": model_id})
            if db_model:
                # Convert database model to router format
                decrypted_models = proxy_config.decrypt_model_list_from_db([db_model])
                if decrypted_models:
                    found_model = decrypted_models[0]
        except Exception as e:
            verbose_proxy_logger.exception(f"Error querying database for modelId {model_id}: {e!s}")

    # If model found, verify search filter if provided
    if found_model is not None:
        if search is not None and search.strip():
            search_lower = search.lower().strip()
            model_name = found_model.get("model_name", "")
            if search_lower not in model_name.lower():
                # Model found but doesn't match search filter
                found_model = None

    # Set all_models to the found model or empty list
    all_models = [found_model] if found_model is not None else []
    search_total_count: int | None = len(all_models)
    return all_models, search_total_count


@router.get(
    "/v2/model/info",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
)
async def model_info_v2(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    model: str | None = fastapi.Query(None, description="Specify the model name (optional)"),
    user_models_only: bool | None = fastapi.Query(False, description="Only return models added by this user"),
    include_team_models: bool | None = fastapi.Query(
        False, description="Return all models across all teams user is in."
    ),
    debug: bool | None = False,
    page: int = Query(1, description="Page number", ge=1),
    size: int = Query(50, description="Page size", ge=1),
    search: str | None = fastapi.Query(None, description="Search model names (case-insensitive partial match)"),
    modelId: str | None = fastapi.Query(None, description="Search for a specific model by its unique ID"),
    teamId: str | None = fastapi.Query(
        None,
        description="Filter models by team ID. Returns models with direct_access=True or teamId in access_via_team_ids",
    ),
    sortBy: str | None = fastapi.Query(
        None,
        description="Field to sort by. Options: model_name, created_at, updated_at, costs, status",
    ),
    sortOrder: str | None = fastapi.Query(
        "asc",
        description="Sort order. Options: asc, desc",
    ),
):
    """
    Paginated model metadata for proxy deployments (pricing, provider, team access).

    Returns configured router deployments with enriched `model_info` (costs, provider,
    context window, etc.). Sensitive fields such as API keys and api_base are omitted.

    Query parameters:
        model: Filter to a single public `model_name`.
        user_models_only: When true, only return models created by the calling user.
        include_team_models: When true, populate `access_via_team_ids` and `direct_access`
            on each model and filter to deployments the caller can use.
        page / size: Pagination controls (defaults: page=1, size=50).
        search: Case-insensitive partial match on model name or team public name.
        modelId: Return a single deployment by LiteLLM model id.
        teamId: Filter to models with direct access or team membership for this team id.
        sortBy / sortOrder: Sort by model_name, created_at, updated_at, costs, or status.

    Example request:
    ```
    curl -X GET 'http://localhost:4000/v2/model/info?include_team_models=true&page=1&size=50' \\
    --header 'Authorization: Bearer sk-1234'
    ```

    Example response:
    ```json
    {
        "data": [
            {
                "model_name": "gpt-4",
                "litellm_params": {"model": "openai/gpt-4.1"},
                "model_info": {
                    "id": "abc123",
                    "litellm_provider": "openai",
                    "access_via_team_ids": ["team-1"],
                    "direct_access": true
                }
            }
        ],
        "total_count": 1,
        "current_page": 1,
        "total_pages": 1,
        "size": 50
    }
    ```
    """
    global llm_model_list, general_settings, user_config_file_path, proxy_config, llm_router

    # Return empty data array when no models are configured (graceful handling for fresh installs)
    if llm_router is None or not llm_router.model_list:
        return {
            "data": [],
            "total_count": 0,
            "current_page": page,
            "total_pages": 0,
            "size": size,
        }

    if prisma_client is None:
        raise HTTPException(
            status_code=500,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    # Load existing config
    await proxy_config.get_config()

    # If modelId is provided, search for the specific model
    if modelId is not None:
        all_models, search_total_count = await _find_model_by_id(
            model_id=modelId,
            search=search,
            llm_router=llm_router,
            prisma_client=prisma_client,
            proxy_config=proxy_config,
        )
    else:
        # Normal flow when modelId is not provided
        all_models = copy.deepcopy(llm_router.model_list)

        if user_model is not None:
            # if user does not use a config.yaml, https://github.com/BerriAI/litellm/issues/2061
            all_models += [user_model]

        if model is not None:
            all_models = [m for m in all_models if m["model_name"] == model]

        # Apply search filter if provided
        all_models, search_total_count = await _apply_search_filter_to_models(
            all_models=all_models,
            search=search or "",
            prisma_client=prisma_client,
            proxy_config=proxy_config,
            user_api_key_dict=user_api_key_dict,
            page=page,
            size=size,
            sort_by=sortBy,
        )

    if user_models_only:
        all_models = await non_admin_all_models(
            all_models=all_models,
            llm_router=llm_router,
            user_api_key_dict=user_api_key_dict,
            prisma_client=prisma_client,
        )

    if include_team_models:
        all_models = await get_all_team_and_direct_access_models(
            user_api_key_dict=user_api_key_dict,
            prisma_client=prisma_client,
            llm_router=llm_router,
            all_models=all_models,
        )

    # Fill in model info based on config.yaml and litellm model_prices_and_context_window.json
    # This must happen before teamId filtering so that direct_access and access_via_team_ids are populated
    for i, _model in enumerate(all_models):
        all_models[i] = _enrich_model_info_with_litellm_data(
            model=_model,
            debug=debug if debug is not None else False,
            llm_router=llm_router,
        )

    # Apply teamId filter if provided
    if teamId is not None and teamId.strip():
        all_models = await _filter_models_by_team_id(
            all_models=all_models,
            team_id=teamId.strip(),
            prisma_client=prisma_client,
            llm_router=llm_router,
            user_api_key_dict=user_api_key_dict,
        )
        # Update search_total_count after teamId filter is applied
        search_total_count = len(all_models)

    # If modelId was provided, update search_total_count after filters are applied
    # to ensure pagination reflects the final filtered result (0 or 1)
    if modelId is not None:
        search_total_count = len(all_models)

    # Apply sorting before pagination
    if sortBy:
        # Validate sortOrder
        if sortOrder and sortOrder.lower() not in ["asc", "desc"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sortOrder: {sortOrder}. Must be 'asc' or 'desc'",
            )
        all_models = _sort_models(
            all_models=all_models,
            sort_by=sortBy,
            sort_order=sortOrder or "asc",
        )

    verbose_proxy_logger.debug("all_models: %s", all_models)

    # Append A2A agents to models list
    from litellm.proxy.agent_endpoints.model_list_helpers import (
        append_agents_to_model_info,
    )

    all_models = await append_agents_to_model_info(
        models=all_models,
        user_api_key_dict=user_api_key_dict,
    )

    # Update total count to include agents
    search_total_count = len(all_models)

    # Translate `model_name` to the public name for team-scoped rows.
    all_models = [_translate_model_name_for_response(m) for m in all_models]

    return _paginate_models_response(
        all_models=all_models,
        page=page,
        size=size,
        total_count=search_total_count,
        search=search,
    )


@router.get(
    "/model/streaming_metrics",
    description="View time to first token for models in spend logs",
    tags=["model management"],
    include_in_schema=False,
    dependencies=[Depends(user_api_key_auth)],
)
async def model_streaming_metrics(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    _selected_model_group: str | None = None,
    startTime: datetime | None = None,
    endTime: datetime | None = None,
):
    global prisma_client, llm_router
    if prisma_client is None:
        raise ProxyException(
            message=CommonProxyErrors.db_not_connected_error.value,
            type="internal_error",
            param="None",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    startTime = startTime or datetime.now() - timedelta(days=7)  # show over past week
    endTime = endTime or datetime.now()

    is_same_day = startTime.date() == endTime.date()
    if is_same_day:
        sql_query = """
            SELECT
                api_base,
                model_group,
                model,
                "startTime",
                request_id,
                EXTRACT(epoch FROM ("completionStartTime" - "startTime")) AS time_to_first_token
            FROM
                "LiteLLM_SpendLogs"
            WHERE
                "model_group" = $1 AND "cache_hit" != 'True'
                AND "completionStartTime" IS NOT NULL
                AND "completionStartTime" != "endTime"
                AND DATE("startTime") = DATE($2::timestamp)
            GROUP BY
                api_base,
                model_group,
                model,
                request_id
            ORDER BY
                time_to_first_token DESC;
        """
    else:
        sql_query = """
            SELECT
                api_base,
                model_group,
                model,
                DATE_TRUNC('day', "startTime")::DATE AS day,
                AVG(EXTRACT(epoch FROM ("completionStartTime" - "startTime"))) AS time_to_first_token
            FROM
                "LiteLLM_SpendLogs"
            WHERE
                "startTime" BETWEEN $2::timestamp AND $3::timestamp
                AND "model_group" = $1 AND "cache_hit" != 'True'
                AND "completionStartTime" IS NOT NULL
                AND "completionStartTime" != "endTime"
            GROUP BY
                api_base,
                model_group,
                model,
                day
            ORDER BY
                time_to_first_token DESC;
        """

    _all_api_bases = set()
    db_response = await prisma_client.db.query_raw(sql_query, _selected_model_group, startTime, endTime)
    _daily_entries: dict = {}  # {"Jun 23": {"model1": 0.002, "model2": 0.003}}
    if db_response is not None:
        for model_data in db_response:
            _api_base = model_data["api_base"]
            _model = model_data["model"]
            time_to_first_token = model_data["time_to_first_token"]
            unique_key = ""
            if is_same_day:
                _request_id = model_data["request_id"]
                unique_key = _request_id
                if _request_id not in _daily_entries:
                    _daily_entries[_request_id] = {}
            else:
                _day = model_data["day"]
                unique_key = _day
                time_to_first_token = model_data["time_to_first_token"]
                if _day not in _daily_entries:
                    _daily_entries[_day] = {}
            _combined_model_name = str(_model)
            if "https://" in _api_base:
                _combined_model_name = str(_api_base)
            if "/openai/" in _combined_model_name:
                _combined_model_name = _combined_model_name.split("/openai/")[0]

            _all_api_bases.add(_combined_model_name)

            _daily_entries[unique_key][_combined_model_name] = time_to_first_token

        """
        each entry needs to be like this:
        {
            date: 'Jun 23',
            'gpt-4-https://api.openai.com/v1/': 0.002,
            'gpt-43-https://api.openai.com-12/v1/': 0.002,
        }
        """
        # convert daily entries to list of dicts

        response: list[dict] = []

        # sort daily entries by date
        _daily_entries = dict(sorted(_daily_entries.items(), key=lambda item: item[0]))
        for day in _daily_entries:
            entry = {"date": str(day)}
            for model_key, latency in _daily_entries[day].items():
                entry[model_key] = latency
            response.append(entry)

        return {
            "data": response,
            "all_api_bases": list(_all_api_bases),
        }


@router.get(
    "/model/metrics",
    description="View number of requests & avg latency per model on config.yaml",
    tags=["model management"],
    include_in_schema=False,
    dependencies=[Depends(user_api_key_auth)],
)
async def model_metrics(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    _selected_model_group: str | None = "gpt-4-32k",
    startTime: datetime | None = None,
    endTime: datetime | None = None,
    api_key: str | None = None,
    customer: str | None = None,
):
    global prisma_client, llm_router
    if prisma_client is None:
        raise ProxyException(
            message="Prisma Client is not initialized",
            type="internal_error",
            param="None",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    startTime = startTime or datetime.now() - timedelta(days=DAYS_IN_A_MONTH)
    endTime = endTime or datetime.now()

    if api_key is None or api_key == "undefined":
        api_key = "null"

    if customer is None or customer == "undefined":
        customer = "null"

    sql_query = """
        SELECT
            api_base,
            model_group,
            model,
            DATE_TRUNC('day', "startTime")::DATE AS day,
            AVG(EXTRACT(epoch FROM ("endTime" - "startTime")) / NULLIF("completion_tokens", 0)) AS avg_latency_per_token
        FROM
            "LiteLLM_SpendLogs"
        WHERE
            "startTime" >= $2::timestamp AND "startTime" <= $3::timestamp
            AND "model_group" = $1 AND "cache_hit" != 'True'
            AND (
                CASE
                    WHEN $4 != 'null' THEN "api_key" = $4
                    ELSE TRUE
                END
            )
            AND (
                CASE
                    WHEN $5 != 'null' THEN "end_user" = $5
                    ELSE TRUE
                END
            )
        GROUP BY
            api_base,
            model_group,
            model,
            day
        HAVING
            SUM(completion_tokens) > 0
        ORDER BY
            avg_latency_per_token DESC;
    """
    _all_api_bases = set()
    db_response = await prisma_client.db.query_raw(
        sql_query, _selected_model_group, startTime, endTime, api_key, customer
    )
    _daily_entries: dict = {}  # {"Jun 23": {"model1": 0.002, "model2": 0.003}}

    if db_response is not None:
        for model_data in db_response:
            _api_base = model_data["api_base"]
            _model = model_data["model"]
            _day = model_data["day"]
            _avg_latency_per_token = model_data["avg_latency_per_token"]
            if _day not in _daily_entries:
                _daily_entries[_day] = {}
            _combined_model_name = str(_model)
            if _api_base is not None and "https://" in _api_base:
                _combined_model_name = str(_api_base)
            if _combined_model_name is not None and "/openai/" in _combined_model_name:
                _combined_model_name = _combined_model_name.split("/openai/")[0]

            _all_api_bases.add(_combined_model_name)
            _daily_entries[_day][_combined_model_name] = _avg_latency_per_token

        """
        each entry needs to be like this:
        {
            date: 'Jun 23',
            'gpt-4-https://api.openai.com/v1/': 0.002,
            'gpt-43-https://api.openai.com-12/v1/': 0.002,
        }
        """
        # convert daily entries to list of dicts

        response: list[dict] = []

        # sort daily entries by date
        _daily_entries = dict(sorted(_daily_entries.items(), key=lambda item: item[0]))
        for day in _daily_entries:
            entry = {"date": str(day)}
            for model_key, latency in _daily_entries[day].items():
                entry[model_key] = latency
            response.append(entry)

        return {
            "data": response,
            "all_api_bases": list(_all_api_bases),
        }


@router.get(
    "/model/metrics/slow_responses",
    description="View number of hanging requests per model_group",
    tags=["model management"],
    include_in_schema=False,
    dependencies=[Depends(user_api_key_auth)],
)
async def model_metrics_slow_responses(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    _selected_model_group: str | None = "gpt-4-32k",
    startTime: datetime | None = None,
    endTime: datetime | None = None,
    api_key: str | None = None,
    customer: str | None = None,
):
    global prisma_client, llm_router, proxy_logging_obj
    if prisma_client is None:
        raise ProxyException(
            message="Prisma Client is not initialized",
            type="internal_error",
            param="None",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if api_key is None or api_key == "undefined":
        api_key = "null"

    if customer is None or customer == "undefined":
        customer = "null"

    startTime = startTime or datetime.now() - timedelta(days=DAYS_IN_A_MONTH)
    endTime = endTime or datetime.now()

    alerting_threshold = (
        proxy_logging_obj.slack_alerting_instance.alerting_threshold or DEFAULT_SLACK_ALERTING_THRESHOLD
    )
    alerting_threshold = int(alerting_threshold)

    sql_query = """
SELECT
    api_base,
    COUNT(*) AS total_count,
    SUM(CASE
        WHEN ("endTime" - "startTime") >= (INTERVAL '1 SECOND' * CAST($1 AS INTEGER)) THEN 1
        ELSE 0
    END) AS slow_count
FROM
    "LiteLLM_SpendLogs"
WHERE
    "model_group" = $2
    AND "cache_hit" != 'True'
    AND "startTime" >= $3::timestamp
    AND "startTime" <= $4::timestamp
    AND (
        CASE
            WHEN $5 != 'null' THEN "api_key" = $5
            ELSE TRUE
        END
    )
    AND (
        CASE
            WHEN $6 != 'null' THEN "end_user" = $6
            ELSE TRUE
        END
    )
GROUP BY
    api_base
ORDER BY
    slow_count DESC;
    """

    db_response = await prisma_client.db.query_raw(
        sql_query,
        alerting_threshold,
        _selected_model_group,
        startTime,
        endTime,
        api_key,
        customer,
    )

    if db_response is not None:
        for row in db_response:
            _api_base = row.get("api_base") or ""
            if "/openai/" in _api_base:
                _api_base = _api_base.split("/openai/")[0]
            row["api_base"] = _api_base
    return db_response


@router.get(
    "/model/metrics/exceptions",
    description="View number of failed requests per model on config.yaml",
    tags=["model management"],
    include_in_schema=False,
    dependencies=[Depends(user_api_key_auth)],
)
async def model_metrics_exceptions(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    _selected_model_group: str | None = None,
    startTime: datetime | None = None,
    endTime: datetime | None = None,
    api_key: str | None = None,
    customer: str | None = None,
):
    global prisma_client, llm_router
    if prisma_client is None:
        raise ProxyException(
            message="Prisma Client is not initialized",
            type="internal_error",
            param="None",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    startTime = startTime or datetime.now() - timedelta(days=DAYS_IN_A_MONTH)
    endTime = endTime or datetime.now()

    if api_key is None or api_key == "undefined":
        api_key = "null"

    """
    """
    sql_query = """
        WITH cte AS (
            SELECT
                CASE WHEN api_base = '' THEN litellm_model_name ELSE CONCAT(litellm_model_name, '-', api_base) END AS combined_model_api_base,
                exception_type,
                COUNT(*) AS num_rate_limit_exceptions
            FROM "LiteLLM_ErrorLogs"
            WHERE
                "startTime" >= $1::timestamp
                AND "endTime" <= $2::timestamp
                AND model_group = $3
            GROUP BY combined_model_api_base, exception_type
        )
        SELECT
            combined_model_api_base,
            COUNT(*) AS total_exceptions,
            json_object_agg(exception_type, num_rate_limit_exceptions) AS exception_counts
        FROM cte
        GROUP BY combined_model_api_base
        ORDER BY total_exceptions DESC
        LIMIT 200;
    """
    db_response = await prisma_client.db.query_raw(sql_query, startTime, endTime, _selected_model_group, api_key)
    response: list[dict] = []
    exception_types = set()

    """
    Return Data
    {
        "combined_model_api_base": "gpt-3.5-turbo-https://api.openai.com/v1/,
        "total_exceptions": 5,
        "BadRequestException": 5,
        "TimeoutException": 2
    }
    """

    if db_response is not None:
        # loop through all models
        for model_data in db_response:
            model = model_data.get("combined_model_api_base", "")
            total_exceptions = model_data.get("total_exceptions", 0)
            exception_counts = model_data.get("exception_counts", {})
            curr_row = {
                "model": model,
                "total_exceptions": total_exceptions,
            }
            curr_row.update(exception_counts)
            response.append(curr_row)
            for k, v in exception_counts.items():
                exception_types.add(k)

    return {"data": response, "exception_types": list(exception_types)}


def _deployment_matches_allowed_model_names(model: dict[str, Any], allowed_model_names: set[str]) -> bool:
    """Match a router deployment against allowed public model names.

    Team-scoped rows store an internal routing key in ``model_name``; callers
    with key/team restrictions still refer to the public name in
    ``model_info.team_public_model_name``.
    """
    if model.get("model_name") in allowed_model_names:
        return True
    model_info = model.get("model_info")
    if not isinstance(model_info, dict):
        return False
    team_public_model_name = model_info.get("team_public_model_name")
    return isinstance(team_public_model_name, str) and team_public_model_name in allowed_model_names


def _get_v1_model_info_allowed_model_names(
    user_api_key_dict: UserAPIKeyAuth,
    llm_router: Router,
) -> set[str] | None:
    """Return key/team allowlisted public model names, or None if unrestricted."""
    model_access_groups = llm_router.get_model_access_groups()
    proxy_model_list = llm_router.get_model_names()
    key_models = get_key_models(
        user_api_key_dict=user_api_key_dict,
        proxy_model_list=proxy_model_list,
        model_access_groups=model_access_groups,
    )
    team_models = get_team_models(
        team_models=user_api_key_dict.team_models,
        proxy_model_list=proxy_model_list,
        model_access_groups=model_access_groups,
    )
    if not key_models and not team_models:
        return None
    return set(
        get_complete_model_list(
            key_models=key_models,
            team_models=team_models,
            proxy_model_list=proxy_model_list,
            user_model=user_model,
            infer_model_from_keys=general_settings.get("infer_model_from_keys", False),
            llm_router=llm_router,
            return_wildcard_routes=False,
        )
    )


def _filter_v1_model_info_deployments(
    all_models: list[dict],
    allowed_model_names: set[str] | None,
) -> list[dict]:
    if allowed_model_names is None:
        return all_models
    return [model for model in all_models if _deployment_matches_allowed_model_names(model, allowed_model_names)]


def _translate_model_name_for_response(model: dict) -> dict:
    """For team-scoped DB rows, replace `model_name` with the public name
    in `model_info.team_public_model_name` before returning. The DB column
    and the in-memory router index keep the internal mangled name
    (`model_name_{team_id}_{uuid}`) as the routing key -- this swap is a
    presentation-layer concern. Returns a shallow copy; never mutates.

    Without this swap the internal name leaks into `/v1/model/info` and
    `/v2/model/info`, the dashboard binds its edit form to it, and a
    non-rename save round-trips the internal name back -- corrupting
    `team_public_model_name` and the team ACL (see issue #28382).
    """
    if not isinstance(model, dict):
        return model
    model_info = model.get("model_info") or {}
    if not isinstance(model_info, dict):
        return model
    team_public = model_info.get("team_public_model_name")
    team_id = model_info.get("team_id")
    if not team_public or not team_id:
        return model
    current = model.get("model_name") or ""
    if not current.startswith(f"model_name_{team_id}_"):
        return model
    return {**model, "model_name": team_public}


def _get_proxy_model_info(model: dict) -> dict:
    # provided model_info in config.yaml
    model_info = model.get("model_info", {})

    # read litellm model_prices_and_context_window.json to get the following:
    # input_cost_per_token, output_cost_per_token, max_tokens
    litellm_model_info = get_litellm_model_info(model=model)

    # 2nd pass on the model, try seeing if we can find model in litellm model_cost map
    if litellm_model_info == {}:
        # use litellm_param model_name to get model_info
        litellm_params = model.get("litellm_params", {})
        litellm_model = litellm_params.get("model", None)
        try:
            litellm_model_info = litellm.get_model_info(model=litellm_model)
        except Exception:
            litellm_model_info = {}
    # 3rd pass on the model, try seeing if we can find model but without the "/" in model cost map
    if litellm_model_info == {}:
        # use litellm_param model_name to get model_info
        litellm_params = model.get("litellm_params", {})
        litellm_model = litellm_params.get("model", None)
        split_model = litellm_model.split("/")
        if len(split_model) > 0:
            litellm_model = split_model[-1]
        try:
            litellm_model_info = litellm.get_model_info(model=litellm_model, custom_llm_provider=split_model[0])
        except Exception:
            litellm_model_info = {}
    for k, v in litellm_model_info.items():
        if k not in model_info:
            model_info[k] = v
    model["model_info"] = model_info
    # don't return the llm credentials
    model = remove_sensitive_info_from_deployment(deployment_dict=model, excluded_keys={"litellm_credential_name"})

    return _translate_model_name_for_response(model)


@router.get(
    "/model/info",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
)
@router.get(
    "/v1/model/info",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
)
async def model_info_v1(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    litellm_model_id: str | None = None,
    include_team_models: bool | None = fastapi.Query(
        False,
        description="When true, filter to deployments the caller can use via direct access or team membership.",
    ),
    teamId: str | None = fastapi.Query(
        None,
        description="Filter models by team ID. Returns models with direct_access=True or teamId in access_via_team_ids",
    ),
):
    """
    Provides more info about each model in /models, including config.yaml descriptions (except api key and api base)

    Parameters:
        litellm_model_id: Optional[str] = None (this is the value of `x-litellm-model-id` returned in response headers)

        - When litellm_model_id is passed, it will return the info for that specific model
        - When litellm_model_id is not passed, it will return the info for all models
        - include_team_models: When true, filter to deployments the caller can use (same as /v2/model/info).
        - teamId: Filter to models accessible by the given team.

    Each model in the list response includes `model_info.access_via_team_ids` and
    `model_info.direct_access` when the proxy database is connected.

    Returns:
        Returns a dictionary containing information about each model.

    Example Response:
    ```json
    {
        "data": [
                    {
                        "model_name": "fake-openai-endpoint",
                        "litellm_params": {
                            "api_base": "https://exampleopenaiendpoint-production.up.railway.app/",
                            "model": "openai/fake"
                        },
                        "model_info": {
                            "id": "112f74fab24a7a5245d2ced3536dd8f5f9192c57ee6e332af0f0512e08bed5af",
                            "db_model": false
                        }
                    }
                ]
    }

    ```
    """
    global llm_model_list, general_settings, user_config_file_path, proxy_config, llm_router, user_model

    # Unit tests call this handler directly; FastAPI normally resolves Query defaults.
    if not isinstance(include_team_models, bool):
        include_team_models = False
    if not isinstance(teamId, str):
        teamId = None

    if user_model is not None:
        # user is trying to get specific model from litellm router
        try:
            model_info: dict = cast(dict, litellm.get_model_info(model=user_model))
        except Exception:
            model_info = {}
        _deployment_info = Deployment(
            model_name="*",
            litellm_params=LiteLLM_Params(
                model=user_model,
            ),
            model_info=model_info,
        )
        _deployment_info_dict = _deployment_info.model_dump()
        _deployment_info_dict = remove_sensitive_info_from_deployment(
            deployment_dict=_deployment_info_dict,
            excluded_keys={"litellm_credential_name"},
        )
        return {"data": _deployment_info_dict}

    if llm_model_list is None:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "LLM Model List not loaded in. Make sure you passed models in your config.yaml or on the LiteLLM Admin UI. - https://docs.litellm.ai/docs/proxy/configs"
            },
        )

    if llm_router is None:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "LLM Router is not loaded in. Make sure you passed models in your config.yaml or on the LiteLLM Admin UI. - https://docs.litellm.ai/docs/proxy/configs"
            },
        )

    if prisma_client is None and (include_team_models or (teamId is not None and teamId.strip())):
        raise HTTPException(
            status_code=500,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    if litellm_model_id is not None:
        # user is trying to get specific model from litellm router
        deployment_info = llm_router.get_deployment(model_id=litellm_model_id)
        if deployment_info is None:
            raise HTTPException(
                status_code=400,
                detail={"error": f"Model id = {litellm_model_id} not found on litellm proxy"},
            )
        _deployment_info_dict = _get_proxy_model_info(model=deployment_info.model_dump(exclude_none=True))
        single_model_list: list[dict] = [_deployment_info_dict]
        if prisma_client is not None:
            single_model_list = await _populate_team_access_on_models(
                user_api_key_dict=user_api_key_dict,
                prisma_client=prisma_client,
                llm_router=llm_router,
                all_models=single_model_list,
            )
            if include_team_models:
                single_model_list = _filter_models_to_user_accessible(single_model_list)
            if teamId is not None and teamId.strip():
                single_model_list = await _filter_models_by_team_id(
                    all_models=single_model_list,
                    team_id=teamId.strip(),
                    prisma_client=prisma_client,
                    llm_router=llm_router,
                    user_api_key_dict=user_api_key_dict,
                )
        return {"data": single_model_list}

    # Return router deployments (same source as /v2/model/info), not wildcard-
    # expanded model names from get_complete_model_list(). Team-scoped rows
    # use internal routing keys (model_name_{team_id}_{uuid}) and were omitted
    # when v1 resolved models only via public model_name strings.
    all_models: list[dict] = copy.deepcopy(llm_router.model_list)
    alias_models = copy.deepcopy(llm_router.get_model_list_from_model_alias())
    all_models.extend(alias_models)

    all_models = expand_wildcard_deployments_for_model_info(all_models)

    allowed_model_names = _get_v1_model_info_allowed_model_names(
        user_api_key_dict=user_api_key_dict,
        llm_router=llm_router,
    )

    all_models = _filter_v1_model_info_deployments(
        all_models=all_models,
        allowed_model_names=allowed_model_names,
    )

    # Team BYOK deployments carry an internal routing key and other teams'
    # public name/team_id/api_base; drop the ones the caller cannot access so
    # listing the full router model_list does not leak cross-team metadata.
    allowed_team_ids = await _get_caller_byok_team_scope(
        user_api_key_dict=user_api_key_dict,
        prisma_client=prisma_client,
    )
    all_models = [
        model
        for model in all_models
        if not _byok_row_outside_caller_teams(model.get("model_info") or {}, allowed_team_ids)
    ]

    if prisma_client is not None:
        all_models = await _populate_team_access_on_models(
            user_api_key_dict=user_api_key_dict,
            prisma_client=prisma_client,
            llm_router=llm_router,
            all_models=all_models,
        )

    if include_team_models:
        all_models = _filter_models_to_user_accessible(all_models)

    all_models = [
        _translate_model_name_for_response(_enrich_model_info_with_litellm_data(model=model, llm_router=llm_router))
        for model in all_models
    ]

    if teamId is not None and teamId.strip():
        all_models = await _filter_models_by_team_id(
            all_models=all_models,
            team_id=teamId.strip(),
            prisma_client=cast(PrismaClient, prisma_client),
            llm_router=llm_router,
            user_api_key_dict=user_api_key_dict,
        )

    verbose_proxy_logger.debug("all_models: %s", all_models)
    return {"data": all_models}


def _get_model_group_info(
    llm_router: Router, all_models_str: list[str], model_group: str | None
) -> list[ModelGroupInfoProxy]:
    model_groups: list[ModelGroupInfoProxy] = []

    unique_models = []
    for model in all_models_str:
        if model not in unique_models:
            unique_models.append(model)

    for model in unique_models:
        if model_group is not None and model_group != model:
            continue

        _model_group_info = llm_router.get_model_group_info(model_group=model)

        if _model_group_info is not None:
            model_groups.append(ModelGroupInfoProxy(**_model_group_info.model_dump()))
        else:
            model_group_info = ModelGroupInfoProxy(
                model_group=model,
                providers=[],
            )
            model_groups.append(model_group_info)

    ## check for public model groups
    if litellm.public_model_groups is not None:
        for mg in model_groups:
            if mg.model_group in litellm.public_model_groups:
                mg.is_public_model_group = True

    return model_groups


@router.get(
    "/model_group/info",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
)
async def model_group_info(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    model_group: str | None = None,
):
    """
    Get information about all the deployments on litellm proxy, including config.yaml descriptions (except api key and api base)

    - /model_group/info returns all model groups. End users of proxy should use /model_group/info since those models will be used for /chat/completions, /embeddings, etc.
    - /model_group/info?model_group=rerank-english-v3.0 returns all model groups for a specific model group (`model_name` in config.yaml)



    Example Request (All Models):
    ```shell
    curl -X 'GET' \
    'http://localhost:4000/model_group/info' \
    -H 'accept: application/json' \
    -H 'x-api-key: sk-1234'
    ```

    Example Request (Specific Model Group):
    ```shell
    curl -X 'GET' \
    'http://localhost:4000/model_group/info?model_group=rerank-english-v3.0' \
    -H 'accept: application/json' \
    -H 'Authorization: Bearer sk-1234'
    ```

    Example Request (Specific Wildcard Model Group): (e.g. `model_name: openai/*` on config.yaml)
    ```shell
    curl -X 'GET' \
    'http://localhost:4000/model_group/info?model_group=openai/tts-1'
    -H 'accept: application/json' \
    -H 'Authorization: Bearersk-1234'
    ```

    Learn how to use and set wildcard models [here](https://docs.litellm.ai/docs/wildcard_routing)

    Example Response:
    ```json
        {
            "data": [
                {
                "model_group": "rerank-english-v3.0",
                "providers": [
                    "cohere"
                ],
                "max_input_tokens": null,
                "max_output_tokens": null,
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "mode": null,
                "tpm": null,
                "rpm": null,
                "supports_parallel_function_calling": false,
                "supports_vision": false,
                "supports_function_calling": false,
                "supported_openai_params": [
                    "stream",
                    "temperature",
                    "max_tokens",
                    "logit_bias",
                    "top_p",
                    "frequency_penalty",
                    "presence_penalty",
                    "stop",
                    "n",
                    "extra_headers"
                ]
                },
                {
                "model_group": "gpt-3.5-turbo",
                "providers": [
                    "openai"
                ],
                "max_input_tokens": 16385.0,
                "max_output_tokens": 4096.0,
                "input_cost_per_token": 1.5e-06,
                "output_cost_per_token": 2e-06,
                "mode": "chat",
                "tpm": null,
                "rpm": null,
                "supports_parallel_function_calling": false,
                "supports_vision": false,
                "supports_function_calling": true,
                "supported_openai_params": [
                    "frequency_penalty",
                    "logit_bias",
                    "logprobs",
                    "top_logprobs",
                    "max_tokens",
                    "max_completion_tokens",
                    "n",
                    "presence_penalty",
                    "seed",
                    "stop",
                    "stream",
                    "stream_options",
                    "temperature",
                    "top_p",
                    "tools",
                    "tool_choice",
                    "function_call",
                    "functions",
                    "max_retries",
                    "extra_headers",
                    "parallel_tool_calls",
                    "response_format"
                ]
                },
                {
                "model_group": "llava-hf",
                "providers": [
                    "openai"
                ],
                "max_input_tokens": null,
                "max_output_tokens": null,
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "mode": null,
                "tpm": null,
                "rpm": null,
                "supports_parallel_function_calling": false,
                "supports_vision": true,
                "supports_function_calling": false,
                "supported_openai_params": [
                    "frequency_penalty",
                    "logit_bias",
                    "logprobs",
                    "top_logprobs",
                    "max_tokens",
                    "max_completion_tokens",
                    "n",
                    "presence_penalty",
                    "seed",
                    "stop",
                    "stream",
                    "stream_options",
                    "temperature",
                    "top_p",
                    "tools",
                    "tool_choice",
                    "function_call",
                    "functions",
                    "max_retries",
                    "extra_headers",
                    "parallel_tool_calls",
                    "response_format"
                ]
                }
            ]
            }
    ```
    """
    global llm_model_list, general_settings, user_config_file_path, proxy_config, llm_router

    # Return empty data array when no models are configured (graceful handling for fresh installs)
    if llm_model_list is None or llm_router is None or not llm_model_list:
        return {"data": []}

    from litellm.proxy.utils import get_available_models_for_user

    # Get available models for the user
    all_models_str = await get_available_models_for_user(
        user_api_key_dict=user_api_key_dict,
        llm_router=llm_router,
        general_settings=general_settings,
        user_model=user_model,
        prisma_client=prisma_client,
        proxy_logging_obj=proxy_logging_obj,
        team_id=None,
        include_model_access_groups=False,
        only_model_access_groups=False,
        return_wildcard_routes=False,
        user_api_key_cache=user_api_key_cache,
    )
    model_groups: list[ModelGroupInfoProxy] = _get_model_group_info(
        llm_router=llm_router, all_models_str=all_models_str, model_group=model_group
    )

    # Append A2A agents to model groups
    from litellm.proxy.agent_endpoints.model_list_helpers import (
        append_agents_to_model_group,
    )

    model_groups = await append_agents_to_model_group(
        model_groups=model_groups,
        user_api_key_dict=user_api_key_dict,
    )

    return {"data": model_groups}


@router.get(
    "/model/settings",
    description="Returns provider name, description, and required parameters for each provider",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def model_settings():
    """
    Used by UI to generate 'model add' page
    {
        field_name=field_name,
        field_type=allowed_args[field_name]["type"], # string/int
        field_description=field_info.description or "", # human-friendly description
        field_value=general_settings.get(field_name, None), # example value
    }
    """

    returned_list = []
    for provider in litellm.provider_list:
        returned_list.append(
            ProviderInfo(
                name=provider,
                fields=litellm.get_provider_fields(custom_llm_provider=provider),
            )
        )

    return returned_list


#### ALERTING MANAGEMENT ENDPOINTS ####


@router.get(
    "/alerting/settings",
    description="Return the configurable alerting param, description, and current value",
    tags=["alerting"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def alerting_settings(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    global proxy_logging_obj, prisma_client
    """
    Used by UI to generate 'alerting settings' page
    {
        field_name=field_name,
        field_type=allowed_args[field_name]["type"], # string/int
        field_description=field_info.description or "", # human-friendly description
        field_value=general_settings.get(field_name, None), # example value
    }
    """
    if prisma_client is None:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    if not _user_has_admin_view(user_api_key_dict):
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"{CommonProxyErrors.not_allowed_access.value}, your role={user_api_key_dict.user_role}"
            },
        )

    ## get general settings from db
    db_general_settings = await ConfigRepository(prisma_client).table.find_first(
        where={"param_name": "general_settings"}
    )

    if db_general_settings is not None and db_general_settings.param_value is not None:
        db_general_settings_dict = dict(db_general_settings.param_value)
        alerting_args_dict: dict = db_general_settings_dict.get("alerting_args", {})  # type: ignore
        alerting_values: list | None = db_general_settings_dict.get("alerting")  # type: ignore
    else:
        alerting_args_dict = {}
        alerting_values = None

    allowed_args = {
        "slack_alerting": {"type": "Boolean"},
        "daily_report_frequency": {"type": "Integer"},
        "report_check_interval": {"type": "Integer"},
        "budget_alert_ttl": {"type": "Integer"},
        "outage_alert_ttl": {"type": "Integer"},
        "region_outage_alert_ttl": {"type": "Integer"},
        "minor_outage_alert_threshold": {"type": "Integer"},
        "major_outage_alert_threshold": {"type": "Integer"},
        "max_outage_alert_list_size": {"type": "Integer"},
    }

    _slack_alerting: SlackAlerting = proxy_logging_obj.slack_alerting_instance
    _slack_alerting_args_dict = _slack_alerting.alerting_args.model_dump()

    return_val = []

    is_slack_enabled = False

    if general_settings.get("alerting") and isinstance(general_settings["alerting"], list):
        if "slack" in general_settings["alerting"]:
            is_slack_enabled = True

    _response_obj = ConfigList(
        field_name="slack_alerting",
        field_type=allowed_args["slack_alerting"]["type"],
        field_description="Enable slack alerting for monitoring proxy in production: llm outages, budgets, spend tracking failures.",
        field_value=is_slack_enabled,
        stored_in_db=True if alerting_values is not None else False,
        field_default_value=None,
        premium_field=False,
    )
    return_val.append(_response_obj)

    for field_name, field_info in SlackAlertingArgs.model_fields.items():
        if field_name in allowed_args:
            _stored_in_db: bool | None = None
            if field_name in alerting_args_dict:
                _stored_in_db = True
            else:
                _stored_in_db = False

            _response_obj = ConfigList(
                field_name=field_name,
                field_type=allowed_args[field_name]["type"],
                field_description=field_info.description or "",
                field_value=_slack_alerting_args_dict.get(field_name, None),
                stored_in_db=_stored_in_db,
                field_default_value=field_info.default,
                premium_field=(True if field_name == "region_outage_alert_ttl" else False),
            )
            return_val.append(_response_obj)
    return return_val


#### EXPERIMENTAL QUEUING ####
@router.post(
    "/queue/chat/completions",
    tags=["experimental"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def async_queue_request(
    request: Request,
    fastapi_response: Response,
    model: str | None = None,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    global general_settings, user_debug, proxy_logging_obj
    """
    v2 attempt at a background worker to handle queuing

    Just supports /chat/completion calls currently.

    Now using a FastAPI background task + /chat/completions compatible endpoint
    """
    data = {}
    try:
        data = await request.json()  # type: ignore

        # Include original request and headers in the data
        data["proxy_server_request"] = {
            "url": str(request.url),
            "method": request.method,
            "headers": _safe_get_request_headers(request).copy(),
            "body": copy.copy(data),  # use copy instead of deepcopy
        }

        verbose_proxy_logger.debug("receiving data: %s", data)
        data["model"] = (
            general_settings.get("completion_model", None)  # server default
            or user_model  # model name passed via cli args
            or model  # for azure deployments
            or data.get("model", None)  # default passed in http request
        )

        # users can pass in 'user' param to /chat/completions. Don't override it
        if data.get("user", None) is None and user_api_key_dict.user_id is not None:
            # if users are using user_api_key_auth, set `user` in `data`
            data["user"] = user_api_key_dict.user_id

        if not isinstance(data.get("metadata"), dict):
            # Covers both missing and JSON-string metadata (multipart /
            # extra_body); see above for the same guard upstream.
            data["metadata"] = {}
        data["metadata"]["user_api_key"] = user_api_key_dict.api_key
        data["metadata"]["user_api_key_metadata"] = user_api_key_dict.metadata
        _headers = _safe_get_request_headers(request).copy()
        _headers.pop("authorization", None)  # do not store the original `sk-..` api key in the db
        data["metadata"]["headers"] = _headers
        data["metadata"]["user_api_key_alias"] = getattr(user_api_key_dict, "key_alias", None)
        data["metadata"]["user_api_key_user_id"] = user_api_key_dict.user_id
        data["metadata"]["user_api_key_team_id"] = getattr(user_api_key_dict, "team_id", None)
        data["metadata"]["user_api_key_object_permission_id"] = getattr(user_api_key_dict, "object_permission_id", None)
        data["metadata"]["user_api_key_team_object_permission_id"] = getattr(
            user_api_key_dict, "team_object_permission_id", None
        )
        data["metadata"]["endpoint"] = str(request.url)

        global user_temperature, user_request_timeout, user_max_tokens, user_api_base
        # override with user settings, these are params passed via cli
        if user_temperature:
            data["temperature"] = user_temperature
        if user_request_timeout:
            data["request_timeout"] = user_request_timeout
        if user_max_tokens:
            data["max_tokens"] = user_max_tokens
        if user_api_base:
            data["api_base"] = user_api_base

        if llm_router is None:
            raise HTTPException(status_code=500, detail={"error": CommonProxyErrors.no_llm_router.value})

        response = await llm_router.schedule_acompletion(**data)

        if "stream" in data and data["stream"] is True:  # use generate_responses to stream responses
            return StreamingResponse(
                async_data_generator(
                    user_api_key_dict=user_api_key_dict,
                    response=response,
                    request_data=data,
                    request=request,
                ),
                media_type="text/event-stream",
            )

        fastapi_response.headers.update({"x-litellm-priority": str(data["priority"])})
        return response
    except Exception as e:
        await proxy_logging_obj.post_call_failure_hook(
            user_api_key_dict=user_api_key_dict, original_exception=e, request_data=data
        )
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "detail", f"Authentication Error({e!s})"),
                type=ProxyErrorTypes.auth_error,
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        elif isinstance(e, ProxyException):
            raise e
        raise ProxyException(
            message="Authentication Error, " + str(e),
            type=ProxyErrorTypes.auth_error,
            param=getattr(e, "param", "None"),
            code=status.HTTP_400_BAD_REQUEST,
        )


@app.get("/fallback/login", tags=["experimental"], include_in_schema=False)
async def fallback_login(request: Request):
    """
    Create Proxy API Keys using Google Workspace SSO. Requires setting PROXY_BASE_URL in .env
    PROXY_BASE_URL should be the your deployed proxy endpoint, e.g. PROXY_BASE_URL="https://litellm-production-7002.up.railway.app/"
    Example:
    """
    from litellm.proxy.proxy_server import ui_link

    # get url from request
    redirect_url = get_custom_url(str(request.base_url))
    if redirect_url.endswith("/"):
        redirect_url += "sso/callback"
    else:
        redirect_url += "/sso/callback"

    from fastapi.responses import HTMLResponse

    hide_default_credentials_hint = (
        os.getenv("LITELLM_HIDE_DEFAULT_CREDENTIALS_HINT", "false").lower() == "true"
        or general_settings.get("hide_default_credentials_hint", False) is True
    )
    return HTMLResponse(
        content=build_ui_login_form(
            show_deprecation_banner=False,
            hide_default_credentials_hint=hide_default_credentials_hint,
        ),
        status_code=200,
    )


@router.post("/login", include_in_schema=False)  # hidden since this is a helper for UI sso login
async def login(request: Request):
    global premium_user, general_settings, master_key
    from litellm.proxy.auth.login_utils import authenticate_user, create_ui_token_object, encode_ui_session_jwt
    from litellm.proxy.utils import get_custom_url

    form = await request.form()
    username = str(form.get("username"))
    password = str(form.get("password"))

    # Authenticate user and get login result
    login_result = await authenticate_user(
        username=username,
        password=password,
        master_key=master_key,
        prisma_client=prisma_client,
    )

    # Create UI token object
    returned_ui_token_object = create_ui_token_object(
        login_result=login_result,
        general_settings=general_settings,
        premium_user=premium_user,
    )

    # Generate JWT token
    jwt_token = encode_ui_session_jwt(returned_ui_token_object, cast(str, master_key))

    # Build redirect URL
    litellm_dashboard_ui = get_custom_url(str(request.base_url))
    if litellm_dashboard_ui.endswith("/"):
        litellm_dashboard_ui += "ui/"
    else:
        litellm_dashboard_ui += "/ui/"
    litellm_dashboard_ui += "?login=success"

    # Honor a same-origin return_to preserved by the sign-in page (e.g. the aggregate DCR connect flow's
    # authorize round-trip), mirroring the SSO callback; otherwise land on the dashboard. Gated by
    # _is_same_origin_return_path (strictly relative path) so it can never be an open redirect, and the
    # one-shot cookie is cleared after use.
    from litellm.proxy.management_endpoints.ui_sso import _sso_return_to_redirect

    # Resume through the SAME resumer the SSO callback uses, rather than a second, narrower arm.
    # _persist_return_to_cookie stores both shapes it accepts (a relative same-origin path AND a
    # control_plane_url-matching absolute URL); honoring only the relative one here silently dropped
    # the control-plane case, landing the user on the dashboard. One function decides how a stored
    # return_to is honored for EVERY sign-in branch, so the write and read sets cannot diverge: it
    # sets the token cookie on the same-origin arm and hands off via a one-time login code on the
    # cross-origin arm, and clears the one-shot cookie in both.
    cp_return_to = request.cookies.get("litellm_cp_return_to")
    if cp_return_to:
        try:
            resumed = await _sso_return_to_redirect(
                return_to=cp_return_to,
                jwt_token=jwt_token,
                redis_usage_cache=redis_usage_cache,
                user_api_key_cache=user_api_key_cache,
            )
        except Exception:  # noqa: BLE001  # resuming must NEVER block a completed sign-in
            # The symmetric half of _persist_return_to_cookie's "never raises" contract. The resumer
            # rejects a return_to that no longer matches control_plane_url (a config change between
            # the cookie's write and this read), and the user has ALREADY authenticated here —
            # failing their login over a stale one-shot cookie is the worst possible outcome. Land
            # on the dashboard instead; the cookie is cleared below either way.
            verbose_proxy_logger.info("Ignoring stale litellm_cp_return_to cookie; landing on dashboard")
            resumed = None
        if resumed is not None:
            return resumed

    # Create redirect response with cookie
    redirect_response = RedirectResponse(url=litellm_dashboard_ui, status_code=303)
    redirect_response.set_cookie(key="token", value=jwt_token)
    if cp_return_to:
        redirect_response.delete_cookie(key="litellm_cp_return_to")
    return redirect_response


@router.post("/v2/login", include_in_schema=False)  # hidden helper for UI logins via API
async def login_v2(request: Request):
    global premium_user, general_settings, master_key
    from litellm.proxy.auth.login_utils import authenticate_user, create_ui_token_object, encode_ui_session_jwt
    from litellm.proxy.utils import get_custom_url

    try:
        body = await request.json()
        username = str(body.get("username"))
        password = str(body.get("password"))

        login_result = await authenticate_user(
            username=username,
            password=password,
            master_key=master_key,
            prisma_client=prisma_client,
        )

        returned_ui_token_object = create_ui_token_object(
            login_result=login_result,
            general_settings=general_settings,
            premium_user=premium_user,
        )

        jwt_token = encode_ui_session_jwt(returned_ui_token_object, cast(str, master_key))

        litellm_dashboard_ui = get_custom_url(str(request.base_url))
        if litellm_dashboard_ui.endswith("/"):
            litellm_dashboard_ui += "ui/"
        else:
            litellm_dashboard_ui += "/ui/"
        litellm_dashboard_ui += "?login=success"

        # Token is included in the response body so the UI can set a JS-accessible
        # cookie even when a reverse proxy (e.g. nginx-ingress) adds HttpOnly to the
        # server-set cookie, which would otherwise cause an infinite login redirect.
        json_response = JSONResponse(
            content={"redirect_url": litellm_dashboard_ui, "token": jwt_token},
            status_code=status.HTTP_200_OK,
        )
        json_response.set_cookie(key="token", value=jwt_token)
        return json_response
    except Exception as e:
        verbose_proxy_logger.exception(f"litellm.proxy.proxy_server.login_v2(): Exception occurred - {e!s}")
        if isinstance(e, ProxyException):
            raise e
        elif isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "detail", str(e)),
                type=ProxyErrorTypes.auth_error,
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=error_msg,
                type=ProxyErrorTypes.auth_error,
                param="None",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@router.post(
    "/v3/login", include_in_schema=False
)  # control-plane login — always returns token in body for cross-origin use
async def login_v3(request: Request):
    global premium_user, general_settings, master_key
    from litellm.proxy.auth.login_utils import authenticate_user, create_ui_token_object, encode_ui_session_jwt
    from litellm.proxy.utils import get_custom_url

    try:
        if not general_settings.get("control_plane_url"):
            raise ProxyException(
                message="/v3/login is only available on workers with control_plane_url configured",
                type=ProxyErrorTypes.not_found_error,
                param="control_plane_url",
                code=status.HTTP_404_NOT_FOUND,
            )

        body = await request.json()
        username = str(body.get("username"))
        password = str(body.get("password"))

        login_result = await authenticate_user(
            username=username,
            password=password,
            master_key=master_key,
            prisma_client=prisma_client,
        )

        returned_ui_token_object = create_ui_token_object(
            login_result=login_result,
            general_settings=general_settings,
            premium_user=premium_user,
        )

        jwt_token = encode_ui_session_jwt(returned_ui_token_object, cast(str, master_key))

        litellm_dashboard_ui = get_custom_url(str(request.base_url))
        if litellm_dashboard_ui.endswith("/"):
            litellm_dashboard_ui += "ui/"
        else:
            litellm_dashboard_ui += "/ui/"
        litellm_dashboard_ui += "?login=success"

        # Store JWT behind a single-use opaque code (60s TTL)
        code = secrets.token_urlsafe(32)
        cache_key = f"login_code:{code}"
        cache_value = {"token": jwt_token, "redirect_url": litellm_dashboard_ui}
        if redis_usage_cache is not None:
            await redis_usage_cache.async_set_cache(key=cache_key, value=cache_value, ttl=60)
        else:
            await user_api_key_cache.async_set_cache(key=cache_key, value=cache_value, ttl=60)

        return JSONResponse(
            content={"code": code, "expires_in": 60},
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        verbose_proxy_logger.exception(f"litellm.proxy.proxy_server.login_v3(): Exception occurred - {e!s}")
        if isinstance(e, ProxyException):
            raise e
        elif isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "detail", str(e)),
                type=ProxyErrorTypes.auth_error,
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
            )
        else:
            error_msg = f"{e!s}"
            raise ProxyException(
                message=error_msg,
                type=ProxyErrorTypes.auth_error,
                param="None",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@router.post("/v3/login/exchange", include_in_schema=False)  # exchange single-use opaque code for JWT
async def login_v3_exchange(request: Request):
    try:
        if not general_settings.get("control_plane_url"):
            raise ProxyException(
                message="/v3/login/exchange is only available on workers with control_plane_url configured",
                type=ProxyErrorTypes.not_found_error,
                param="control_plane_url",
                code=status.HTTP_404_NOT_FOUND,
            )

        body = await request.json()
        code = body.get("code")
        if not code:
            raise ProxyException(
                message="Missing 'code' parameter",
                type=ProxyErrorTypes.auth_error,
                param="code",
                code=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"login_code:{code}"
        if redis_usage_cache is not None:
            cached_data = await redis_usage_cache.async_get_cache(key=cache_key)
        else:
            cached_data = await user_api_key_cache.async_get_cache(key=cache_key)

        if not cached_data or not isinstance(cached_data, dict):
            raise ProxyException(
                message="Invalid or expired login code",
                type=ProxyErrorTypes.auth_error,
                param="code",
                code=status.HTTP_401_UNAUTHORIZED,
            )

        # Single-use: delete immediately
        if redis_usage_cache is not None:
            await redis_usage_cache.async_delete_cache(key=cache_key)
        else:
            await user_api_key_cache.async_delete_cache(key=cache_key)

        json_response = JSONResponse(
            content={
                "token": cached_data["token"],
                "redirect_url": cached_data["redirect_url"],
            },
            status_code=status.HTTP_200_OK,
        )
        json_response.set_cookie(key="token", value=cached_data["token"])
        return json_response
    except ProxyException:
        raise
    except Exception as e:
        verbose_proxy_logger.exception(
            f"litellm.proxy.proxy_server.login_v3_exchange(): Exception occurred - {e!s}"
        )
        raise ProxyException(
            message=str(e),
            type=ProxyErrorTypes.auth_error,
            param="None",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@app.get("/onboarding/get_token", include_in_schema=False)
async def onboarding(invite_link: str, request: Request):
    """
    - Get the invite link
    - Validate it's still 'valid'
    - Return a short-lived onboarding token
    - Get user from db
    - Pass in user_email if set
    """
    global prisma_client, master_key, general_settings
    from litellm.types.proxy.ui_sso import ReturnedUITokenObject

    if master_key is None:
        raise ProxyException(
            message="Master Key not set for Proxy. Please set Master Key to use Admin UI. Set `LITELLM_MASTER_KEY` in .env or set general_settings:master_key in config.yaml.  https://docs.litellm.ai/docs/proxy/virtual_keys. If set, use `--detailed_debug` to debug issue.",
            type=ProxyErrorTypes.auth_error,
            param="master_key",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    ### VALIDATE INVITE LINK ###
    if prisma_client is None:
        raise HTTPException(
            status_code=500,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    invite_obj = await InvitationLinkRepository(prisma_client).table.find_unique(where={"id": invite_link})
    if invite_obj is None:
        raise HTTPException(status_code=401, detail={"error": "Invitation link does not exist in db."})
    #### CHECK IF EXPIRED
    # Extract the date part from both datetime objects
    utc_now_date = litellm.utils.get_utc_datetime().date()
    expires_at_date = invite_obj.expires_at.date()
    if expires_at_date < utc_now_date:
        raise HTTPException(status_code=401, detail={"error": "Invitation link has expired."})

    #### CHECK IF ALREADY USED
    if invite_obj.is_accepted is True or invite_obj.accepted_at is not None:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invitation link has already been used."},
        )

    ### GET USER OBJECT ###
    user_obj = await UserRepository(prisma_client).table.find_unique(where={"user_id": invite_obj.user_id})

    if user_obj is None:
        raise HTTPException(status_code=401, detail={"error": "User does not exist in db."})

    litellm_dashboard_ui = get_custom_url(str(request.base_url))
    if litellm_dashboard_ui.endswith("/"):
        litellm_dashboard_ui += "ui/onboarding"
    else:
        litellm_dashboard_ui += "/ui/onboarding"
    import jwt

    user_email = user_obj.user_email
    onboarding_token = jwt.encode(  # type: ignore
        {
            "token_type": "litellm_onboarding",
            "invitation_link": invite_link,
            "user_id": user_obj.user_id,
            "exp": litellm.utils.get_utc_datetime() + timedelta(minutes=15),
        },
        master_key,
        algorithm="HS256",
    )
    disabled_non_admin_personal_key_creation = get_disabled_non_admin_personal_key_creation()

    returned_ui_token_object = ReturnedUITokenObject(
        user_id=user_obj.user_id,
        key=onboarding_token,
        user_email=user_obj.user_email,
        user_role=user_obj.user_role,
        login_method="username_password",
        premium_user=premium_user,
        auth_header_name=general_settings.get("litellm_key_header_name", "Authorization"),
        disabled_non_admin_personal_key_creation=disabled_non_admin_personal_key_creation,
        server_root_path=get_server_root_path(),
    )
    jwt_token = jwt.encode(  # type: ignore
        cast(dict, returned_ui_token_object),
        master_key,
        algorithm="HS256",
    )

    litellm_dashboard_ui += f"?token={jwt_token}&user_email={user_email}"
    return {
        "login_url": litellm_dashboard_ui,
        "token": jwt_token,
        "user_email": user_email,
    }


def _get_onboarding_claims_from_request(request: Request) -> dict:
    global master_key, general_settings

    if master_key is None:
        raise ProxyException(
            message="Master Key not set for Proxy. Please set Master Key to use Admin UI. Set `LITELLM_MASTER_KEY` in .env or set general_settings:master_key in config.yaml.  https://docs.litellm.ai/docs/proxy/virtual_keys. If set, use `--detailed_debug` to debug issue.",
            type=ProxyErrorTypes.auth_error,
            param="master_key",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    auth_header_name = general_settings.get("litellm_key_header_name", "Authorization")
    onboarding_auth_header = request.headers.get(auth_header_name)
    if onboarding_auth_header is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "Missing onboarding session for invitation link."},
        )
    onboarding_token = onboarding_auth_header
    if onboarding_token.lower().startswith("bearer "):
        onboarding_token = onboarding_token.split(" ", 1)[1]

    import jwt

    try:
        return jwt.decode(
            onboarding_token,
            master_key,
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid onboarding session for invitation link."},
        )


async def _rollback_onboarding_invite_claim(
    invitation_link: str,
    user_id: str,
) -> None:
    global prisma_client

    if prisma_client is None:
        return

    try:
        await InvitationLinkRepository(prisma_client).table.update_many(
            where={"id": invitation_link, "is_accepted": True},
            data={
                "accepted_at": None,
                "is_accepted": False,
                "updated_at": litellm.utils.get_utc_datetime(),
                "updated_by": user_id,
            },
        )
    except Exception:
        verbose_proxy_logger.exception("Failed to roll back onboarding invitation after session key mint failed.")


async def _generate_onboarding_ui_session_token(user_obj: Any) -> str:
    global master_key, general_settings

    response = await generate_key_helper_fn(
        request_type="key",
        user_role=user_obj.user_role, duration=LITELLM_UI_SESSION_DURATION, key_max_budget=litellm.max_ui_session_budget, models=[], aliases={}, config={}, spend=0, user_id=user_obj.user_id, team_id=UI_TEAM_ID,  # type: ignore
    )
    key = response["token"]  # type: ignore

    import jwt

    from litellm.types.proxy.ui_sso import ReturnedUITokenObject

    disabled_non_admin_personal_key_creation = get_disabled_non_admin_personal_key_creation()
    returned_ui_token_object = ReturnedUITokenObject(
        user_id=user_obj.user_id,
        key=key,
        user_email=user_obj.user_email,
        user_role=user_obj.user_role,
        login_method="username_password",
        premium_user=premium_user,
        auth_header_name=general_settings.get("litellm_key_header_name", "Authorization"),
        disabled_non_admin_personal_key_creation=disabled_non_admin_personal_key_creation,
        server_root_path=get_server_root_path(),
    )
    assert master_key is not None
    return jwt.encode(  # type: ignore
        cast(dict, returned_ui_token_object),
        master_key,
        algorithm="HS256",
    )


@app.post("/onboarding/claim_token", include_in_schema=False)
async def claim_onboarding_link(data: InvitationClaim, request: Request):
    """
    Special route. Allows UI link share user to update their password.

    - Get the invite link
    - Validate it's still 'valid'
    - Check if user within initial session (prevents abuse)
    - Get user from db
    - Update user password

    This route can only update user password.
    """
    global prisma_client, master_key, general_settings
    ### VALIDATE INVITE LINK ###
    if prisma_client is None:
        raise HTTPException(
            status_code=500,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    invite_obj = await InvitationLinkRepository(prisma_client).table.find_unique(where={"id": data.invitation_link})
    if invite_obj is None:
        raise HTTPException(status_code=401, detail={"error": "Invitation link does not exist in db."})
    #### CHECK IF EXPIRED
    # Extract the date part from both datetime objects
    utc_now_date = litellm.utils.get_utc_datetime().date()
    expires_at_date = invite_obj.expires_at.date()
    if expires_at_date < utc_now_date:
        raise HTTPException(status_code=401, detail={"error": "Invitation link has expired."})

    #### CHECK IF ALREADY USED
    if invite_obj.is_accepted is True or invite_obj.accepted_at is not None:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invitation link has already been used."},
        )

    #### CHECK IF VALID USER ID
    if invite_obj.user_id != data.user_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": f"Invalid invitation link. The user id submitted does not match the user id this link is attached to. Got={data.user_id}, Expected={invite_obj.user_id}"
            },
        )

    onboarding_claims = _get_onboarding_claims_from_request(request=request)
    if (
        onboarding_claims.get("token_type") != "litellm_onboarding"
        or onboarding_claims.get("invitation_link") != data.invitation_link
        or onboarding_claims.get("user_id") != data.user_id
    ):
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid onboarding session for invitation link."},
        )

    hashed_pw = hash_password(data.password)
    current_time = litellm.utils.get_utc_datetime()
    async with prisma_client.db.tx() as tx:
        updated_count = await tx.litellm_invitationlink.update_many(
            where={"id": data.invitation_link, "is_accepted": False},
            data={
                "is_accepted": True,
                "updated_at": current_time,
                "updated_by": invite_obj.user_id,  # type: ignore
            },
        )
        if updated_count == 0:
            raise HTTPException(
                status_code=401,
                detail={"error": "Invitation link has already been used."},
            )

        ### UPDATE USER OBJECT ###
        user_obj = await tx.litellm_usertable.update(
            where={"user_id": invite_obj.user_id}, data={"password": hashed_pw}
        )

        if user_obj is None:
            raise HTTPException(status_code=401, detail={"error": "User does not exist in db."})

        #### MARK LINK AS USED
        current_time = litellm.utils.get_utc_datetime()
        await tx.litellm_invitationlink.update(
            where={"id": data.invitation_link},
            data={
                "accepted_at": current_time,
                "updated_at": current_time,
                "updated_by": invite_obj.user_id,  # type: ignore
            },
        )

    if user_obj and hasattr(user_obj, "__dict__"):
        user_obj.__dict__.pop("password", None)

    try:
        jwt_token = await _generate_onboarding_ui_session_token(user_obj=user_obj)
    except Exception as e:
        await _rollback_onboarding_invite_claim(
            invitation_link=data.invitation_link,
            user_id=data.user_id,
        )
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to create onboarding session. Please retry the invitation link."},
        ) from e

    litellm_dashboard_ui = get_custom_url(str(request.base_url))
    if litellm_dashboard_ui.endswith("/"):
        litellm_dashboard_ui += "ui/"
    else:
        litellm_dashboard_ui += "/ui/"
    litellm_dashboard_ui += "?login=success"
    return {
        "login_url": litellm_dashboard_ui,
        "token": jwt_token,
        "user_email": user_obj.user_email,
        "user": user_obj,
    }


@app.get("/get_logo_url", include_in_schema=False)
def get_logo_url():
    """Get the current logo URL from environment.

    Only HTTP(S) URLs are returned — those are intended to be loaded
    directly by the browser from a public/internal CDN. Local file
    paths set via ``UI_LOGO_PATH`` are NOT returned: they are admin-
    only filesystem details, the dashboard falls back to ``/get_image``
    which serves the file only when it is a supported image. Without
    this filter, the unauthenticated endpoint would disclose internal
    hostnames or filesystem paths to any caller.
    """
    logo_path = os.getenv("UI_LOGO_PATH", "")
    if logo_path.startswith(("http://", "https://")):
        return {"logo_url": logo_path}
    return {"logo_url": ""}


@app.get("/get_image", include_in_schema=False)
async def get_image():
    """Get logo to show on admin UI"""

    # get current_dir
    current_dir = os.path.dirname(os.path.abspath(__file__))
    default_site_logo = os.path.join(current_dir, "logo.jpg")

    is_non_root = os.getenv("LITELLM_NON_ROOT", "").lower() == "true"

    # Determine assets directory
    # Priority: LITELLM_ASSETS_PATH env var > default based on is_non_root
    default_assets_dir = "/var/lib/litellm/assets" if is_non_root else current_dir
    assets_dir = os.getenv("LITELLM_ASSETS_PATH", default_assets_dir)

    # Try to create assets_dir if it doesn't exist (simple try/except approach)
    if not os.path.exists(assets_dir):
        try:
            os.makedirs(assets_dir, exist_ok=True)
            verbose_proxy_logger.debug(f"Created assets directory at {assets_dir}")
        except (PermissionError, OSError) as e:
            verbose_proxy_logger.warning(
                f"Cannot create assets directory at {assets_dir}: {e}. "
                f"Logo caching may not work. Using current directory for assets."
            )
            assets_dir = current_dir

    # Determine default logo path
    default_logo = os.path.join(assets_dir, "logo.jpg") if assets_dir != current_dir else default_site_logo
    if assets_dir != current_dir and not os.path.exists(default_logo):
        default_logo = default_site_logo

    logo_path = os.getenv("UI_LOGO_PATH", default_logo)
    verbose_proxy_logger.debug("Reading logo from path: %s", logo_path)

    from litellm.proxy.common_utils.static_asset_utils import (
        resolve_validated_local_image_path,
    )

    if logo_path != default_logo and not logo_path.startswith(("http://", "https://")):
        safe_logo = resolve_validated_local_image_path(logo_path)
        if safe_logo is not None:
            safe_logo_path, media_type = safe_logo
            return FileResponse(safe_logo_path, media_type=media_type)
        verbose_proxy_logger.warning(
            "UI_LOGO_PATH %r is not a supported image file or does not exist, falling back to default logo",
            logo_path,
        )
        logo_path = default_logo

    # Remote logo URLs are loaded by the browser. The proxy should not fetch
    # arbitrary admin-configured URLs server-side.
    if logo_path.startswith(("http://", "https://")):
        return RedirectResponse(url=logo_path)

    # Default logo (resolved from the bundled asset, not user-controlled).
    safe_logo = resolve_validated_local_image_path(logo_path)
    if safe_logo is not None:
        safe_logo_path, media_type = safe_logo
        return FileResponse(safe_logo_path, media_type=media_type)
    return FileResponse(default_site_logo, media_type="image/jpeg")


@app.get("/get_favicon", include_in_schema=False)
async def get_favicon():
    """Get custom favicon for the admin UI."""
    from litellm.proxy.common_utils.static_asset_utils import (
        resolve_validated_local_image_path,
    )

    current_dir = os.path.dirname(os.path.abspath(__file__))
    default_favicon = os.path.join(current_dir, "_experimental", "out", "favicon.ico")

    favicon_url = os.getenv("LITELLM_FAVICON_URL", "")

    if not favicon_url:
        if os.path.exists(default_favicon):
            return FileResponse(default_favicon, media_type="image/x-icon")
        raise HTTPException(status_code=404, detail="Default favicon not found")

    if favicon_url.startswith(("http://", "https://")):
        return RedirectResponse(url=favicon_url)
    else:
        safe_favicon = resolve_validated_local_image_path(favicon_url)
        if safe_favicon is not None:
            safe_favicon_path, media_type = safe_favicon
            return FileResponse(safe_favicon_path, media_type=media_type)
        verbose_proxy_logger.warning(
            "LITELLM_FAVICON_URL %r is not a supported image file or does not exist, falling back to default favicon",
            favicon_url,
        )
        if os.path.exists(default_favicon):
            return FileResponse(default_favicon, media_type="image/x-icon")
        raise HTTPException(status_code=404, detail="Favicon not found")


#### INVITATION MANAGEMENT ####


@router.post(
    "/invitation/new",
    tags=["Invite Links"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=InvitationModel,
    include_in_schema=False,
)
async def new_invitation(data: InvitationNew, user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)):
    """
    Allow admin to create invite links, to onboard new users to Admin UI.

    ```
    curl -X POST 'http://localhost:4000/invitation/new' \
        -H 'Content-Type: application/json' \
        -d '{
            "user_id": "1234" // 👈 id of user in 'LiteLLM_UserTable'
        }'
    ```
    """
    try:
        from litellm.proxy.management_helpers.user_invitation import (
            create_invitation_for_user,
        )

        global prisma_client

        if prisma_client is None:
            raise HTTPException(
                status_code=400,
                detail={"error": CommonProxyErrors.db_not_connected_error.value},
            )

        # Allow proxy admins and org/team admins (admin status from DB via get_user_object)
        has_access = user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN or await _user_has_admin_privileges(
            user_api_key_dict=user_api_key_dict,
            prisma_client=prisma_client,
            user_api_key_cache=user_api_key_cache,
            proxy_logging_obj=proxy_logging_obj,
        )
        if not has_access:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"{CommonProxyErrors.not_allowed_access.value}, your role={user_api_key_dict.user_role}"
                },
            )

        # Org/team admins can only invite users within their org/team
        if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
            can_invite = await admin_can_invite_user(
                target_user_id=data.user_id,
                user_api_key_dict=user_api_key_dict,
                prisma_client=prisma_client,
                user_api_key_cache=user_api_key_cache,
                proxy_logging_obj=proxy_logging_obj,
            )
            if not can_invite:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "You can only create invitations for users in your organization or team."},
                )

        response = await create_invitation_for_user(
            data=data,
            user_api_key_dict=user_api_key_dict,
        )
        return response
    except Exception as e:
        raise handle_exception_on_proxy(e)


@router.get(
    "/invitation/info",
    tags=["Invite Links"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=InvitationModel,
    include_in_schema=False,
)
async def invitation_info(invitation_id: str, user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)):
    """
    Allow admin to create invite links, to onboard new users to Admin UI.

    ```
    curl -X POST 'http://localhost:4000/invitation/new' \
        -H 'Content-Type: application/json' \
        -d '{
            "user_id": "1234" // 👈 id of user in 'LiteLLM_UserTable'
        }'
    ```
    """
    global prisma_client

    if prisma_client is None:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    if not _user_has_admin_view(user_api_key_dict):
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"{CommonProxyErrors.not_allowed_access.value}, your role={user_api_key_dict.user_role}"
            },
        )

    response = await InvitationLinkRepository(prisma_client).table.find_unique(where={"id": invitation_id})

    if response is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invitation id does not exist in the database."},
        )
    return response


@router.post(
    "/invitation/update",
    tags=["Invite Links"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=InvitationModel,
    include_in_schema=False,
)
async def invitation_update(
    data: InvitationUpdate,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Update when invitation is accepted

    ```
    curl -X POST 'http://localhost:4000/invitation/update' \
        -H 'Content-Type: application/json' \
        -d '{
            "invitation_id": "1234" // 👈 id of invitation in 'LiteLLM_InvitationTable'
            "is_accepted": True // when invitation is accepted
        }'
    ```
    """
    global prisma_client

    if prisma_client is None:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    if user_api_key_dict.user_id is None:
        raise HTTPException(
            status_code=500,
            detail={"error": f"Unable to identify user id. Received={user_api_key_dict.user_id}"},
        )

    current_time = litellm.utils.get_utc_datetime()
    response = await InvitationLinkRepository(prisma_client).table.update(
        where={"id": data.invitation_id},
        data={
            "id": data.invitation_id,
            "is_accepted": data.is_accepted,
            "accepted_at": current_time,
            "updated_at": current_time,
            "updated_by": user_api_key_dict.user_id,  # type: ignore
        },
    )

    if response is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invitation id does not exist in the database."},
        )
    return response


@router.post(
    "/invitation/delete",
    tags=["Invite Links"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=InvitationModel,
    include_in_schema=False,
)
async def invitation_delete(
    data: InvitationDelete,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Delete invitation link

    ```
    curl -X POST 'http://localhost:4000/invitation/delete' \
        -H 'Content-Type: application/json' \
        -d '{
            "invitation_id": "1234" // 👈 id of invitation in 'LiteLLM_InvitationTable'
        }'
    ```
    """
    global prisma_client

    if prisma_client is None:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    # Proxy admins can delete any invitation; org admins only their own
    is_proxy_admin = user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN
    is_other_admin = await _user_has_admin_privileges(
        user_api_key_dict=user_api_key_dict,
        prisma_client=prisma_client,
        user_api_key_cache=user_api_key_cache,
        proxy_logging_obj=proxy_logging_obj,
    )

    if not is_proxy_admin and not is_other_admin:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"{CommonProxyErrors.not_allowed_access.value}, your role={user_api_key_dict.user_role}"
            },
        )

    # Org admins can only delete invitations they created
    if is_other_admin and not is_proxy_admin:
        invitation = await InvitationLinkRepository(prisma_client).table.find_unique(where={"id": data.invitation_id})
        if invitation is None:
            raise HTTPException(
                status_code=400,
                detail={"error": "Invitation id does not exist in the database."},
            )
        if invitation.created_by != user_api_key_dict.user_id:
            raise HTTPException(
                status_code=403,
                detail={"error": "Organization admins can only delete invitations they created."},
            )

    response = await InvitationLinkRepository(prisma_client).table.delete(where={"id": data.invitation_id})

    if response is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invitation id does not exist in the database."},
        )
    return response


#### CONFIG MANAGEMENT ####
@router.post(
    "/config/update",
    tags=["config.yaml"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def update_config(
    config_info: ConfigYAML,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    For Admin UI - allows admin to update config via UI.

    Writes only the sections present in the request body to LiteLLM_Config rows
    (one row per top-level section). Sections the caller did not send are left
    untouched — this endpoint never persists pre-existing YAML values to DB as
    a side effect of an unrelated update.
    """
    global llm_router, llm_model_list, general_settings, proxy_config, proxy_logging_obj, master_key, prisma_client
    try:
        if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
            raise HTTPException(status_code=403, detail="Only proxy admins can update config")

        if prisma_client is None:
            raise Exception("No DB Connected")

        async def _read_section(param_name: str) -> dict:
            row = await ConfigRepository(prisma_client).table.find_first(where={"param_name": param_name})
            if row is None or row.param_value is None:
                return {}
            return dict(row.param_value)

        async def _upsert_section(param_name: str, value: dict) -> None:
            serialized = json.dumps(value)
            await ConfigRepository(prisma_client).table.upsert(
                where={"param_name": param_name},
                data={
                    "create": {"param_name": param_name, "param_value": serialized},
                    "update": {"param_value": serialized},
                },
            )
            # invalidate the DualCache entry so the next reader (this process
            # or any other proxy in the cluster) goes to DB.
            await invalidate_config_param(param_name)

        # general_settings: merge per-key, with the alert_to_webhook_url side
        # effect of auto-enabling slack alerting.
        if config_info.general_settings is not None:
            existing = await _read_section("general_settings")
            before_general_settings = copy.deepcopy(existing)
            updates = config_info.general_settings.dict(exclude_none=True)
            for k, v in updates.items():
                if k == "alert_to_webhook_url":
                    if "alerting" not in existing:
                        existing["alerting"] = ["slack"]
                    elif isinstance(existing["alerting"], list) and "slack" not in existing["alerting"]:
                        existing["alerting"].append("slack")
                existing[k] = v
            await _upsert_section("general_settings", existing)
            asyncio.create_task(
                create_config_audit_log(
                    "general_settings", "updated", before_general_settings, existing, user_api_key_dict
                )
            )

        # environment_variables: idempotently encrypt the request values
        # (plaintext on first write, OR ciphertext the UI read back via
        # /get/config/callbacks and re-submitted on save), then merge into
        # existing. Only the sent keys are re-written; untouched keys keep
        # their stored ciphertext byte-for-byte.
        if config_info.environment_variables is not None:
            existing = await _read_section("environment_variables")
            before_environment_variables = copy.deepcopy(existing)
            existing.update(
                proxy_config._encrypt_env_variables_for_db(environment_variables=config_info.environment_variables)
            )
            await _upsert_section("environment_variables", existing)
            asyncio.create_task(
                create_config_audit_log(
                    "environment_variables", "updated", before_environment_variables, existing, user_api_key_dict
                )
            )

        # litellm_settings: merge existing + request, request wins (matching
        # router_settings semantics — the caller's value for any given key is
        # what gets persisted). success_callback is special-cased: it is
        # always normalized + deduped, and unioned with any existing list,
        # because callbacks are additive (callers send the new entry, not
        # the full set). Normalizing on every write — not only when an
        # existing entry is present — keeps the DB free of mixed-case
        # entries that delete_callback (lowercase lookup) cannot find.
        if config_info.litellm_settings is not None:
            existing = await _read_section("litellm_settings")
            before_litellm_settings = copy.deepcopy(existing)
            updated_litellm_settings = dict(config_info.litellm_settings)

            incoming_cb = updated_litellm_settings.get("success_callback")
            if isinstance(incoming_cb, list):
                updated_litellm_settings["success_callback"] = normalize_callback_names(incoming_cb)

            merged = {**existing, **updated_litellm_settings}

            incoming_cb = updated_litellm_settings.get("success_callback")
            existing_cb = existing.get("success_callback")
            if isinstance(incoming_cb, list):
                if isinstance(existing_cb, list):
                    # Normalize the existing list too — a row written by a
                    # different code path may still hold mixed-case names,
                    # which would otherwise dedup-miss against the lowercase
                    # incoming entries.
                    merged["success_callback"] = list(set(normalize_callback_names(existing_cb) + incoming_cb))
                else:
                    merged["success_callback"] = list(set(incoming_cb))

            await _upsert_section("litellm_settings", merged)
            asyncio.create_task(
                create_config_audit_log(
                    "litellm_settings", "updated", before_litellm_settings, merged, user_api_key_dict
                )
            )

        # router_settings: merge existing + request, request wins.
        if config_info.router_settings is not None:
            existing = await _read_section("router_settings")
            before_router_settings = copy.deepcopy(existing)
            updates = config_info.router_settings.dict(exclude_none=True)
            new_router_settings = {**existing, **updates}
            await _upsert_section("router_settings", new_router_settings)
            asyncio.create_task(
                create_config_audit_log(
                    "router_settings", "updated", before_router_settings, new_router_settings, user_api_key_dict
                )
            )

        await proxy_config.add_deployment(prisma_client=prisma_client, proxy_logging_obj=proxy_logging_obj)

        return {"message": "Config updated successfully"}
    except Exception as e:
        verbose_proxy_logger.error(f"litellm.proxy.proxy_server.update_config(): Exception occured - {e!s}")
        verbose_proxy_logger.debug(traceback.format_exc())
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "detail", f"Authentication Error({e!s})"),
                type=ProxyErrorTypes.auth_error,
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        elif isinstance(e, ProxyException):
            raise e
        raise ProxyException(
            message="Authentication Error, " + str(e),
            type=ProxyErrorTypes.auth_error,
            param=getattr(e, "param", "None"),
            code=status.HTTP_400_BAD_REQUEST,
        )


### CONFIG GENERAL SETTINGS
"""
- Update config settings
- Get config settings

Keep it more precise, to prevent overwrite other values unintentially
"""

_PLUGIN_KEY_REDACTED = "***"


def _preserve_redacted_plugin_keys(incoming: object, existing: object) -> object:
    """Restore real plugin_key values the client never sees.

    /config/field/info redacts every plugin_key to ``"***"``, so an admin
    editing a plugin posts that placeholder (or a blank, when the UI clears the
    field) straight back. Treat a blank or redacted plugin_key as "keep the
    stored credential" by sourcing it from the existing config; only a real,
    non-redacted value replaces it, and a blank with no stored key drops the
    field entirely instead of persisting the placeholder.
    """
    if not isinstance(incoming, list):
        return incoming

    stored_keys = {
        p["name"]: p["plugin_key"]
        for p in (existing if isinstance(existing, list) else [])
        if isinstance(p, dict) and p.get("name") and p.get("plugin_key")
    }

    def resolve(plugin: object) -> object:
        if not isinstance(plugin, dict):
            return plugin
        key = plugin.get("plugin_key")
        if key not in (None, "", _PLUGIN_KEY_REDACTED):
            return plugin
        name = plugin.get("name")
        if name in stored_keys:
            return {**plugin, "plugin_key": stored_keys[name]}
        return {k: v for k, v in plugin.items() if k != "plugin_key"}

    return [resolve(p) for p in incoming]


@router.post(
    "/config/field/update",
    tags=["config.yaml"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def update_config_general_settings(
    data: ConfigFieldUpdate,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Update a specific field in litellm general settings
    """
    global prisma_client
    ## VALIDATION ##
    """
    - Check if prisma_client is None
    - Check if user allowed to call this endpoint (admin-only)
    - Check if param in general settings
    - Check if config value is valid type
    """

    if prisma_client is None:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.not_allowed_access.value},
        )

    if data.field_name in _GENERAL_SETTINGS_UI_LITELLM_FIELDS:
        return await _persist_general_settings_ui_litellm_field(data.field_name, data.field_value, user_api_key_dict)

    if data.field_name not in ConfigGeneralSettings.model_fields:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Invalid field={data.field_name} passed in."},
        )

    try:
        ConfigGeneralSettings(**{data.field_name: data.field_value})
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Invalid type of field value={type(data.field_value)} passed in."
            },
        )

    ## get general settings from db
    db_general_settings = await ConfigRepository(prisma_client).table.find_first(
        where={"param_name": "general_settings"}
    )
    ### update value

    if db_general_settings is None or db_general_settings.param_value is None:
        general_settings = {}
    else:
        general_settings = dict(db_general_settings.param_value)

    before_general_settings = copy.deepcopy(general_settings)

    ## update db

    field_value = data.field_value
    if data.field_name == "plugins":
        field_value = _preserve_redacted_plugin_keys(field_value, general_settings.get("plugins"))

    general_settings[data.field_name] = field_value

    response = await ConfigRepository(prisma_client).table.upsert(
        where={"param_name": "general_settings"},
        data={
            "create": {
                "param_name": "general_settings",
                "param_value": json.dumps(general_settings),
            },  # type: ignore
            "update": {"param_value": json.dumps(general_settings)},  # type: ignore
        },
    )
    await invalidate_config_param("general_settings")
    asyncio.create_task(
        create_config_audit_log(
            "general_settings", "updated", before_general_settings, general_settings, user_api_key_dict
        )
    )

    if data.field_name == "plugins":
        register_plugins_from_config(general_settings)
    _apply_ssrf_general_settings(general_settings)

    return response


def _is_secret_general_setting_field(field_name: str) -> bool:
    return field_name in _EXTRA_SECRET_GENERAL_SETTINGS_FIELDS or SENSITIVE_DATA_MASKER.is_sensitive_key(field_name)


# Matches the cap on _redact_sensitive_litellm_params (the closest analog in the
# proxy). Past this depth we fail closed by returning "REDACTED" for the whole
# subtree rather than recursing further — better to over-redact a pathological
# config than to silently return a deeply-nested credential verbatim
_REDACT_SECRET_MAX_DEPTH = 10


def _redact_secret_values_in_obj(value: JsonValue, depth: int = 0) -> JsonValue:
    """Recursively redact secret leaves inside a structured field so a nested
    credential (e.g. aws_web_identity_token under database_args) is never
    returned to a non-admin, while non-secret siblings stay visible. At
    _REDACT_SECRET_MAX_DEPTH the whole subtree is replaced with "REDACTED"
    so depth-overrun fails closed."""
    if depth >= _REDACT_SECRET_MAX_DEPTH:
        return "REDACTED"
    if isinstance(value, dict):
        return {
            key: ("REDACTED" if _is_secret_general_setting_field(key) else _redact_secret_values_in_obj(sub, depth + 1))
            for key, sub in value.items()
        }
    if isinstance(value, list):
        return [_redact_secret_values_in_obj(item, depth + 1) for item in value]
    return value


def _redact_config_param_value_for_logging(param_name: str | None, param_value: JsonValue) -> JsonValue:
    if param_name == "environment_variables" and isinstance(param_value, dict):
        return {key: "REDACTED" for key in param_value}
    if isinstance(param_value, (dict, list)):
        return _redact_secret_values_in_obj(param_value)
    return param_value


def _redact_general_setting_value(field_name: str, value: JsonValue, is_full_admin: bool) -> JsonValue:
    if is_full_admin:
        return value
    if _is_secret_general_setting_field(field_name):
        return "REDACTED"
    if isinstance(value, (dict, list)):
        return _redact_secret_values_in_obj(value)
    return value


def _dump_redacted_config(value: JsonValue | None, *, redact_all_values: bool = False) -> str | None:
    # `default=str` matches the sibling audit-log serializers in
    # team_endpoints.py and the LiteLLM_AuditLogs validator, so a YAML-loaded
    # value with a non-JSON-native leaf (datetime, custom object) cannot turn
    # an audit write into a 500.
    if value is None:
        return None
    if redact_all_values and isinstance(value, dict):
        return json.dumps({key: "REDACTED" for key in value}, default=str)
    return json.dumps(_redact_secret_values_in_obj(value), default=str)


async def create_config_audit_log(
    param_name: str,
    action: AUDIT_ACTIONS,
    before_value: JsonValue | None,
    after_value: JsonValue | None,
    user_api_key_dict: UserAPIKeyAuth,
    table_name: LitellmTableNames = LitellmTableNames.CONFIG_TABLE_NAME,
) -> None:
    """Record a system-wide settings change in LiteLLM_AuditLog.

    Secret leaves are redacted before the row is written. environment_variables
    hold arbitrary credentials under non-secret-looking uppercase keys (e.g.
    DATABASE_URL), so every value in that section is redacted rather than
    relying on key-name matching; other sections reuse the same matcher
    /config/field/info applies for non-admins.
    """
    redact_all_values = param_name == "environment_variables"
    await create_object_audit_log(
        object_id=param_name,
        action=action,
        table_name=table_name,
        before_value=_dump_redacted_config(before_value, redact_all_values=redact_all_values),
        after_value=_dump_redacted_config(after_value, redact_all_values=redact_all_values),
        user_api_key_dict=user_api_key_dict,
        litellm_changed_by=None,
        litellm_proxy_admin_name=LITELLM_PROXY_ADMIN_NAME,
    )


_EXTRA_SECRET_CALLBACK_ENV_VARS = frozenset(
    {
        "GALILEO_USERNAME",
        "GENERIC_LOGGER_HEADERS",
        "OTEL_HEADERS",
        "SLACK_WEBHOOK_URL",
        "SMTP_USERNAME",
    }
)


def _redact_callback_env_vars(env_vars: dict[str, str | None]) -> dict[str, str | None]:
    """Return a copy of ``env_vars`` with values for keys classified as
    sensitive by ``is_sensitive_callback_key`` replaced with ``"REDACTED"``.
    ``None`` values pass through unchanged.
    """
    return {
        key: (
            "REDACTED"
            if value is not None and is_sensitive_callback_key(key, extra=_EXTRA_SECRET_CALLBACK_ENV_VARS)
            else value
        )
        for key, value in env_vars.items()
    }


def _apply_callback_role_gate(entries: list, is_full_admin: bool) -> list:
    if is_full_admin:
        return entries
    return [{**entry, "variables": _redact_callback_env_vars(entry.get("variables") or {})} for entry in entries]


def _apply_alerting_env_role_gate(env_vars: dict, is_full_admin: bool) -> dict:
    if is_full_admin:
        return mask_sensitive_keys(env_vars, _ALERTING_SENSITIVE_VARS)
    return _redact_callback_env_vars(env_vars)


def _apply_webhook_role_gate(webhook_map, is_full_admin: bool):
    if is_full_admin or not isinstance(webhook_map, dict):
        return webhook_map
    return {alert_type: "REDACTED" for alert_type in webhook_map}


@router.get(
    "/config/field/info",
    tags=["config.yaml"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=ConfigFieldInfo,
    include_in_schema=False,
)
async def get_config_general_settings(
    field_name: str,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    global prisma_client

    ## VALIDATION ##
    """
    - Check if prisma_client is None
    - Check if user allowed to call this endpoint (admin-only)
    - Check if param in general settings
    """
    if prisma_client is None:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    if not _user_has_admin_view(user_api_key_dict):
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.not_allowed_access.value},
        )

    if field_name not in ConfigGeneralSettings.model_fields:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Invalid field={field_name} passed in."},
        )

    ## get general settings from db
    db_general_settings = await ConfigRepository(prisma_client).table.find_first(
        where={"param_name": "general_settings"}
    )
    ### pop the value

    if db_general_settings is None or db_general_settings.param_value is None:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Field name={field_name} not in DB"},
        )
    else:
        general_settings = dict(db_general_settings.param_value)

        if field_name in general_settings:
            field_value = _redact_general_setting_value(
                field_name,
                general_settings[field_name],
                user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN,
            )
            if field_name == "plugins" and isinstance(field_value, list):
                field_value = [
                    ({k: ("***" if k == "plugin_key" else v) for k, v in p.items()} if isinstance(p, dict) else p)
                    for p in field_value
                ]
            return ConfigFieldInfo(field_name=field_name, field_value=field_value)
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": f"Field name={field_name} not in DB"},
            )


GeneralSettingsUILiteLLMValue = Union[float, bool, str, None]


class GeneralSettingsUILiteLLMFieldSpec(TypedDict):
    type: Literal["Float", "Dollar", "Boolean", "Select"]
    description: str
    options: NotRequired[tuple[str, ...]]
    tab: NotRequired[str]  # Admin UI sub-tab this field renders under; None groups it with the rest
    default: NotRequired[float]  # reset/clear restores this instead of None; fields whose None means fail-open set it


_GENERAL_SETTINGS_UI_LITELLM_FIELDS: dict[str, GeneralSettingsUILiteLLMFieldSpec] = {
    "budget_exceeded_throttle_percentage": {
        "type": "Float",
        "description": (
            "Fraction (0, 1] of a key's configured TPM/RPM that an over-budget key with "
            "'Throttle on budget exceeded' enabled keeps serving at. Leave empty to hard-block "
            "over-budget keys."
        ),
    },
    "enable_anthropic_prompt_caching": {
        "type": "Boolean",
        "tab": "prompt_caching",
        "description": (
            "Auto-adds cache_control to the system prompt and trailing turn for supported Anthropic "
            "and Bedrock Claude models. The cache is shared across callers on the same upstream credentials."
        ),
    },
    "anthropic_prompt_caching_ttl": {
        "type": "Select",
        "options": ("5m", "1h"),
        "tab": "prompt_caching",
        "description": "Empty uses Anthropic's 5m default. 1h suits long sessions but doubles the cache write cost.",
    },
    "max_ui_session_budget": {
        "type": "Dollar",
        "default": 1.0,
        "description": (
            "USD spend cap for each dashboard login session; covers LLM calls made from the dashboard "
            "such as the playground and auto router Test Connection. Each login starts a fresh session "
            "with this budget. Clearing restores the $1 default."
        ),
    },
}


def _general_settings_ui_litellm_default(
    spec: GeneralSettingsUILiteLLMFieldSpec,
) -> GeneralSettingsUILiteLLMValue:
    """The value a field falls back to when it is cleared or reset."""
    if "default" in spec:
        return spec["default"]
    return False if spec["type"] == "Boolean" else None


def _validate_general_settings_ui_litellm_value(field_name: str, value: Any) -> GeneralSettingsUILiteLLMValue:
    spec = _GENERAL_SETTINGS_UI_LITELLM_FIELDS[field_name]
    field_type = spec["type"]
    if value is None or value == "":
        return _general_settings_ui_litellm_default(spec)
    match field_type:
        case "Boolean":
            if not isinstance(value, bool):
                raise HTTPException(
                    status_code=400,
                    detail={"error": f"{field_name} must be true or false"},
                )
            return value
        case "Select":
            options = spec.get("options", ())
            if value not in options:
                raise HTTPException(
                    status_code=400,
                    detail={"error": f"{field_name} must be one of: {', '.join(options)}, or empty"},
                )
            return cast(str, value)  # cast-ok: membership in options proves it is one of the option strings
        case "Float":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not (0 < float(value) <= 1):
                raise HTTPException(
                    status_code=400,
                    detail={"error": f"{field_name} must be a number in (0, 1] or empty"},
                )
            return float(value)
        case "Dollar":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0:
                raise HTTPException(
                    status_code=400,
                    detail={"error": f"{field_name} must be a positive dollar amount or empty"},
                )
            return float(value)
        case _:
            assert_never(field_type)


async def _persist_general_settings_ui_litellm_field(
    field_name: str, value: Any, user_api_key_dict: UserAPIKeyAuth
) -> dict:
    validated = _validate_general_settings_ui_litellm_value(field_name, value)
    config = await proxy_config.get_config()
    before_value = config.get("litellm_settings", {}).get(field_name)
    setattr(litellm, field_name, validated)
    if "litellm_settings" not in config:
        config["litellm_settings"] = {}
    config["litellm_settings"][field_name] = validated
    await proxy_config.save_config(new_config=config)
    asyncio.create_task(create_config_audit_log(field_name, "updated", before_value, validated, user_api_key_dict))
    return {"message": f"Field {field_name} updated", "status": "success"}


async def _reset_general_settings_ui_litellm_field(field_name: str, user_api_key_dict: UserAPIKeyAuth) -> dict:
    config = await proxy_config.get_config()
    before_value = config.get("litellm_settings", {}).get(field_name)
    default_value = _general_settings_ui_litellm_default(_GENERAL_SETTINGS_UI_LITELLM_FIELDS[field_name])
    setattr(litellm, field_name, default_value)
    if "litellm_settings" in config:
        config["litellm_settings"].pop(field_name, None)
    await proxy_config.save_config(new_config=config)
    asyncio.create_task(create_config_audit_log(field_name, "deleted", before_value, default_value, user_api_key_dict))
    return {"message": f"Field {field_name} reset", "status": "success"}


@router.get(
    "/config/list",
    tags=["config.yaml"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def get_config_list(
    config_type: Literal["general_settings"],
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> list[ConfigList]:
    """
    List the available fields + current values for a given type of setting (currently just 'general_settings'user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),)
    """
    global prisma_client, general_settings

    ## VALIDATION ##
    """
    - Check if prisma_client is None
    - Check if user allowed to call this endpoint (admin-only)
    - Check if param in general settings
    """
    if prisma_client is None:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    if not _user_has_admin_view(user_api_key_dict):
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"{CommonProxyErrors.not_allowed_access.value}, your role={user_api_key_dict.user_role}"
            },
        )

    is_full_admin = user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN

    ## get general settings from db
    db_general_settings = await ConfigRepository(prisma_client).table.find_first(
        where={"param_name": "general_settings"}
    )

    if db_general_settings is not None and db_general_settings.param_value is not None:
        db_general_settings_dict = dict(db_general_settings.param_value)
    else:
        db_general_settings_dict = {}

    allowed_args = {
        "max_parallel_requests": {"type": "Integer"},
        "global_max_parallel_requests": {"type": "Integer"},
        "max_request_size_mb": {"type": "Integer"},
        "max_response_size_mb": {"type": "Integer"},
        "proxy_config_reload_interval_seconds": {"type": "Integer"},
        "pass_through_endpoints": {"type": "PydanticModel"},
        "store_model_in_db": {"type": "Boolean"},
        "store_prompts_in_spend_logs": {"type": "Boolean"},
        "maximum_spend_logs_retention_period": {"type": "String"},
        "mcp_internal_ip_ranges": {"type": "List"},
        "mcp_trusted_proxy_ranges": {"type": "List"},
        "mcp_xff_num_trusted_hops": {"type": "Integer"},
        "always_include_stream_usage": {"type": "Boolean"},
        "forward_client_headers_to_llm_api": {"type": "Boolean"},
        "mcp_required_fields": {"type": "List"},
        "cancel_on_disconnect": {"type": "Boolean"},
        "skip_user_budget_on_team_key": {"type": "Boolean"},
        "disable_auto_add_proxy_admin_to_teams": {"type": "Boolean"},
    }

    return_val = []

    for field_name, field_info in ConfigGeneralSettings.model_fields.items():
        if field_name in allowed_args:
            ## HANDLE TYPED DICT

            typed_dict_type = allowed_args[field_name]["type"]

            if typed_dict_type == "PydanticModel":
                if field_name == "pass_through_endpoints":
                    pydantic_class_list = [PassThroughGenericEndpoint]
                else:
                    pydantic_class_list = []

                for pydantic_class in pydantic_class_list:
                    # Get type hints from the TypedDict to create FieldDetail objects
                    nested_fields = [
                        FieldDetail(
                            field_name=sub_field,
                            field_type=sub_field_type.__name__,
                            field_description="",  # Add custom logic if descriptions are available
                            field_default_value=_redact_general_setting_value(
                                sub_field,
                                general_settings.get(sub_field, None),
                                is_full_admin,
                            ),
                            stored_in_db=None,
                        )
                        for sub_field, sub_field_type in pydantic_class.__annotations__.items()
                    ]

                    idx = 0
                    for (
                        sub_field,
                        sub_field_info,
                    ) in pydantic_class.model_fields.items():
                        if hasattr(sub_field_info, "description") and sub_field_info.description is not None:
                            nested_fields[idx].field_description = sub_field_info.description
                        idx += 1

                    _stored_in_db = None
                    if field_name in db_general_settings_dict:
                        _stored_in_db = True
                    elif field_name in general_settings:
                        _stored_in_db = False

                    _response_obj = ConfigList(
                        field_name=field_name,
                        field_type=allowed_args[field_name]["type"],
                        field_description=field_info.description or "",
                        field_value=_redact_general_setting_value(
                            field_name,
                            general_settings.get(field_name, None),
                            is_full_admin,
                        ),
                        stored_in_db=_stored_in_db,
                        field_default_value=field_info.default,
                        nested_fields=nested_fields,
                    )
                    return_val.append(_response_obj)

            else:
                nested_fields = None

                _stored_in_db = None
                if field_name in db_general_settings_dict:
                    _stored_in_db = True
                elif field_name in general_settings:
                    _stored_in_db = False

                _field_value = general_settings.get(field_name, None)
                if _field_value is None and field_name in db_general_settings_dict:
                    _field_value = db_general_settings_dict[field_name]

                _response_obj = ConfigList(
                    field_name=field_name,
                    field_type=allowed_args[field_name]["type"],
                    field_description=field_info.description or "",
                    field_value=_redact_general_setting_value(field_name, _field_value, is_full_admin),
                    stored_in_db=_stored_in_db,
                    field_default_value=field_info.default,
                    nested_fields=nested_fields,
                )
                return_val.append(_response_obj)

    db_litellm_settings_row = await ConfigRepository(prisma_client).table.find_first(
        where={"param_name": "litellm_settings"}
    )
    db_litellm_settings: dict = (
        dict(db_litellm_settings_row.param_value)
        if db_litellm_settings_row is not None and db_litellm_settings_row.param_value is not None
        else {}
    )
    for litellm_field_name, spec in _GENERAL_SETTINGS_UI_LITELLM_FIELDS.items():
        current_value: GeneralSettingsUILiteLLMValue = getattr(litellm, litellm_field_name, None)
        default_value = _general_settings_ui_litellm_default(spec)
        stored_in_db_litellm: bool | None
        if litellm_field_name in db_litellm_settings:
            stored_in_db_litellm = True
        elif current_value != default_value:
            stored_in_db_litellm = False
        else:
            stored_in_db_litellm = None
        return_val.append(
            ConfigList(
                field_name=litellm_field_name,
                field_type=spec["type"],
                field_description=spec["description"],
                field_value=current_value,
                stored_in_db=stored_in_db_litellm,
                field_default_value=default_value,
                field_options=list(spec.get("options", ())) or None,
                field_tab=spec.get("tab"),
                nested_fields=None,
            )
        )

    return return_val


@router.post(
    "/config/field/delete",
    tags=["config.yaml"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def delete_config_general_settings(
    data: ConfigFieldDelete,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Delete the db value of this field in litellm general settings. Resets it to it's initial default value on litellm.
    """
    global prisma_client
    ## VALIDATION ##
    """
    - Check if prisma_client is None
    - Check if user allowed to call this endpoint (admin-only)
    - Check if param in general settings
    """
    if prisma_client is None:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"{CommonProxyErrors.not_allowed_access.value}, your role={user_api_key_dict.user_role}"
            },
        )

    if data.field_name in _GENERAL_SETTINGS_UI_LITELLM_FIELDS:
        return await _reset_general_settings_ui_litellm_field(data.field_name, user_api_key_dict)

    if data.field_name not in ConfigGeneralSettings.model_fields:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Invalid field={data.field_name} passed in."},
        )

    ## get general settings from db
    db_general_settings = await ConfigRepository(prisma_client).table.find_first(
        where={"param_name": "general_settings"}
    )
    ### pop the value

    if db_general_settings is None or db_general_settings.param_value is None:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Field name={data.field_name} not in config"},
        )
    else:
        general_settings = dict(db_general_settings.param_value)

    before_general_settings = copy.deepcopy(general_settings)

    ## update db

    general_settings.pop(data.field_name, None)

    response = await ConfigRepository(prisma_client).table.upsert(
        where={"param_name": "general_settings"},
        data={
            "create": {
                "param_name": "general_settings",
                "param_value": json.dumps(general_settings),
            },  # type: ignore
            "update": {"param_value": json.dumps(general_settings)},  # type: ignore
        },
    )
    await invalidate_config_param("general_settings")
    asyncio.create_task(
        create_config_audit_log(
            "general_settings", "deleted", before_general_settings, general_settings, user_api_key_dict
        )
    )

    return response


@router.post(
    "/config/callback/delete",
    tags=["config.yaml"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def delete_callback(
    data: CallbackDelete,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Delete specific logging callback from configuration.
    """
    global prisma_client, proxy_config

    if prisma_client is None:
        raise HTTPException(
            status_code=400,
            detail={"error": CommonProxyErrors.db_not_connected_error.value},
        )

    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"{CommonProxyErrors.not_allowed_access.value}, your role={user_api_key_dict.user_role}"
            },
        )

    if store_model_in_db is not True:
        raise HTTPException(
            status_code=500,
            detail={"error": "Set `'STORE_MODEL_IN_DB='True'` in your env to enable this feature."},
        )

    try:
        # Get current configuration
        config = await proxy_config.get_config()
        callback_name = data.callback_name.lower()

        # Check if callback exists in current configuration
        litellm_settings = config.get("litellm_settings", {})
        success_callbacks = litellm_settings.get("success_callback", [])

        if callback_name not in success_callbacks:
            raise HTTPException(
                status_code=404,
                detail={"error": f"Callback '{callback_name}' not found in active configuration"},
            )

        before_success_callbacks = list(success_callbacks)

        # Remove callback from success_callback list
        success_callbacks.remove(callback_name)
        config.setdefault("litellm_settings", {})["success_callback"] = success_callbacks

        # Save the updated configuration
        await proxy_config.save_config(new_config=config)

        asyncio.create_task(
            create_config_audit_log(
                "litellm_settings",
                "deleted",
                {"success_callback": before_success_callbacks},
                {"success_callback": success_callbacks},
                user_api_key_dict,
            )
        )

        # Restart the proxy to apply changes
        await proxy_config.add_deployment(prisma_client=prisma_client, proxy_logging_obj=proxy_logging_obj)

        return {
            "message": f"Successfully deleted callback: {callback_name}",
            "removed_callback": callback_name,
            "remaining_callbacks": success_callbacks,
            "deleted_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.error(f"litellm.proxy.proxy_server.delete_callback(): Exception occurred - {e!s}")
        verbose_proxy_logger.debug(traceback.format_exc())
        raise ProxyException(
            message="Error deleting callback: " + str(e),
            type=ProxyErrorTypes.internal_server_error,
            param="callback_name",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/get/config/callbacks",
    tags=["config.yaml"],
    include_in_schema=False,
    dependencies=[Depends(user_api_key_auth)],
)
async def get_config(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    For Admin UI - allows admin to view config via UI
    # return the callbacks and the env variables for the callback

    """
    global llm_router, llm_model_list, general_settings, proxy_config, proxy_logging_obj, master_key
    try:
        all_available_callbacks = AllCallbacks()

        config_data = await proxy_config.get_config()
        _litellm_settings = config_data.get("litellm_settings", {})
        _general_settings = config_data.get("general_settings", {})
        environment_variables = config_data.get("environment_variables", {})

        is_full_admin = user_api_key_dict.user_role == LitellmUserRoles.PROXY_ADMIN

        _success_callbacks = _litellm_settings.get("success_callback", [])
        _failure_callbacks = _litellm_settings.get("failure_callback", [])
        _success_and_failure_callbacks = _litellm_settings.get("callbacks", [])

        # Normalize string callbacks to lists
        def normalize_callback(callback):
            if isinstance(callback, str):
                return [callback]
            elif callback is None:
                return []
            return callback

        _success_callbacks = normalize_callback(_success_callbacks)
        _failure_callbacks = normalize_callback(_failure_callbacks)
        _success_and_failure_callbacks = normalize_callback(_success_and_failure_callbacks)

        _data_to_return = []
        """
        [
            {
                "name": "langfuse",
                "variables": {
                    "LANGFUSE_PUB_KEY": "value",
                    "LANGFUSE_SECRET_KEY": "value",
                    "LANGFUSE_HOST": "value"
                },
                "type": "success"
            }
        ]

        """

        for _callback in _success_callbacks:
            _data_to_return.append(process_callback(_callback, "success", environment_variables))

        for _callback in _failure_callbacks:
            _data_to_return.append(process_callback(_callback, "failure", environment_variables))

        for _callback in _success_and_failure_callbacks:
            _data_to_return.append(process_callback(_callback, "success_and_failure", environment_variables))

        _data_to_return = _apply_callback_role_gate(_data_to_return, is_full_admin)

        # Check if slack alerting is on
        _alerting = _general_settings.get("alerting", [])
        alerting_data = []
        if "slack" in _alerting:
            _slack_values, _ = resolve_fields(
                SLACK_DESCRIPTORS, environment_variables, os.environ, empty_db_is_set=True
            )
            _slack_env_vars = _apply_alerting_env_role_gate(_slack_values, is_full_admin)

            _alerting_types = proxy_logging_obj.slack_alerting_instance.alert_types
            _all_alert_types = proxy_logging_obj.slack_alerting_instance._all_possible_alert_types()
            _alerts_to_webhook = _apply_webhook_role_gate(
                proxy_logging_obj.slack_alerting_instance.alert_to_webhook_url, is_full_admin
            )
            alerting_data.append(
                {
                    "name": "slack",
                    "variables": _slack_env_vars,
                    "active_alerts": _alerting_types,
                    "alerts_to_webhook": _alerts_to_webhook,
                }
            )
        # pass email alerting vars
        _email_values, _ = resolve_fields(EMAIL_DESCRIPTORS, environment_variables, os.environ, empty_db_is_set=True)
        _email_env_vars = _apply_alerting_env_role_gate(_email_values, is_full_admin)

        alerting_data.append(
            {
                "name": "email",
                "variables": _email_env_vars,
            }
        )

        if llm_router is None:
            _router_settings = {}
        else:
            _router_settings = llm_router.get_settings()

        return {
            "status": "success",
            "callbacks": _data_to_return,
            "alerts": alerting_data,
            "router_settings": _router_settings,
            "available_callbacks": all_available_callbacks,
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"litellm.proxy.proxy_server.get_config(): Exception occured - {e!s}")
        if isinstance(e, HTTPException):
            raise ProxyException(
                message=getattr(e, "detail", f"Authentication Error({e!s})"),
                type=ProxyErrorTypes.auth_error,
                param=getattr(e, "param", "None"),
                code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        elif isinstance(e, ProxyException):
            raise e
        raise ProxyException(
            message="Authentication Error, " + str(e),
            type=ProxyErrorTypes.auth_error,
            param=getattr(e, "param", "None"),
            code=status.HTTP_400_BAD_REQUEST,
        )


@router.get(
    "/config/yaml",
    tags=["config.yaml"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def config_yaml_endpoint(config_info: ConfigYAML):
    """
    This is a mock endpoint, to show what you can set in config.yaml details in the Swagger UI.

    Parameters:

    The config.yaml object has the following attributes:
    - **model_list**: *Optional[List[ModelParams]]* - A list of supported models on the server, along with model-specific configurations. ModelParams includes "model_name" (name of the model), "litellm_params" (litellm-specific parameters for the model), and "model_info" (additional info about the model such as id, mode, cost per token, etc).

    - **litellm_settings**: *Optional[dict]*: Settings for the litellm module. You can specify multiple properties like "drop_params", "set_verbose", "api_base", "cache".

    - **general_settings**: *Optional[ConfigGeneralSettings]*: General settings for the server like "completion_model" (default model for chat completion calls), "use_azure_key_vault" (option to load keys from azure key vault), "master_key" (key required for all calls to proxy), and others.

    Please, refer to each class's description for a better understanding of the specific attributes within them.

    Note: This is a mock endpoint primarily meant for demonstration purposes, and does not actually provide or change any configurations.
    """
    return {"hello": "world"}


@router.post(
    "/reload/model_cost_map",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def reload_model_cost_map(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    ADMIN ONLY / MASTER KEY Only Endpoint

    Manually reload the model cost map from the remote source.
    This will fetch fresh pricing data from the model_prices_and_context_window.json file.
    """
    # Check if user is admin
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Admin role required. Current role: {user_api_key_dict.user_role}",
        )

    try:
        global prisma_client
        if prisma_client is None:
            raise HTTPException(status_code=500, detail="Database connection not available")

        # Immediately reload the model cost map in the current pod
        from litellm.litellm_core_utils.get_model_cost_map import get_model_cost_map

        model_cost_map_url = litellm.model_cost_map_url
        new_model_cost_map = get_model_cost_map(url=model_cost_map_url)
        litellm.model_cost = new_model_cost_map
        # Invalidate case-insensitive lookup map since model_cost was replaced
        _invalidate_model_cost_lowercase_map()
        # Repopulate provider model sets (e.g. litellm.anthropic_models) so that
        # wildcard patterns like "anthropic/*" include any newly added models.
        litellm.add_known_models(model_cost_map=new_model_cost_map)

        # Update pod's in-memory last reload time
        global last_model_cost_map_reload
        current_time = datetime.utcnow()
        last_model_cost_map_reload = current_time.isoformat()

        # Set force reload flag in database for other pods, preserving existing interval_hours
        existing_config = await ConfigRepository(prisma_client).table.find_unique(
            where={"param_name": "model_cost_map_reload_config"}
        )
        existing_interval = None
        if existing_config and existing_config.param_value:
            existing_interval = existing_config.param_value.get("interval_hours")

        await ConfigRepository(prisma_client).table.upsert(
            where={"param_name": "model_cost_map_reload_config"},
            data={
                "create": {
                    "param_name": "model_cost_map_reload_config",
                    "param_value": safe_dumps({"interval_hours": None, "force_reload": True}),
                },
                "update": {"param_value": safe_dumps({"interval_hours": existing_interval, "force_reload": True})},
            },
        )
        await invalidate_config_param("model_cost_map_reload_config")

        models_count = len(new_model_cost_map) if new_model_cost_map else 0
        verbose_proxy_logger.info(f"Model cost map reloaded successfully in current pod. Models count: {models_count}")

        return {
            "message": f"Price data reloaded successfully! {models_count} models updated.",
            "status": "success",
            "models_count": models_count,
            "timestamp": current_time.isoformat(),
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"Failed to reload model cost map: {e!s}")
        raise HTTPException(status_code=500, detail=f"Failed to reload model cost map: {e!s}")


@router.post(
    "/schedule/model_cost_map_reload",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def schedule_model_cost_map_reload(
    hours: int,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    ADMIN ONLY / MASTER KEY Only Endpoint

    Schedule periodic reload of the model cost map.
    This will create a background job that reloads the model cost map every specified hours.
    """
    # Check if user is admin
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Admin role required. Current role: {user_api_key_dict.user_role}",
        )

    if hours <= 0:
        raise HTTPException(status_code=400, detail="Hours must be greater than 0")

    try:
        global prisma_client
        if prisma_client is None:
            raise HTTPException(status_code=500, detail="Database connection not available")

        # Update database with new reload configuration
        await ConfigRepository(prisma_client).table.upsert(
            where={"param_name": "model_cost_map_reload_config"},
            data={
                "create": {
                    "param_name": "model_cost_map_reload_config",
                    "param_value": safe_dumps({"interval_hours": hours, "force_reload": False}),
                },
                "update": {"param_value": safe_dumps({"interval_hours": hours, "force_reload": False})},
            },
        )
        await invalidate_config_param("model_cost_map_reload_config")

        verbose_proxy_logger.info(f"Model cost map reload scheduled for every {hours} hours")

        return {
            "message": f"Model cost map reload scheduled for every {hours} hours",
            "status": "success",
            "interval_hours": hours,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"Failed to schedule model cost map reload: {e!s}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule model cost map reload: {e!s}",
        )


@router.delete(
    "/schedule/model_cost_map_reload",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def cancel_model_cost_map_reload(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    ADMIN ONLY / MASTER KEY Only Endpoint

    Cancel the scheduled periodic reload of the model cost map.
    """
    # Check if user is admin
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Admin role required. Current role: {user_api_key_dict.user_role}",
        )

    try:
        global prisma_client
        if prisma_client is None:
            raise HTTPException(status_code=500, detail="Database connection not available")

        # Remove reload configuration from database
        await ConfigRepository(prisma_client).table.delete(where={"param_name": "model_cost_map_reload_config"})
        await invalidate_config_param("model_cost_map_reload_config")

        verbose_proxy_logger.info("Model cost map reload schedule cancelled")

        return {
            "message": "Model cost map reload schedule cancelled",
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"Failed to cancel model cost map reload: {e!s}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel model cost map reload: {e!s}")


@router.get(
    "/schedule/model_cost_map_reload/status",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def get_model_cost_map_reload_status(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    ADMIN ONLY / MASTER KEY Only Endpoint

    Get the status of the scheduled model cost map reload job.
    """
    # Read-only status check — admin viewers can read.
    if not _user_has_admin_view(user_api_key_dict):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Admin role required. Current role: {user_api_key_dict.user_role}",
        )

    try:
        global prisma_client, last_model_cost_map_reload

        verbose_proxy_logger.info(f"Checking model cost map reload status. Last reload: {last_model_cost_map_reload}")

        if prisma_client is None:
            verbose_proxy_logger.info("No database connection, returning not scheduled")
            return {
                "scheduled": False,
                "interval_hours": None,
                "last_run": None,
                "next_run": None,
            }

        # Get reload configuration from database
        config_record = await ConfigRepository(prisma_client).table.find_unique(
            where={"param_name": "model_cost_map_reload_config"}
        )

        if config_record is None or config_record.param_value is None:
            verbose_proxy_logger.info("No model cost map reload configuration found")
            return {
                "scheduled": False,
                "interval_hours": None,
                "last_run": None,
                "next_run": None,
            }

        config = config_record.param_value
        interval_hours = config.get("interval_hours")

        if interval_hours is None:
            verbose_proxy_logger.info("No interval configured, returning not scheduled")
            return {
                "scheduled": False,
                "interval_hours": None,
                "last_run": None,
                "next_run": None,
            }

        current_time = datetime.utcnow()
        next_run = None

        # Use pod's in-memory last reload time
        if last_model_cost_map_reload is not None:
            try:
                last_reload_time = datetime.fromisoformat(last_model_cost_map_reload)
                time_since_last_reload = current_time - last_reload_time
                hours_since_last_reload = time_since_last_reload.total_seconds() / 3600

                if hours_since_last_reload < interval_hours:
                    next_run = (last_reload_time + timedelta(hours=interval_hours)).isoformat()
            except Exception as e:
                verbose_proxy_logger.warning(f"Error parsing last reload time: {e}")

        return {
            "scheduled": True,
            "interval_hours": interval_hours,
            "last_run": last_model_cost_map_reload,
            "next_run": next_run,
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"Failed to get model cost map reload status: {e!s}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model cost map reload status: {e!s}",
        )


@router.get(
    "/model/cost_map/source",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def get_model_cost_map_source(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    ADMIN ONLY / MASTER KEY Only Endpoint

    Returns information about where the current model cost/pricing data was loaded from.

    Response fields:
    - source: "local" (bundled backup) or "remote" (fetched from URL)
    - url: the remote URL that was attempted (null when env-forced local)
    - is_env_forced: true if LITELLM_LOCAL_MODEL_COST_MAP=True forced local usage
    - fallback_reason: human-readable reason why remote failed (null on success)
    - model_count: number of models in the currently loaded cost map
    """
    # Read-only source info — admin viewers can read.
    if not _user_has_admin_view(user_api_key_dict):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Admin role required. Current role: {user_api_key_dict.user_role}",
        )

    try:
        from litellm.litellm_core_utils.get_model_cost_map import (
            get_model_cost_map_source_info,
        )

        source_info = get_model_cost_map_source_info()
        model_count = len(litellm.model_cost) if litellm.model_cost else 0

        return {
            **source_info,
            "model_count": model_count,
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"Failed to get model cost map source info: {e!s}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model cost map source info: {e!s}",
        )


#### ANTHROPIC BETA HEADERS RELOAD ENDPOINTS ####


@router.post(
    "/reload/anthropic_beta_headers",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def reload_anthropic_beta_headers(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    ADMIN ONLY / MASTER KEY Only Endpoint

    Manually reload the Anthropic beta headers configuration from the remote source.
    This will fetch fresh configuration from the anthropic_beta_headers_config.json file.
    """
    # Check if user is admin
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Admin role required. Current role: {user_api_key_dict.user_role}",
        )

    try:
        global prisma_client
        if prisma_client is None:
            raise HTTPException(status_code=500, detail="Database connection not available")

        # Immediately reload the beta headers config in the current pod
        from litellm.anthropic_beta_headers_manager import reload_beta_headers_config

        new_config = reload_beta_headers_config()

        # Update pod's in-memory last reload time
        global last_anthropic_beta_headers_reload
        current_time = datetime.utcnow()
        last_anthropic_beta_headers_reload = current_time.isoformat()

        # Set force reload flag in database for other pods, preserving existing interval_hours
        existing_beta_config = await ConfigRepository(prisma_client).table.find_unique(
            where={"param_name": "anthropic_beta_headers_reload_config"}
        )
        existing_beta_interval = None
        if existing_beta_config and existing_beta_config.param_value:
            existing_beta_interval = existing_beta_config.param_value.get("interval_hours")

        await ConfigRepository(prisma_client).table.upsert(
            where={"param_name": "anthropic_beta_headers_reload_config"},
            data={
                "create": {
                    "param_name": "anthropic_beta_headers_reload_config",
                    "param_value": safe_dumps({"interval_hours": None, "force_reload": True}),
                },
                "update": {"param_value": safe_dumps({"interval_hours": existing_beta_interval, "force_reload": True})},
            },
        )
        await invalidate_config_param("anthropic_beta_headers_reload_config")

        provider_count = sum(1 for k in new_config.keys() if k not in ["provider_aliases", "description"])
        verbose_proxy_logger.info(
            f"Anthropic beta headers config reloaded successfully in current pod. Providers: {provider_count}"
        )

        return {
            "message": f"Anthropic beta headers configuration reloaded successfully! {provider_count} providers updated.",
            "status": "success",
            "providers_count": provider_count,
            "timestamp": current_time.isoformat(),
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"Failed to reload anthropic beta headers: {e!s}")
        raise HTTPException(status_code=500, detail=f"Failed to reload anthropic beta headers: {e!s}")


@router.post(
    "/schedule/anthropic_beta_headers_reload",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def schedule_anthropic_beta_headers_reload(
    hours: int,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    ADMIN ONLY / MASTER KEY Only Endpoint

    Schedule periodic reload of the Anthropic beta headers configuration.
    This will create a background job that reloads the configuration every specified hours.
    """
    # Check if user is admin
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Admin role required. Current role: {user_api_key_dict.user_role}",
        )

    if hours <= 0:
        raise HTTPException(status_code=400, detail="Hours must be greater than 0")

    try:
        global prisma_client
        if prisma_client is None:
            raise HTTPException(status_code=500, detail="Database connection not available")

        # Update database with new reload configuration
        await ConfigRepository(prisma_client).table.upsert(
            where={"param_name": "anthropic_beta_headers_reload_config"},
            data={
                "create": {
                    "param_name": "anthropic_beta_headers_reload_config",
                    "param_value": safe_dumps({"interval_hours": hours, "force_reload": False}),
                },
                "update": {"param_value": safe_dumps({"interval_hours": hours, "force_reload": False})},
            },
        )
        await invalidate_config_param("anthropic_beta_headers_reload_config")

        verbose_proxy_logger.info(f"Anthropic beta headers reload scheduled for every {hours} hours")

        return {
            "message": f"Anthropic beta headers reload scheduled for every {hours} hours",
            "status": "success",
            "interval_hours": hours,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"Failed to schedule anthropic beta headers reload: {e!s}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule anthropic beta headers reload: {e!s}",
        )


@router.delete(
    "/schedule/anthropic_beta_headers_reload",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def cancel_anthropic_beta_headers_reload(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    ADMIN ONLY / MASTER KEY Only Endpoint

    Cancel the scheduled periodic reload of the Anthropic beta headers configuration.
    """
    # Check if user is admin
    if user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Admin role required. Current role: {user_api_key_dict.user_role}",
        )

    try:
        global prisma_client
        if prisma_client is None:
            raise HTTPException(status_code=500, detail="Database connection not available")

        # Remove reload configuration from database
        await ConfigRepository(prisma_client).table.delete(where={"param_name": "anthropic_beta_headers_reload_config"})
        await invalidate_config_param("anthropic_beta_headers_reload_config")

        verbose_proxy_logger.info("Anthropic beta headers reload schedule cancelled")

        return {
            "message": "Anthropic beta headers reload schedule cancelled",
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"Failed to cancel anthropic beta headers reload: {e!s}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel anthropic beta headers reload: {e!s}",
        )


@router.get(
    "/schedule/anthropic_beta_headers_reload/status",
    tags=["model management"],
    dependencies=[Depends(user_api_key_auth)],
    include_in_schema=False,
)
async def get_anthropic_beta_headers_reload_status(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    ADMIN ONLY / MASTER KEY Only Endpoint

    Get the status of the scheduled Anthropic beta headers reload job.
    """
    # Read-only status — admin viewers can read.
    if not _user_has_admin_view(user_api_key_dict):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Admin role required. Current role: {user_api_key_dict.user_role}",
        )

    try:
        global prisma_client, last_anthropic_beta_headers_reload

        verbose_proxy_logger.info(
            f"Checking anthropic beta headers reload status. Last reload: {last_anthropic_beta_headers_reload}"
        )

        if prisma_client is None:
            verbose_proxy_logger.info("No database connection, returning not scheduled")
            return {
                "scheduled": False,
                "interval_hours": None,
                "last_run": None,
                "next_run": None,
            }

        # Get reload configuration from database
        config_record = await ConfigRepository(prisma_client).table.find_unique(
            where={"param_name": "anthropic_beta_headers_reload_config"}
        )

        if config_record is None or config_record.param_value is None:
            verbose_proxy_logger.info("No anthropic beta headers reload configuration found")
            return {
                "scheduled": False,
                "interval_hours": None,
                "last_run": None,
                "next_run": None,
            }

        config = config_record.param_value
        interval_hours = config.get("interval_hours")

        if interval_hours is None:
            verbose_proxy_logger.info("No interval configured, returning not scheduled")
            return {
                "scheduled": False,
                "interval_hours": None,
                "last_run": None,
                "next_run": None,
            }

        current_time = datetime.utcnow()
        next_run = None

        # Use pod's in-memory last reload time
        if last_anthropic_beta_headers_reload is not None:
            try:
                last_reload_time = datetime.fromisoformat(last_anthropic_beta_headers_reload)
                time_since_last_reload = current_time - last_reload_time
                hours_since_last_reload = time_since_last_reload.total_seconds() / 3600

                if hours_since_last_reload < interval_hours:
                    next_run = (last_reload_time + timedelta(hours=interval_hours)).isoformat()
            except Exception as e:
                verbose_proxy_logger.warning(f"Error parsing last reload time: {e}")

        return {
            "scheduled": True,
            "interval_hours": interval_hours,
            "last_run": last_anthropic_beta_headers_reload,
            "next_run": next_run,
        }
    except Exception as e:
        verbose_proxy_logger.exception(f"Failed to get anthropic beta headers reload status: {e!s}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get anthropic beta headers reload status: {e!s}",
        )


@router.get("/", dependencies=[Depends(user_api_key_auth)])
async def home(request: Request):
    return "LiteLLM: RUNNING"


@router.get(
    "/adaptive_router/state",
    tags=["adaptive_router"],
    dependencies=[Depends(user_api_key_auth)],
)
async def get_adaptive_router_state(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """Return live bandit posteriors + queue depth for every configured adaptive router.

    Admin-only. Returns 404 if no adaptive router is configured.

    Response shape: `{"routers": [<snapshot>, ...]}` — one snapshot per
    adaptive-router deployment. Each snapshot's `router_name` field identifies
    which deployment it came from.
    """
    # Read-only state — admin viewers can read.
    if not _user_has_admin_view(user_api_key_dict):
        raise HTTPException(
            status_code=403,
            detail={"error": CommonProxyErrors.not_allowed_access.value},
        )
    if llm_router is None or not llm_router.adaptive_routers:
        raise HTTPException(
            status_code=404,
            detail={"error": "No adaptive_router is configured on this proxy."},
        )
    snapshots = [
        await tagged.strategy.get_state_snapshot()
        for tagged_routers in llm_router.adaptive_routers.values()
        for tagged in tagged_routers
    ]
    return {"routers": snapshots}


@router.get("/routes", dependencies=[Depends(user_api_key_auth)])
async def get_routes():
    """
    Get a list of available routes in the FastAPI application.
    """
    from litellm.proxy.common_utils.get_routes import GetRoutes

    routes = []
    for route in app.routes:
        endpoint_route = getattr(route, "endpoint", None)
        if endpoint_route is not None:
            routes.extend(
                GetRoutes.get_app_routes(
                    route=route,
                    endpoint_route=endpoint_route,
                )
            )
        # Handle mounted sub-applications (like MCP app)
        elif hasattr(route, "app") and hasattr(route, "path"):
            routes.extend(GetRoutes.get_routes_for_mounted_app(route=route))

    return {"routes": routes}


#### TEST ENDPOINTS ####
# @router.get(
#     "/token/generate",
#     dependencies=[Depends(user_api_key_auth)],
#     include_in_schema=False,
# )
# async def token_generate():
#     """
#     Test endpoint. Admin-only access. Meant for generating admin tokens with specific claims and testing if they work for creating keys, etc.
#     """
#     # Initialize AuthJWTSSO with your OpenID Provider configuration
#     from fastapi_sso import AuthJWTSSO

#     auth_jwt_sso = AuthJWTSSO(
#         issuer=os.getenv("OPENID_BASE_URL"),
#         client_id=os.getenv("OPENID_CLIENT_ID"),
#         client_secret=os.getenv("OPENID_CLIENT_SECRET"),
#         scopes=["litellm_proxy_admin"],
#     )

#     token = auth_jwt_sso.create_access_token()

#     return {"token": token}


app.include_router(router)
app.include_router(response_router)
app.include_router(public_endpoints_router)
app.include_router(rerank_router)
app.include_router(ocr_router)
app.include_router(video_router)
app.include_router(container_router)
app.include_router(search_router)
app.include_router(image_router)
app.include_router(fine_tuning_router)
app.include_router(credential_router)
app.include_router(batches_router)
app.include_router(openai_files_router)
app.include_router(llm_passthrough_router)
app.include_router(pass_through_router)
app.include_router(health_router)
app.include_router(key_management_router)
app.include_router(internal_user_router)
app.include_router(team_router)
app.include_router(ui_sso_router)
app.include_router(organization_router)
app.include_router(customer_router)
app.include_router(spend_management_router)
app.include_router(caching_router)
app.include_router(analytics_router)
app.include_router(callback_management_endpoints_router)
app.include_router(debugging_endpoints_router)
app.include_router(rust_control_plane_router)
app.include_router(ui_crud_endpoints_router)
app.include_router(team_callback_router)
app.include_router(budget_management_router)
app.include_router(model_management_router)
app.include_router(model_access_group_management_router)
app.include_router(tag_management_router)
app.include_router(workflow_management_router)
app.include_router(memory_router)
app.include_router(plugin_router)
app.include_router(cost_tracking_settings_router)
app.include_router(router_settings_router)
app.include_router(fallback_management_router)
app.include_router(cache_settings_router)
app.include_router(coordination_redis_settings_router)
app.include_router(user_agent_analytics_router)
app.include_router(enterprise_router)
app.include_router(ui_discovery_endpoints_router)
# Eager: /models/{name}:method overlaps with the OpenAI /models endpoint.
app.include_router(google_router)

attach_lazy_features(app)
app.add_middleware(
    RequestSizeLimitMiddleware,
    get_max_request_size_mb=lambda: general_settings.get("max_request_size_mb"),
    is_request_size_limit_enabled=lambda: premium_user is True,
)


async def _stream_mcp_asgi_response(handle_fn, scope: dict, receive) -> "StreamingResponse":
    """
    Call an ASGI MCP handler and return a StreamingResponse so SSE/streaming works.

    asyncio.create_task copies the current context, so any ContextVar set before
    this call (e.g. _mcp_active_toolset_id) is visible inside the handler task.
    """
    from starlette.responses import StreamingResponse

    headers_ready: asyncio.Future = asyncio.get_running_loop().create_future()
    body_queue: asyncio.Queue = asyncio.Queue(maxsize=1024)

    async def bridging_send(message):
        if message["type"] == "http.response.start":
            if not headers_ready.done():
                headers_ready.set_result((message.get("status", 200), message.get("headers", [])))
        elif message["type"] == "http.response.body":
            chunk = message.get("body", b"")
            if chunk:
                await body_queue.put(chunk)
            if not message.get("more_body", False):
                await body_queue.put(None)  # EOF sentinel

    handler_task = asyncio.create_task(handle_fn(scope, receive, bridging_send))

    # If the handler task dies (exception or cancellation) without sending the EOF
    # sentinel, body_iter() would block forever on body_queue.get().  The callback
    # below guarantees the queue gets unblocked regardless of how the task ends.
    # When this happens before response headers, propagate the original exception
    # instead of waiting for the header timeout.
    def _ensure_eof(task: asyncio.Task) -> None:
        if task.cancelled():
            body_queue.put_nowait(None)
            return

        task_exception = task.exception()
        if task_exception is not None:
            if not headers_ready.done():
                headers_ready.set_exception(task_exception)
            body_queue.put_nowait(None)

    handler_task.add_done_callback(_ensure_eof)

    try:
        status, raw_headers = await asyncio.wait_for(asyncio.shield(headers_ready), timeout=30.0)
    except asyncio.TimeoutError:
        handler_task.cancel()
        raise HTTPException(status_code=504, detail="MCP handler did not respond in time")

    headers_dict = {k.decode("latin-1"): v.decode("latin-1") for k, v in raw_headers}

    async def body_iter():
        try:
            while True:
                chunk = await body_queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            if not handler_task.done():
                handler_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await handler_task

    return StreamingResponse(
        body_iter(),
        status_code=status,
        headers=headers_dict,
        media_type=headers_dict.get("content-type"),
    )


########################################################
# MCP Server
########################################################


# Toolset-namespaced MCP routes - handle /toolset/{toolset_name}/mcp
# Must be declared BEFORE /{mcp_server_name}/mcp to avoid being swallowed by the catchall.
@app.api_route(
    "/toolset/{toolset_name}/mcp",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def toolset_mcp_route(toolset_name: str, request: Request):
    """
    Namespace a toolset as its own MCP endpoint.

    Connecting to /toolset/<name>/mcp exposes exactly the tools defined in
    the toolset. Access is enforced: non-admin API keys must have the toolset
    listed in their object_permission.mcp_toolsets grant list, or the request
    will be rejected with a 403.
    """
    try:
        from litellm.proxy._experimental.mcp_server.mcp_server_manager import (
            global_mcp_server_manager,
        )
        from litellm.proxy._experimental.mcp_server.server import (
            _mcp_active_toolset_id,
            handle_streamable_http_mcp,
        )

        if prisma_client is None:
            raise HTTPException(status_code=503, detail="Database not available")

        toolset = await global_mcp_server_manager.get_toolset_by_name_cached(prisma_client, toolset_name)
        if toolset is None:
            raise HTTPException(
                status_code=404,
                detail=f"Toolset '{toolset_name}' not found",
            )

        scope = dict(request.scope)
        scope["path"] = "/mcp"

        token = _mcp_active_toolset_id.set(toolset.toolset_id)
        try:
            return await _stream_mcp_asgi_response(handle_streamable_http_mcp, scope, request.receive)
        finally:
            _mcp_active_toolset_id.reset(token)

    except HTTPException as e:
        raise e
    except Exception as e:
        verbose_proxy_logger.exception("Error handling toolset MCP route for %s: %s", toolset_name, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


async def _mcp_forward_as_path(path_segment: str, request: Request):
    """Rewrite path to /mcp/{path_segment} and stream the response."""
    from litellm.proxy._experimental.mcp_server.server import (
        handle_streamable_http_mcp,
    )

    scope = dict(request.scope)
    # Preserve the public request path for OAuth challenge URL selection.
    scope["_original_path"] = scope.get("path", "")
    scope["path"] = f"/mcp/{path_segment}"
    return await _stream_mcp_asgi_response(handle_streamable_http_mcp, scope, request.receive)


async def _resolve_mcp_csv_tokens(csv_segment: str, client_ip: str | None) -> list[str]:
    """Validate a comma-separated ``/{name1,name2,...}/mcp`` segment.

    For each token, check (in order) whether it is a registered MCP server
    alias / name or an MCP access group tag (cached). Tokens are stripped,
    deduped (exact-match, keeping first occurrence in original order), and
    capped at ``DEFAULT_MCP_NAMESPACE_CSV_MAX_TOKENS`` to bound the
    per-request DB / cache fan-out an authenticated caller can trigger by
    stuffing the path with tokens. Dedup is case-sensitive on purpose:
    downstream resolvers may treat names case-sensitively, so collapsing
    ``MyGroup`` and ``mygroup`` would risk dropping a valid distinct token.

    Toolset names are intentionally NOT resolved here — toolsets bind a single
    toolset id into request scope and have no defined semantics inside a
    comma-separated server list.

    Returns the subset of resolved tokens in original order. An empty list
    means the segment did not resolve to any known server / group; the caller
    should treat that as a 404 instead of forwarding it downstream (where an
    all-unmatched server filter falls back to the full ``allowed_mcp_servers``
    list and silently broadens the request scope).
    """
    from litellm.constants import DEFAULT_MCP_NAMESPACE_CSV_MAX_TOKENS
    from litellm.proxy._experimental.mcp_server.mcp_server_manager import (
        global_mcp_server_manager,
    )

    seen: set = set()
    deduped: list[str] = []
    for raw in csv_segment.split(","):
        token = raw.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= DEFAULT_MCP_NAMESPACE_CSV_MAX_TOKENS:
            break

    resolved: list[str] = []
    for token in deduped:
        if global_mcp_server_manager.get_mcp_server_by_name(token, client_ip=client_ip):
            resolved.append(token)
            continue
        if await _is_mcp_access_group_cached(token):
            resolved.append(token)
    return resolved


async def _is_mcp_access_group_cached(name: str) -> bool:
    """Return True if *name* is a known MCP access group tag.

    Positive results are cached for the configured management-object TTL
    (``get_management_object_ttl(user_api_key_cache)``). Negative results are
    cached for a short
    ``DEFAULT_MCP_ACCESS_GROUP_NEGATIVE_CACHE_TTL`` window so unauthenticated
    callers cannot force a fresh DB lookup per request for unknown names, while
    bounding staleness so a transient DB error (which surfaces as an empty
    list) cannot hide a real group for long.
    """
    from litellm.constants import DEFAULT_MCP_ACCESS_GROUP_NEGATIVE_CACHE_TTL
    from litellm.proxy._experimental.mcp_server.auth.user_api_key_auth_mcp import (
        MCPRequestHandler,
    )

    cache_key = f"mcp_access_group_exists:{name}"
    cached = await user_api_key_cache.async_get_cache(key=cache_key)
    if cached is not None:
        return bool(cached)
    result = bool(await MCPRequestHandler._get_mcp_servers_from_access_groups([name]))
    await user_api_key_cache.async_set_cache(
        key=cache_key,
        value=result,
        ttl=(get_management_object_ttl(user_api_key_cache) if result else DEFAULT_MCP_ACCESS_GROUP_NEGATIVE_CACHE_TTL),
    )
    return result


# Dynamic MCP server routes - handle /{mcp_server_name}/mcp
@app.api_route(
    "/{mcp_server_name}/mcp",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def dynamic_mcp_route(mcp_server_name: str, request: Request):
    """Handle /{name}/mcp for MCP server aliases, toolsets, MCP access group tags, and comma-separated lists.

    Resolution order:
    1. Registered MCP server alias / name
    2. Comma-separated list (short-circuits before any DB call)
    3. Toolset name (DB lookup, cached)
    4. MCP access group tag (DB lookup, cached)
    """
    try:
        from litellm.proxy._experimental.mcp_server.mcp_server_manager import (
            global_mcp_server_manager,
        )
        from litellm.proxy.auth.ip_address_utils import IPAddressUtils

        client_ip = IPAddressUtils.get_mcp_client_ip(request)

        # 1. Registered MCP server alias
        if global_mcp_server_manager.get_mcp_server_by_name(mcp_server_name, client_ip=client_ip):
            return await _mcp_forward_as_path(mcp_server_name, request)

        # 2. Comma-separated list — validate every token resolves to a known
        # server alias or access group before forwarding. Bounds DB / cache
        # fan-out and prevents the downstream filter from silently falling back
        # to the full allowed_mcp_servers list when no token matches.
        if "," in mcp_server_name:
            resolved_tokens = await _resolve_mcp_csv_tokens(mcp_server_name, client_ip)
            if not resolved_tokens:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"No MCP server, toolset, or access group in '{mcp_server_name}' resolved to a known target"
                    ),
                )
            return await _mcp_forward_as_path(",".join(resolved_tokens), request)

        # 3. Toolset name (cached)
        if prisma_client is not None:
            from litellm.proxy._experimental.mcp_server.server import (
                _mcp_active_toolset_id,
                handle_streamable_http_mcp,
            )

            toolset = await global_mcp_server_manager.get_toolset_by_name_cached(prisma_client, mcp_server_name)
            if toolset is not None:
                scope = dict(request.scope)
                scope["_original_path"] = scope.get("path", "")
                scope["path"] = "/mcp"
                token = _mcp_active_toolset_id.set(toolset.toolset_id)
                try:
                    return await _stream_mcp_asgi_response(handle_streamable_http_mcp, scope, request.receive)
                finally:
                    _mcp_active_toolset_id.reset(token)

        # 4. MCP access group tag (cached)
        if await _is_mcp_access_group_cached(mcp_server_name):
            return await _mcp_forward_as_path(mcp_server_name, request)

        raise HTTPException(
            status_code=404,
            detail=f"MCP server, toolset, or access group '{mcp_server_name}' not found",
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        verbose_proxy_logger.exception("Error handling dynamic MCP route for %s: %s", mcp_server_name, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
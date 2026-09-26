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
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
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

REALTIME_REQUEST_SCOPE_TEMPLATE: Dict[str, Any] = {
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

try:
    import logging

    import backoff
    import fastapi
    import orjson
    import yaml  # type: ignore
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except ImportError as e:
    raise ImportError(f"Missing dependency {e}. Run `pip install 'litellm[proxy]'`")

list_of_messages = [
    "'The thing I wish you improved is...'",
    "'A feature I really want is...'",
    "'The worst thing about this product is...'",
    "'This product would be better if...'",
    "'I don't like how this works...'",
    "'It would help me if you could add...'",
    "'This feature doesn't meet my needs because...'",
    "'I get frustrated when the product...'",
]


def generate_feedback_box():
    box_width = 60

    # Select a random message
    message = random.choice(list_of_messages)

    print()  # noqa: T201
    print("\033[1;37m" + "#" + "-" * box_width + "#\033[0m")  # noqa: T201
    print("\033[1;37m" + "#" + " " * box_width + "#\033[0m")  # noqa: T201
    print("\033[1;37m" + "# {:^59} #\033[0m".format(message))  # noqa: T201
    print(  # noqa: T201
        "\033[1;37m" + "# {:^59} #\033[0m".format("https://github.com/BerriAI/litellm/issues/new")
    )
    print("\033[1;37m" + "#" + " " * box_width + "#\033[0m")  # noqa: T201
    print("\033[1;37m" + "#" + "-" * box_width + "#\033[0m")  # noqa: T201
    print()  # noqa: T201
    print(" Thank you for using LiteLLM! - Krrish & Ishaan")  # noqa: T201
    print()  # noqa: T201
    print()  # noqa: T201
    print()  # noqa: T201
    print(  # noqa: T201
        "\033[1;31mGive Feedback / Get Help: https://github.com/BerriAI/litellm/issues/new\033[0m"
    )
    print()  # noqa: T201
    print()  # noqa: T201


import contextlib
from collections import defaultdict
from contextlib import asynccontextmanager
from functools import lru_cache

import litellm
import litellm._redis
from litellm import Router
from litellm._logging import verbose_proxy_logger, verbose_router_logger
from litellm.caching.caching import DualCache, RedisCache
from litellm.caching.redis_cluster_cache import RedisClusterCache
from litellm.constants import (
    _REALTIME_BODY_CACHE_SIZE,
    APSCHEDULER_COALESCE,
    APSCHEDULER_MAX_INSTANCES,
    APSCHEDULER_MISFIRE_GRACE_TIME,
    APSCHEDULER_REPLACE_EXISTING,
    CLI_SSO_SESSION_TTL_SECONDS,
    DAYS_IN_A_MONTH,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_MODEL_CREATED_AT_TIME,
    GLOBAL_PROXY_SPEND_CACHE_KEY,
    LITELLM_PROXY_ADMIN_NAME,
    LITELLM_PROXY_BUDGET_NAME,
    PROMETHEUS_FALLBACK_STATS_SEND_TIME_HOURS,
    PROXY_BATCH_POLLING_ENABLED,
    PROXY_BATCH_POLLING_INTERVAL,
    PROXY_BATCH_WRITE_AT,
    PROXY_BUDGET_RESCHEDULER_MAX_TIME,
    PROXY_BUDGET_RESCHEDULER_MIN_TIME,
    PROXY_CONFIG_RELOAD_INTERVAL_SECONDS,
)
from litellm.exceptions import RejectedRequestError
from litellm.integrations.custom_logger import CustomLogger
from litellm.integrations.SlackAlerting.slack_alerting import SlackAlerting
from litellm.litellm_core_utils.core_helpers import (
    _get_parent_otel_span_from_kwargs,
    get_litellm_metadata_from_kwargs,
)
from litellm.litellm_core_utils.credential_accessor import CredentialAccessor
from litellm.litellm_core_utils.litellm_logging import Logging as LiteLLMLoggingObj
from litellm.litellm_core_utils.sensitive_data_masker import (
    SensitiveDataMasker,
    mask_sensitive_keys,
)
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
from litellm.proxy._lazy_features import attach_lazy_features
from litellm.proxy._types import *
from litellm.proxy.analytics_endpoints.analytics_endpoints import (
    router as analytics_router,
)
from litellm.proxy.auth.auth_checks import (
    ExperimentalUIJWTToken,
    can_key_call_resolved_model,
    get_team_object,
    log_db_metrics,
)
from litellm.proxy.auth.auth_utils import (
    check_response_size_is_safe,
    is_request_body_safe,
    warn_once_if_custom_auth_skips_common_checks,
)
from litellm.proxy.auth.handle_jwt import JWTHandler
from litellm.proxy.auth.litellm_license import LicenseCheck
from litellm.proxy.auth.model_checks import (
    expand_wildcard_deployments_for_model_info,
    get_all_fallbacks,
    get_complete_model_list,
    get_key_models,
    get_mcp_server_ids,
    get_team_models,
)
from litellm.proxy.auth.user_api_key_auth import (
    _fetch_global_spend_with_event_coordination,
    user_api_key_auth,
    user_api_key_auth_websocket,
)
from litellm.proxy.batches_endpoints.endpoints import router as batches_router

## Import All Misc routes here ##
from litellm.proxy.caching_routes import router as caching_router
from litellm.proxy.common_request_processing import (
    ProxyBaseLLMRequestProcessing,
    _is_azure_model_router_request,
    _should_return_raw_model_name,
    create_response,
)
from litellm.proxy.common_utils.callback_utils import initialize_callbacks_on_proxy
from litellm.proxy.common_utils.debug_utils import init_verbose_loggers
from litellm.proxy.common_utils.debug_utils import router as debugging_endpoints_router
from litellm.proxy.common_utils.encrypt_decrypt_utils import (
    decrypt_value_helper,
    encrypt_value_helper,
)
from litellm.proxy.common_utils.html_forms.ui_login import build_ui_login_form
from litellm.proxy.config_resolvers import resolve_fields
from litellm.proxy.config_resolvers.alerting import (
    EMAIL_DESCRIPTORS,
    SLACK_DESCRIPTORS,
)
from litellm.proxy.common_utils.http_parsing_utils import (
    _read_request_body,
    _safe_get_request_headers,
    check_file_size_under_limit,
    get_form_data,
)
from litellm.proxy.common_utils.load_config_utils import (
    get_config_file_contents_from_gcs,
    get_file_contents_from_s3,
)
from litellm.proxy.common_utils.model_listing_utils import TeamModelNameTranslator
from litellm.proxy.common_utils.openai_endpoint_utils import (
    remove_sensitive_info_from_deployment,
)
from litellm.proxy.common_utils.proxy_state import ProxyState
from litellm.proxy.common_utils.reset_budget_job import ResetBudgetJob
from litellm.proxy.common_utils.swagger_utils import ERROR_RESPONSES
from litellm.proxy.common_utils.timezone_utils import (
    get_budget_reset_settings,
    get_budget_reset_time,
)
from litellm.proxy.common_utils.user_api_key_cache import (
    UserApiKeyCache,
    get_management_object_ttl,
)
from litellm.proxy.container_endpoints.endpoints import router as container_router
from litellm.proxy.credential_endpoints.endpoints import router as credential_router
from litellm.proxy.db.db_transaction_queue.spend_log_cleanup import SpendLogCleanup
from litellm.proxy.db.exception_handler import (
    PrismaDBExceptionHandler,
    call_with_db_reconnect_retry,
)
from litellm.proxy.db.spend_counter_reseed import SpendCounterReseed
from litellm.proxy.discovery_endpoints import ui_discovery_endpoints_router
from litellm.proxy.fine_tuning_endpoints.endpoints import router as fine_tuning_router
from litellm.proxy.fine_tuning_endpoints.endpoints import set_fine_tuning_config
from litellm.proxy.google_endpoints.endpoints import router as google_router
from litellm.proxy.health_check import (
    health_check_filter_kwargs_from_general_settings,
    perform_health_check,
)
from litellm.proxy.health_endpoints._health_endpoints import router as health_router
from litellm.proxy.hooks.model_max_budget_limiter import (
    _PROXY_VirtualKeyModelMaxBudgetLimiter,
)
from litellm.proxy.hooks.prompt_injection_detection import (
    _OPTIONAL_PromptInjectionDetection,
)
from litellm.proxy.hooks.proxy_track_cost_callback import _ProxyDBLogger
from litellm.proxy.image_endpoints.endpoints import router as image_router
from litellm.proxy.litellm_pre_call_utils import add_litellm_data_to_request
from litellm.proxy.logging_endpoints.callback_logs_endpoints import (
    rust_control_plane_router,
)
from litellm.proxy.management_endpoints.budget_management_endpoints import (
    router as budget_management_router,
)
from litellm.proxy.management_endpoints.cache_settings_endpoints import (
    router as cache_settings_router,
)
from litellm.proxy.management_endpoints.callback_management_endpoints import (
    router as callback_management_endpoints_router,
)
from litellm.proxy.management_endpoints.common_utils import (
    _user_has_admin_privileges,
    _user_has_admin_view,
    admin_can_invite_user,
)
from litellm.proxy.management_endpoints.coordination_redis_endpoints import (
    get_persisted_coordination_redis_settings,
    router as coordination_redis_settings_router,
)
from litellm.proxy.management_endpoints.cost_tracking_settings import (
    router as cost_tracking_settings_router,
)
from litellm.proxy.management_endpoints.customer_endpoints import (
    router as customer_router,
)
from litellm.proxy.management_endpoints.fallback_management_endpoints import (
    router as fallback_management_router,
)
from litellm.proxy.management_endpoints.internal_user_endpoints import (
    router as internal_user_router,
)
from litellm.proxy.management_endpoints.internal_user_endpoints import (
    user_update,
)
from litellm.proxy.management_endpoints.key_management_endpoints import (
    delete_verification_tokens,
    duration_in_seconds,
    generate_key_helper_fn,
)
from litellm.proxy.management_endpoints.key_management_endpoints import (
    router as key_management_router,
)
from litellm.proxy.management_endpoints.model_access_group_management_endpoints import (
    router as model_access_group_management_router,
)
from litellm.proxy.management_endpoints.model_management_endpoints import (
    _add_model_to_db,
    _add_team_model_to_db,
    _deduplicate_litellm_router_models,
)
from litellm.proxy.management_endpoints.model_management_endpoints import (
    router as model_management_router,
)
from litellm.proxy.management_endpoints.organization_endpoints import (
    router as organization_router,
)
from litellm.proxy.management_endpoints.router_settings_endpoints import (
    router as router_settings_router,
)
from litellm.proxy.management_endpoints.tag_management_endpoints import (
    router as tag_management_router,
)
from litellm.proxy.management_endpoints.team_callback_endpoints import (
    router as team_callback_router,
)
from litellm.proxy.management_endpoints.team_endpoints import router as team_router
from litellm.proxy.management_endpoints.team_endpoints import (
    update_team,
    validate_membership,
)
from litellm.proxy.management_endpoints.ui_sso import (
    get_disabled_non_admin_personal_key_creation,
)
from litellm.proxy.management_endpoints.ui_sso import router as ui_sso_router
from litellm.proxy.management_endpoints.user_agent_analytics_endpoints import (
    router as user_agent_analytics_router,
)
from litellm.proxy.management_endpoints.workflow_management_endpoints import (
    router as workflow_management_router,
)
from litellm.proxy.management_helpers.audit_logs import (
    create_audit_log_for_update,
    create_object_audit_log,
)
from litellm.proxy.memory.memory_endpoints import router as memory_router
from litellm.proxy.middleware.billable_request_metrics_middleware import (
    BillableRequestMetricsMiddleware,
    BillingRecorder,
)
from litellm.proxy.plugin_routes import (
    register_plugins_from_config,
)
from litellm.proxy.plugin_routes import (
    router as plugin_router,
)

try:
    from litellm.proxy.enterprise_billing.billing_metrics import (
        build_billing_metrics_recorder as _build_billing_metrics_recorder,
    )
    from litellm.proxy.enterprise_billing.billing_metrics import (
        shutdown_billing_metrics_recorder as _shutdown_billing_metrics_recorder,
    )

    build_billing_metrics_recorder: Optional[Callable[..., Optional[BillingRecorder]]] = _build_billing_metrics_recorder
    shutdown_billing_metrics_recorder: Optional[Callable[[], None]] = _shutdown_billing_metrics_recorder
except ImportError:
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
    passthrough_endpoint_router,
    vertex_ai_live_websocket_passthrough,
)
from litellm.proxy.pass_through_endpoints.llm_passthrough_endpoints import (
    router as llm_passthrough_router,
)
from litellm.proxy.pass_through_endpoints.pass_through_endpoints import (
    initialize_pass_through_endpoints,
)
from litellm.proxy.pass_through_endpoints.pass_through_endpoints import (
    router as pass_through_router,
)
from litellm.proxy.public_endpoints import router as public_endpoints_router
from litellm.proxy.rag_endpoints.endpoints import router as rag_router
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

try:
    from litellm._version import version
except Exception:
    version = "0.0.0"
litellm.suppress_debug_info = True
import json
from typing import Union

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    applications,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    ORJSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.routing import APIRouter
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from litellm.types.agents import AgentConfig

# import enterprise folder
enterprise_router = APIRouter()
try:
    # when using litellm cli
    import litellm.proxy.enterprise as enterprise
except Exception:
    # when using litellm docker image
    try:
        import enterprise  # type: ignore
    except Exception:
        pass

###################
# Import enterprise routes
try:
    from litellm_enterprise.proxy.enterprise_routes import router as _enterprise_router
    from litellm_enterprise.proxy.proxy_server import EnterpriseProxyConfig

    enterprise_router = _enterprise_router
    enterprise_proxy_config: Optional[EnterpriseProxyConfig] = EnterpriseProxyConfig()
except ImportError:
    enterprise_proxy_config = None
###################

server_root_path = get_server_root_path()
_license_check = LicenseCheck()
premium_user: bool = _license_check.is_premium()
premium_user_data: Optional["EnterpriseLicenseData"] = _license_check.airgapped_license_data
global_max_parallel_request_retries_env: Optional[str] = os.getenv("LITELLM_GLOBAL_MAX_PARALLEL_REQUEST_RETRIES")
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

global_max_parallel_request_retry_timeout_env: Optional[str] = os.getenv(
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
        try:
            # flush langfuse logs on shutdow
            from litellm.utils import langFuseLogger

            if langFuseLogger is not None:
                langFuseLogger.Langfuse.flush()
        except Exception:
            # [DO NOT BLOCK shutdown events for this]
            pass

    ## RESET CUSTOM VARIABLES ##
    cleanup_router_config_variables()


async def _initialize_shared_aiohttp_session():
    """Initialize shared aiohttp session for connection reuse with connection limits."""
    try:
        from aiohttp import ClientSession, TCPConnector

        from litellm.llms.custom_httpx.http_handler import (
            _build_aiohttp_keepalive_socket_factory,
        )

        connector_kwargs: Dict[str, Any] = {
            "keepalive_timeout": AIOHTTP_KEEPALIVE_TIMEOUT,
            "ttl_dns_cache": AIOHTTP_TTL_DNS_CACHE,
        }
        if AIOHTTP_NEEDS_CLEANUP_CLOSED:
            connector_kwargs["enable_cleanup_closed"] = True
        if AIOHTTP_CONNECTOR_LIMIT > 0:
            connector_kwargs["limit"] = AIOHTTP_CONNECTOR_LIMIT
        if AIOHTTP_CONNECTOR_LIMIT_PER_HOST > 0:
            connector_kwargs["limit_per_host"] = AIOHTTP_CONNECTOR_LIMIT_PER_HOST
        socket_factory = _build_aiohttp_keepalive_socket_factory()
        if socket_factory is not None:
            connector_kwargs["socket_factory"] = socket_factory

        connector = TCPConnector(**connector_kwargs)
        session = ClientSession(connector=connector)

        verbose_proxy_logger.info(
            f"SESSION REUSE: Created shared aiohttp session for connection pooling (ID: {id(session)}, "
            f"limit={AIOHTTP_CONNECTOR_LIMIT}, limit_per_host={AIOHTTP_CONNECTOR_LIMIT_PER_HOST})"
        )
        return session
    except Exception as e:
        verbose_proxy_logger.warning(f"Failed to create shared aiohttp session: {e}. Continuing without session reuse.")
        return None


@asynccontextmanager
async def proxy_startup_event(app: FastAPI):
    global \
        prisma_client, \
        master_key, \
        use_background_health_checks, \
        llm_router, \
        llm_model_list, \
        general_settings, \
        proxy_budget_rescheduler_min_time, \
        proxy_budget_rescheduler_max_time, \
        litellm_proxy_admin_name, \
        db_writer_client, \
        store_model_in_db, \
        premium_user, \
        _license_check, \
        proxy_batch_polling_interval, \
        shared_aiohttp_session
    import json

    init_verbose_loggers()

    ## RUN WORKER STARTUP HOOKS (e.g., gflags initialization) ##
    _startup_hooks_env = os.environ.get("LITELLM_WORKER_STARTUP_HOOKS", "")
    if _startup_hooks_env:
        for _hook_spec in _startup_hooks_env.split(","):
            _hook_spec = _hook_spec.strip()
            if not _hook_spec:
                continue
            try:
                if ":" not in _hook_spec:
                    raise ValueError(
                        f"Invalid hook spec '{_hook_spec}': expected format is 'module.path:function_name'"
                    )
                _module_path, _func_name = _hook_spec.rsplit(":", 1)
                _module = importlib.import_module(_module_path)
                _hook_fn = getattr(_module, _func_name)
                if inspect.iscoroutinefunction(_hook_fn):
                    await _hook_fn()
                else:
                    _hook_fn()
                verbose_proxy_logger.info("Worker startup hook '%s' executed successfully", _hook_spec)
            except Exception as e:
                verbose_proxy_logger.error("Worker startup hook '%s' failed: %s", _hook_spec, e)
                raise

    ## CHECK PREMIUM USER
    verbose_proxy_logger.debug(
        "litellm.proxy.proxy_server.py::startup() - CHECKING PREMIUM USER - {}".format(premium_user)
    )
    if premium_user is False:
        premium_user = _license_check.is_premium()

    ## CHECK MASTER KEY IN ENVIRONMENT ##
    master_key = get_secret_str("LITELLM_MASTER_KEY")
    ### LOAD CONFIG ###
    worker_config: Optional[Union[str, dict]] = get_secret("WORKER_CONFIG")  # type: ignore
    env_config_yaml: Optional[str] = get_secret_str("CONFIG_FILE_PATH")
    verbose_proxy_logger.debug("worker_config: %s", _redact_worker_config_for_logging(worker_config))
    # check if it's a valid file path
    if env_config_yaml is not None:
        if os.path.isfile(env_config_yaml) and proxy_config.is_yaml(config_file_path=env_config_yaml):
            (
                llm_router,
                llm_model_list,
                general_settings,
            ) = await proxy_config.load_config(router=llm_router, config_file_path=env_config_yaml)
    elif worker_config is not None:
        if (
            isinstance(worker_config, str)
            and os.path.isfile(worker_config)
            and proxy_config.is_yaml(config_file_path=worker_config)
        ):
            (
                llm_router,
                llm_model_list,
                general_settings,
            ) = await proxy_config.load_config(router=llm_router, config_file_path=worker_config)
        elif os.environ.get("LITELLM_CONFIG_BUCKET_NAME") is not None and isinstance(worker_config, str):
            (
                llm_router,
                llm_model_list,
                general_settings,
            ) = await proxy_config.load_config(router=llm_router, config_file_path=worker_config)
        elif isinstance(worker_config, dict):
            await initialize(**worker_config)
        else:
            # if not, assume it's a json string
            worker_config = json.loads(worker_config)
            if isinstance(worker_config, dict):
                await initialize(**worker_config)

    # check if DATABASE_URL in environment - load from there
    if prisma_client is None:
        _db_url: Optional[str] = get_secret("DATABASE_URL", None)  # type: ignore
        prisma_client = await ProxyStartupEvent._setup_prisma_client(
            database_url=_db_url,
            proxy_logging_obj=proxy_logging_obj,
            user_api_key_cache=user_api_key_cache,
        )

    if prisma_client is not None:

        async def _run_pw_migration():
            try:
                result = await migrate_passwords_to_scrypt_async(prisma_client)
                verbose_proxy_logger.info(f"Password migration: {result}")
            except Exception as e:
                verbose_proxy_logger.warning(f"Password migration skipped: {e}")

        asyncio.create_task(_run_pw_migration())

    ## A coordination_redis block saved from the admin UI lives in the database,
    ## which is only reachable once the prisma client exists. Apply it here, before
    ## the coordination Redis is published to its consumers below.
    db_coordination_redis_cache = await ProxyStartupEvent._init_coordination_redis_from_db(
        litellm_settings=proxy_config.get_config_state().get("litellm_settings") or {},
        llm_router=llm_router,
    )
    if db_coordination_redis_cache is not None:
        _set_redis_usage_cache(db_coordination_redis_cache)

    ## use_redis_transaction_buffer: fall back to a standalone Redis (REDIS_* env)
    ## when the proxy cache backend is not Redis ##
    transaction_buffer_redis_cache = redis_usage_cache
    if transaction_buffer_redis_cache is None:
        transaction_buffer_redis_cache = ProxyStartupEvent._get_transaction_buffer_redis_cache(
            general_settings=general_settings
        )

    ProxyStartupEvent._initialize_startup_logging(
        llm_router=llm_router,
        proxy_logging_obj=proxy_logging_obj,
        redis_usage_cache=transaction_buffer_redis_cache,
    )

    ## V2 OTEL: publish the chosen V2 logger's TracerProvider as the OTel global.
    ## This MUST run after callback initialization above: a preset (arize, langfuse,
    ## …) builds its logger there, folding the OTEL_* base exporter and its own
    ## exporter into one logger. The FastAPI instrumentation mounted at app-creation
    ## binds to the global provider, so reusing that one logger is what makes the
    ## server span and the gen-ai spans share one provider and land in the same
    ## trace, exporting to every configured backend. Running before callback init
    ## (when no logger exists yet) would build a second, generic logger whose
    ## provider became the global, orphaning the gen-ai spans onto a different
    ## backend than the server span. A generic logger is built only when none was
    ## configured.
    try:
        from litellm.integrations.otel.model.config import is_otel_v2_enabled

        if is_otel_v2_enabled():
            from opentelemetry import trace as _otel_trace

            from litellm.integrations.otel.logger import (
                OpenTelemetryV2,
                publish_global_otel_v2_provider,
            )
            from litellm.litellm_core_utils.litellm_logging import _in_memory_loggers

            registered = open_telemetry_logger if isinstance(open_telemetry_logger, OpenTelemetryV2) else None
            publish_global_otel_v2_provider(
                _in_memory_loggers,  # any-ok: pre-existing untyped List[Any] global
                _otel_trace.set_tracer_provider,
                registered=registered,
            )
    except Exception as e:
        verbose_proxy_logger.debug("Skipping OTel V2 provider setup: %s", e)

    ## Validate use_redis_transaction_buffer requires Redis cache ##
    ProxyStartupEvent._validate_redis_transaction_buffer_config(
        general_settings=general_settings,
        redis_usage_cache=transaction_buffer_redis_cache,
    )

    ## SEMANTIC TOOL FILTER ##
    # Read litellm_settings from config for semantic filter initialization
    try:
        verbose_proxy_logger.debug("About to initialize semantic tool filter")
        _config = proxy_config.get_config_state()
        _litellm_settings = _config.get("litellm_settings", {})
        verbose_proxy_logger.debug(f"litellm_settings keys = {list(_litellm_settings.keys())}")
        await ProxyStartupEvent._initialize_semantic_tool_filter(
            llm_router=llm_router,
            litellm_settings=_litellm_settings,
        )
        verbose_proxy_logger.debug("After semantic tool filter initialization")
    except Exception as e:
        verbose_proxy_logger.error(f"Semantic filter init failed: {e}", exc_info=True)

    ## JWT AUTH ##
    ProxyStartupEvent._initialize_jwt_auth(
        general_settings=general_settings,
        prisma_client=prisma_client,
        user_api_key_cache=user_api_key_cache,
    )

    if prompt_injection_detection_obj is not None:  # [TODO] - REFACTOR THIS
        prompt_injection_detection_obj.update_environment(router=llm_router)

    verbose_proxy_logger.debug("prisma_client: %s", prisma_client)
    if prisma_client is not None and litellm.max_budget > 0:
        ProxyStartupEvent._add_proxy_budget_to_db()
        asyncio.create_task(
            ProxyStartupEvent._warm_global_spend_cache(
                user_api_key_cache=user_api_key_cache,
                prisma_client=prisma_client,
            )
        )

    ### START BATCH WRITING DB + CHECKING NEW MODELS###
    if prisma_client is not None:
        await ProxyStartupEvent.initialize_scheduled_background_jobs(
            general_settings=general_settings,
            prisma_client=prisma_client,
            proxy_budget_rescheduler_min_time=proxy_budget_rescheduler_min_time,
            proxy_budget_rescheduler_max_time=proxy_budget_rescheduler_max_time,
            proxy_batch_write_at=proxy_batch_write_at,
            proxy_logging_obj=proxy_logging_obj,
        )

        await ProxyStartupEvent._update_default_team_member_budget()

        ## SYNC UI SETTINGS ##
        await ProxyStartupEvent._sync_ui_settings_to_general_settings()

    # Start background health checks AFTER models are loaded and index is built
    if use_background_health_checks:
        asyncio.create_task(_run_background_health_check())  # start the background health check coroutine.

    # Start adaptive-router queue flusher unconditionally — adaptive routers
    # may be added later via `/config/reload`, and the flusher is a no-op when
    # `llm_router.adaptive_routers` is empty. Per-router DB state is loaded
    # lazily by the flusher on first tick (see `_state_loaded` flag) so
    # hot-reloaded routers also get their persisted priors.
    if llm_router is not None and getattr(llm_router, "adaptive_routers", None):
        for _tagged_routers in llm_router.adaptive_routers.values():
            for _tagged in _tagged_routers:
                await _tagged.strategy.load_state_from_db(prisma_client)
                _tagged.strategy._state_loaded = True
    asyncio.create_task(_adaptive_router_flusher_loop())

    ## [Optional] Initialize dd tracer
    ProxyStartupEvent._init_dd_tracer()

    ## [Optional] Initialize Pyroscope continuous profiling (env: LITELLM_ENABLE_PYROSCOPE=true)
    ProxyStartupEvent._init_pyroscope()

    ## Initialize shared aiohttp session for connection reuse
    shared_aiohttp_session = await _initialize_shared_aiohttp_session()

    # End of startup event
    yield

    # Shutdown event - drain in-flight requests before tearing down dependencies
    # so SIGTERM (rolling update, scale-down, liveness kill) doesn't drop them.
    GracefulShutdownManager.start_shutdown()
    await GracefulShutdownManager.wait_for_drain()

    # Shutdown event - close shared aiohttp session
    if shared_aiohttp_session is not None:
        try:
            await shared_aiohttp_session.close()
            verbose_proxy_logger.info("SESSION REUSE: Closed shared aiohttp session")
        except Exception as e:
            verbose_proxy_logger.error(f"Error closing shared aiohttp session: {e}")

    # Shutdown event - stop RDS IAM token refresh background task
    if (
        prisma_client is not None
        and hasattr(prisma_client, "db")
        and hasattr(prisma_client.db, "stop_token_refresh_task")
    ):
        try:
            await prisma_client.db.stop_token_refresh_task()
        except Exception as e:
            verbose_proxy_logger.error(f"Error stopping token refresh task: {e}")

    # Shutdown event - stop Prisma DB health watchdog task
    if prisma_client is not None and hasattr(prisma_client, "stop_db_health_watchdog_task"):
        try:
            await prisma_client.stop_db_health_watchdog_task()
        except Exception as e:
            verbose_proxy_logger.error(f"Error stopping DB health watchdog task: {e}")

    await proxy_shutdown_event()  # type: ignore[reportGeneralTypeIssues]


def _generate_stable_operation_id(route: Any) -> str:
    operation_id = re.sub(r"\W", "_", f"{route.name}{route.path_format}")
    route_methods = sorted(route.methods or [])
    if len(route_methods) == 1:
        operation_id = f"{operation_id}_{route_methods[0].lower()}"
    return operation_id


_OPENAPI_HTTP_METHODS = {
    "delete",
    "get",
    "head",
    "options",
    "patch",
    "post",
    "put",
    "trace",
}


# Credentials surfaced by `/get/config/callbacks` in the alerting block: the
# full Slack incoming-webhook URL is itself a credential, and the SMTP
# password is a service password. Masked on read so plaintext never reaches
# the UI. Kept here at module scope to match the analogous descriptor
# `is_secret` flags in litellm.proxy.config_resolvers and the
# `_CACHE_SENSITIVE_FIELDS` constant in the cache endpoint file.
_ALERTING_SENSITIVE_VARS: Set[str] = {"SLACK_WEBHOOK_URL", "SMTP_PASSWORD"}


def _strip_operation_id_method_suffix(operation_id: str) -> str:
    base, separator, suffix = operation_id.rpartition("_")
    if separator and suffix in _OPENAPI_HTTP_METHODS:
        return base
    return operation_id


def ensure_unique_openapi_operation_ids(
    openapi_schema: Dict[str, Any],
    reserved_operation_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    operation_entries = []
    operation_id_counts: Dict[str, int] = {}
    for path_item in openapi_schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in _OPENAPI_HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str):
                continue
            operation_entries.append((method, operation, operation_id))
            operation_id_counts[operation_id] = operation_id_counts.get(operation_id, 0) + 1

    used_operation_ids = set(reserved_operation_ids or set())
    seen_operation_ids: Set[str] = set()
    for method, operation, operation_id in operation_entries:
        should_rewrite = (
            operation_id_counts[operation_id] > 1
            or operation_id in used_operation_ids
            or operation_id in seen_operation_ids
        )
        if not should_rewrite:
            seen_operation_ids.add(operation_id)
            used_operation_ids.add(operation_id)
            continue

        base_operation_id = _strip_operation_id_method_suffix(operation_id)
        new_operation_id = f"{base_operation_id}_{method}"
        suffix = 2
        while new_operation_id in used_operation_ids or new_operation_id in seen_operation_ids:
            new_operation_id = f"{base_operation_id}_{method}_{suffix}"
            suffix += 1
        operation["operationId"] = new_operation_id
        seen_operation_ids.add(new_operation_id)
        used_operation_ids.add(new_operation_id)

    if reserved_operation_ids is not None:
        reserved_operation_ids.update(used_operation_ids)

    return openapi_schema


app = FastAPI(
    docs_url=_get_docs_url(),
    redoc_url=_get_redoc_url(),
    openapi_url=_get_openapi_url(),
    title=_title,
    description=_description,
    version=version,
    root_path=server_root_path,
    lifespan=proxy_startup_event,  # type: ignore[reportGeneralTypeIssues]
    generate_unique_id_function=_generate_stable_operation_id,
    strict_content_type=False,
)

## V2 OTEL: instrument the FastAPI app for server spans (gated by
## LITELLM_OTEL_V2). This MUST run at app-creation time — once the lifespan runs,
## the middleware stack is frozen and ``instrument_app`` raises "Cannot add
## middleware after an application has started". See
## ``litellm.integrations.otel.mount`` for the full rationale; the call is a safe
## no-op when the gate is off or the instrumentation package is unavailable.
from litellm.integrations.otel.mount import instrument_fastapi_app

instrument_fastapi_app(app)

vertex_live_passthrough_vertex_base = VertexBase()


### CUSTOM API DOCS [ENTERPRISE FEATURE] ###
# Custom OpenAPI schema generator to include only selected routes
from fastapi.routing import APIWebSocketRoute


def _inject_websocket_stubs_into_openapi_schema(openapi_schema: dict, websocket_routes: list) -> dict:
    """
    Add a synthetic GET stub for each WebSocket route so it appears in Swagger UI.

    Merges into any existing path entry rather than replacing it — a WebSocket route
    that shares its path with an HTTP route must not erase the HTTP operation. If
    a "get" operation is already documented on the path, the WebSocket stub is
    skipped to preserve the real GET.
    """
    for route in websocket_routes:
        base_path = route.path.split("{")[0].rstrip("?")

        parameters = []
        try:
            if hasattr(route, "dependant") and route.dependant is not None:
                # Handle both FastAPI <0.120 and >=0.120
                query_params = getattr(route.dependant, "query_params", [])
                if query_params:
                    for param in query_params:
                        parameters.append(
                            {
                                "name": param.name,
                                "in": "query",
                                "required": param.required,
                                "schema": {"type": "string"},
                            }
                        )
        except (AttributeError, TypeError):
            pass

        path_entry = openapi_schema["paths"].setdefault(base_path, {})
        if "get" not in path_entry:
            path_entry["get"] = {
                "summary": f"WebSocket: {route.name or base_path}",
                "description": "WebSocket connection endpoint",
                "operationId": f"websocket_{route.name or base_path.replace('/', '_')}",
                "parameters": parameters,
                "responses": {"101": {"description": "WebSocket Protocol Switched"}},
                "tags": ["WebSocket"],
            }

    return openapi_schema


def get_openapi_schema():
    if app.openapi_schema:
        return app.openapi_schema

    # Use compatibility wrapper for FastAPI 0.120+ schema generation
    from litellm.proxy.common_utils.openapi_schema_compat import (
        get_openapi_schema_with_compat,
    )

    openapi_schema = get_openapi_schema_with_compat(
        get_openapi_func=get_openapi,
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Find all WebSocket routes
    websocket_routes = [route for route in app.routes if isinstance(route, APIWebSocketRoute)]

    # Add a synthetic GET stub for each so they render in Swagger UI,
    # without clobbering existing HTTP operations on the same path.
    openapi_schema = _inject_websocket_stubs_into_openapi_schema(openapi_schema, websocket_routes)

    # Add LLM API request schema bodies for documentation
    from litellm.proxy.common_utils.custom_openapi_spec import CustomOpenAPISpec

    openapi_schema = CustomOpenAPISpec.add_llm_api_request_schema_body(openapi_schema)

    # Stub unloaded lazy features so they appear as Swagger sections.
    from litellm.proxy._lazy_features import inject_lazy_stubs

    openapi_schema = inject_lazy_stubs(openapi_schema)
    openapi_schema = ensure_unique_openapi_operation_ids(openapi_schema)

    # Fix Swagger UI execute path error when server_root_path is set
    if server_root_path:
        openapi_schema["servers"] = [{"url": "/" + server_root_path.strip("/")}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi_schema()

    # Filter routes to include only specific ones
    openai_routes = LiteLLMRoutes.openai_routes.value
    paths_to_include: dict = {}
    for route in openai_routes:
        if route in openapi_schema["paths"]:
            paths_to_include[route] = openapi_schema["paths"][route]
    openapi_schema["paths"] = paths_to_include

    # Add LLM API request schema bodies for documentation
    from litellm.proxy.common_utils.custom_openapi_spec import CustomOpenAPISpec

    openapi_schema = CustomOpenAPISpec.add_llm_api_request_schema_body(openapi_schema)

    # Stub unloaded lazy features so they appear as Swagger sections.
    from litellm.proxy._lazy_features import inject_lazy_stubs

    openapi_schema = inject_lazy_stubs(openapi_schema)
    openapi_schema = ensure_unique_openapi_operation_ids(openapi_schema)

    # Fix Swagger UI execute path error when server_root_path is set
    if server_root_path:
        openapi_schema["servers"] = [{"url": "/" + server_root_path.strip("/")}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


if os.getenv("DOCS_FILTERED", "False") == "True" and premium_user:
    app.openapi = custom_openapi  # type: ignore
else:
    # For regular users, use get_openapi_schema to include LLM API schemas
    app.openapi = get_openapi_schema  # type: ignore


class UserAPIKeyCacheTTLEnum(enum.Enum):
    in_memory_cache_ttl = 60  # 1 min ttl ## configure via `general_settings::user_api_key_cache_ttl: <your-value>`


@app.exception_handler(ProxyException)
async def openai_exception_handler(request: Request, exc: ProxyException):
    # NOTE: DO NOT MODIFY THIS, its crucial to map to Openai exceptions
    headers = exc.headers
    error_dict = exc.to_dict()
    status_code = int(exc.code) if exc.code else status.HTTP_500_INTERNAL_SERVER_ERROR
    _close_dangling_otel_server_span(request, status_code, exc=exc)
    return JSONResponse(
        status_code=status_code,
        content={"error": error_dict},
        headers=headers,
    )


def _close_dangling_otel_server_span(request: Request, status_code: int, exc: Optional[Exception] = None) -> None:
    parent_otel_span = getattr(request.state, "parent_otel_span", None)
    if parent_otel_span is None:
        return
    if open_telemetry_logger is None:
        return
    # Under OTel V2 the FastAPI instrumentor owns the server span (parent_otel_span
    # is that same span) and ends it itself with the http.* attributes stamped on
    # completion. The instrumentor only records an error when the exception reaches
    # it uncaught, but these handlers swallow it into a JSONResponse, so it never
    # does; stamp the error.* attributes here (without ending or re-statusing the
    # span, which the instrumentor still owns) so pre-call failures carry the error
    # like v1 did. Otherwise close and annotate the dangling span ourselves.
    try:
        from litellm.integrations.otel.model.config import is_otel_v2_enabled

        v2_enabled = is_otel_v2_enabled()
    except Exception:
        v2_enabled = False
    try:
        from opentelemetry.trace import Status, StatusCode

        if v2_enabled:
            if status_code >= 400:
                open_telemetry_logger.record_error_attributes_on_span(parent_otel_span, exc, status_code)
            return
        open_telemetry_logger.set_response_status_code_attribute(parent_otel_span, status_code)
        if status_code >= 400:
            open_telemetry_logger.record_error_attributes_on_span(parent_otel_span, exc, status_code)
        parent_otel_span.set_status(Status(StatusCode.ERROR if status_code >= 400 else StatusCode.OK))
        parent_otel_span.end()
    except Exception as e:
        verbose_proxy_logger.debug("Error closing dangling OTEL SERVER span: %s", str(e))
    finally:
        if not v2_enabled:
            request.state.parent_otel_span = None


@app.exception_handler(RequestValidationError)
async def otel_request_validation_exception_handler(request: Request, exc: RequestValidationError):
    _close_dangling_otel_server_span(request, 422, exc=exc)
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(Exception)
async def otel_unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, (ProxyException, HTTPException, RequestValidationError)):
        raise exc
    verbose_proxy_logger.exception("Unhandled exception in request: %s", type(exc).__name__)
    _close_dangling_otel_server_span(request, 500, exc=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "internal_server_error",
            }
        },
    )


router = APIRouter()


def _get_cors_config(
    cors_origins_env: Optional[str] = None,
    cors_credentials_env: Optional[str] = None,
):
    """
    Compute CORS allowed origins and credentials flag from environment variables.

    Extracted into a function so it can be unit-tested without reloading the module.

    Args:
        cors_origins_env: Value of LITELLM_CORS_ORIGINS (defaults to os.getenv).
        cors_credentials_env: Value of LITELLM_CORS_ALLOW_CREDENTIALS (defaults to os.getenv).

    Returns:
        Tuple[List[str], bool]: (origins, allow_credentials)
    """
    _origins_raw = cors_origins_env if cors_origins_env is not None else os.getenv("LITELLM_CORS_ORIGINS")
    if _origins_raw is None or _origins_raw.strip() == "":
        computed_origins = ["*"]
    else:
        computed_origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]

    # Disable credentials by default when wildcard origins are used — combining
    # allow_origins=["*"] with allow_credentials=True causes Starlette to reflect
    # the incoming Origin header, allowing any site to make credentialed requests.
    # Set LITELLM_CORS_ALLOW_CREDENTIALS=true to explicitly restore the old behaviour
    # (e.g. for non-browser clients that relied on the Access-Control-Allow-Credentials
    # header being present regardless of origin).
    _credentials_raw = (
        cors_credentials_env if cors_credentials_env is not None else os.getenv("LITELLM_CORS_ALLOW_CREDENTIALS")
    )
    if _credentials_raw is not None:
        computed_credentials = _credentials_raw.strip().lower() == "true"
    else:
        computed_credentials = "*" not in computed_origins

    return computed_origins, computed_credentials


origins, allow_cors_credentials = _get_cors_config()


# get current directory
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    packaged_ui_path = os.path.join(current_dir, "_experimental", "out")
    ui_path = packaged_ui_path
    litellm_asset_prefix = "/litellm-asset-prefix"

    def _dir_has_content(path: str) -> bool:
        try:
            return os.path.isdir(path) and any(os.scandir(path))
        except FileNotFoundError:
            return False

    def _validate_ui_directory(ui_path: str) -> bool:
        """
        Verify UI directory has minimum required structure.

        Checks for:
        - Directory exists
        - Has index.html (main entry point)
        - Has _next directory (Next.js assets)

        Returns True if UI directory appears valid and servable.
        """
        if not os.path.isdir(ui_path):
            return False

        # Must have main index.html
        if not os.path.exists(os.path.join(ui_path, "index.html")):
            return False

        # Must have _next directory with Next.js assets
        next_dir = os.path.join(ui_path, "_next")
        if not os.path.isdir(next_dir):
            return False

        return True

    def _is_ui_pre_restructured(ui_dir: str) -> bool:
        """
        Detect if UI directory is already pre-restructured and ready to serve.

        Returns True if:
        1. Marker file .litellm_ui_ready exists (created by Dockerfile), OR
        2. Restructuring pattern detected (subdirectories with index.html inside)

        This allows skipping copy/restructure operations on read-only filesystems.
        """
        if not os.path.isdir(ui_dir):
            return False

        # Primary signal: marker file created by Dockerfile
        marker_file = os.path.join(ui_dir, ".litellm_ui_ready")
        if os.path.exists(marker_file):
            verbose_proxy_logger.debug(f"Found UI ready marker: {marker_file}")
            return True

        # Fallback signal: Detect restructuring pattern
        # After restructuring, routes exist as directories with index.html inside
        # (e.g., login/index.html instead of login.html)
        # Check for main index.html first (basic UI structure requirement)
        if not os.path.exists(os.path.join(ui_dir, "index.html")):
            return False

        # Look for ANY subdirectory with index.html (proves restructuring happened)
        # Ignore directories starting with _ (Next.js internals like _next)
        try:
            for entry in os.scandir(ui_dir):
                if entry.is_dir() and not entry.name.startswith("_"):
                    index_path = os.path.join(entry.path, "index.html")
                    if os.path.exists(index_path):
                        # Found at least one restructured route - this proves the pattern
                        verbose_proxy_logger.debug(
                            f"Detected restructured UI via pattern: found {entry.name}/index.html"
                        )
                        return True
        except (PermissionError, OSError) as e:
            verbose_proxy_logger.debug(f"Could not scan {ui_dir} for restructuring detection: {e}")
            return False

        # No restructured routes found
        return False

    def _try_populate_ui_directory(source_path: str, target_path: str) -> tuple[bool, str]:
        """
        Attempt to populate target UI directory from source.

        Returns: (success: bool, error_message: str)
        """
        try:
            os.makedirs(target_path, exist_ok=True)
            if not _dir_has_content(target_path) and _dir_has_content(source_path):
                shutil.copytree(
                    source_path,
                    target_path,
                    dirs_exist_ok=True,
                )
                verbose_proxy_logger.info(f"Successfully populated UI at {target_path}")
                return True, ""
            else:
                return False, "Source or target directory state invalid"
        except (PermissionError, OSError) as e:
            return False, str(e)

    # Use a writable runtime UI directory whenever possible.
    # This prevents mutating the packaged UI directory (e.g. site-packages or the repo checkout)
    # and ensures extensionless routes like /ui/login work via <route>/index.html.
    is_non_root = os.getenv("LITELLM_NON_ROOT", "").lower() == "true"

    # Determine runtime UI path
    # Priority: LITELLM_UI_PATH env var > default path based on is_non_root
    if is_non_root:
        default_runtime_ui_path = "/var/lib/litellm/ui"
    else:
        default_runtime_ui_path = packaged_ui_path

    runtime_ui_path = os.getenv("LITELLM_UI_PATH", default_runtime_ui_path)

    # Validate packaged UI before proceeding
    if not _validate_ui_directory(packaged_ui_path):
        verbose_proxy_logger.error(
            f"Packaged UI at {packaged_ui_path} is invalid or incomplete. UI may not function correctly."
        )

    # Decision tree for UI path selection:
    # 1. If runtime path == packaged path: use packaged UI directly
    # 2. If runtime UI exists and is pre-restructured: use it
    # 3. If runtime UI exists but not restructured: use it (will restructure later)
    # 4. If runtime UI missing: try to populate from packaged UI
    #    4a. If population succeeds: use runtime UI
    #    4b. If population fails: fall back to packaged UI

    should_use_runtime_path = runtime_ui_path != packaged_ui_path

    if should_use_runtime_path:
        is_pre_restructured = _is_ui_pre_restructured(runtime_ui_path)
        has_content = _dir_has_content(runtime_ui_path)

        # Case 2: Runtime UI exists and is ready
        if has_content and is_pre_restructured:
            verbose_proxy_logger.info(f"Using pre-restructured UI at {runtime_ui_path}")
            ui_path = runtime_ui_path

        # Case 3: Runtime UI exists but needs restructuring
        elif has_content and not is_pre_restructured:
            verbose_proxy_logger.warning(
                f"UI at {runtime_ui_path} has content but is not properly restructured. "
                f"Will attempt to restructure in place."
            )
            ui_path = runtime_ui_path

        # Case 4: Runtime UI missing - try to populate
        else:
            verbose_proxy_logger.info(f"UI not found at {runtime_ui_path}. Attempting to populate from packaged UI.")

            success, error = _try_populate_ui_directory(packaged_ui_path, runtime_ui_path)

            if success:
                # Case 4a: Population succeeded
                ui_path = runtime_ui_path
            else:
                # Case 4b: Population failed - fall back to packaged UI
                verbose_proxy_logger.warning(
                    f"Failed to populate UI at {runtime_ui_path}: {error}. "
                    f"Falling back to packaged UI at {packaged_ui_path}. "
                    f"For read-only deployments, pre-build UI in Dockerfile "
                    f"or set LITELLM_UI_PATH to a writable emptyDir volume."
                )
                ui_path = packaged_ui_path
    else:
        # Case 1: Using packaged UI directly (local development)
        verbose_proxy_logger.info(f"Using packaged UI directory: {packaged_ui_path}")
        ui_path = packaged_ui_path

    # Validate final UI path
    if not _validate_ui_directory(ui_path):
        verbose_proxy_logger.error(f"Selected UI path {ui_path} is invalid or incomplete. UI may not work correctly.")

    # Only modify files if a custom server root path is set AND filesystem is writable
    if server_root_path and server_root_path != "/":
        # Check if UI path is writable
        is_writable = os.access(ui_path, os.W_OK)

        if not is_writable:
            verbose_proxy_logger.warning(
                f"Cannot apply server_root_path replacements to UI at {ui_path}: "
                f"path is not writable. Ensure server_root_path is '/' or pre-process "
                f"UI files in Dockerfile with custom server_root_path."
            )
        else:
            # Iterate through files in the UI directory
            for root, dirs, files in os.walk(ui_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    # Skip binary files and files that don't need path replacement
                    if filename.endswith(
                        (
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".gif",
                            ".ico",
                            ".woff",
                            ".woff2",
                            ".ttf",
                            ".eot",
                        )
                    ):
                        continue
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                        # Replace the asset prefix with the server root path
                        modified_content = content.replace(
                            f"{litellm_asset_prefix}",
                            f"{server_root_path}",
                        )

                        # Replace the /.well-known/litellm-ui-config with the server root path
                        modified_content = modified_content.replace(
                            "/litellm/.well-known/litellm-ui-config",
                            f"{server_root_path}/.well-known/litellm-ui-config",
                        )

                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(modified_content)
                    except (UnicodeDecodeError, PermissionError, OSError):
                        # Skip binary files or files we can't write to
                        continue

    # # Mount the _next directory at the root level
    app.mount(
        "/_next",
        StaticFiles(directory=os.path.join(ui_path, "_next")),
        name="next_static",
    )
    app.mount(
        f"{litellm_asset_prefix}/_next",
        StaticFiles(directory=os.path.join(ui_path, "_next")),
        name="next_static",
    )
    # print(f"mounted _next at {server_root_path}/ui/_next")

    app.mount("/ui", StaticFiles(directory=ui_path, html=True), name="ui")

    def _restructure_ui_html_files(ui_root: str) -> None:
        """Ensure each exported HTML route is available as <route>/index.html."""

        for current_root, _, files in os.walk(ui_root):
            rel_root = os.path.relpath(current_root, ui_root)
            first_segment = "" if rel_root == "." else rel_root.split(os.sep)[0]

            # Ignore Next.js asset directories
            if first_segment in {"_next", "litellm-asset-prefix"}:
                continue

            for filename in files:
                if not filename.endswith(".html") or filename == "index.html":
                    continue

                file_path = os.path.join(current_root, filename)
                target_dir = os.path.splitext(file_path)[0]
                target_path = os.path.join(target_dir, "index.html")

                os.makedirs(target_dir, exist_ok=True)
                try:
                    os.replace(file_path, target_path)
                except FileNotFoundError:
                    # Another process may have already moved this file.
                    continue

    # Handle HTML file restructuring
    # Only restructure if:
    # 1. UI is not already pre-restructured
    # 2. Filesystem is writable
    try:
        is_pre_restructured = _is_ui_pre_restructured(ui_path)
        is_writable = os.access(ui_path, os.W_OK)

        if is_pre_restructured:
            verbose_proxy_logger.info(f"Skipping UI restructuring: {ui_path} is already pre-restructured")
        elif not is_writable:
            verbose_proxy_logger.warning(
                f"Cannot restructure UI at {ui_path}: path is not writable. "
                f"UI may not work correctly for extensionless routes. "
                f"Pre-build and restructure UI in Dockerfile for read-only deployments."
            )
        else:
            _restructure_ui_html_files(ui_path)
            verbose_proxy_logger.info(f"Restructured UI directory: {ui_path}")
    except PermissionError as e:
        verbose_proxy_logger.exception(f"Permission error while restructuring UI directory {ui_path}: {e}")
    except Exception as e:
        verbose_proxy_logger.exception(f"Error while restructuring UI directory {ui_path}: {e}")

except Exception:
    pass
current_dir = os.path.dirname(os.path.abspath(__file__))
# ui_path = os.path.join(current_dir, "_experimental", "out")
# # Mount this test directory instead
# app.mount("/ui", StaticFiles(directory=ui_path, html=True), name="ui")


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=LITELLM_UI_ALLOW_HEADERS,
)

app.add_middleware(PrometheusAuthMiddleware)
# Added before InFlightRequestsMiddleware so it nests *inside* it: Starlette
# makes the last-added middleware outermost. The billable count is recorded
# after the inner app returns, so if this sat outside the in-flight tracker a
# request could be counted as drained while its record() had not yet run, and
# proxy_shutdown_event could flush and stop the exporter underneath it.
app.add_middleware(
    BillableRequestMetricsMiddleware,
    # Factory, not an instance: the recorder is resolved on the first request so
    # it sees premium_user and the billing env vars AFTER proxy_startup_event has
    # loaded the YAML config's environment_variables. Building it here at import
    # time would permanently capture recorder=None for YAML-configured
    # deployments. The lambda reads the module globals at call time.
    recorder_factory=lambda: (
        build_billing_metrics_recorder(
            premium=premium_user,
            # Read from the license check, not the premium_user_data module
            # global: that global is bound once at import and goes stale when
            # the license arrives via the YAML config's environment_variables.
            license_data=_license_check.airgapped_license_data,
            litellm_version=version,
        )
        if build_billing_metrics_recorder is not None
        else None
    ),
)
app.add_middleware(InFlightRequestsMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


def mount_swagger_ui():
    swagger_directory = os.path.join(current_dir, "swagger")
    swagger_path = "/" if server_root_path is None else server_root_path
    if not swagger_path.endswith("/"):
        swagger_path = swagger_path + "/"
    custom_root_path_swagger_path = swagger_path + "swagger"

    app.mount("/swagger", StaticFiles(directory=swagger_directory), name="swagger")

    # On dropdown expand: one-time fetch to the prefix (triggers lazy load),
    # then spec re-download so real routes replace the stub. Raw JS (no
    # <script> tag) since it's injected inside the existing inline script.
    from fastapi.responses import HTMLResponse

    from litellm.proxy._lazy_features import lazy_tag_to_prefix

    _lazy_plugin_js = (
        "const TAG_TO_PREFIX = " + json.dumps(lazy_tag_to_prefix()) + ";"
        "const warmedTags = new Set();"
        "const LAZY_TAGS = new Set(Object.keys(TAG_TO_PREFIX));"
        "const hideStubRows = () => {"
        "document.querySelectorAll('.opblock').forEach(op => {"
        "const d = op.querySelector('.opblock-summary-description');"
        "if (d && LAZY_TAGS.has(d.textContent.trim())) op.style.display = 'none';"
        "});};"
        "const annotateLazyHeaders = () => {"
        "document.querySelectorAll('.opblock-tag').forEach(tagEl => {"
        "const m = (tagEl.id || '').match(/^operations-tag-(.+)$/);"
        "if (!m || !LAZY_TAGS.has(m[1])) return;"
        "const existing = tagEl.querySelector('.lazy-load-hint');"
        "if (warmedTags.has(m[1])) { if (existing) existing.remove(); return; }"
        "if (existing) return;"
        "const hint = document.createElement('small');"
        "hint.className = 'lazy-load-hint';"
        "hint.textContent = ' (expand to load routes)';"
        "hint.style.opacity = '0.6';"
        "hint.style.marginLeft = '6px';"
        "const target = tagEl.querySelector('a span') || tagEl.querySelector('span') || tagEl;"
        "target.appendChild(hint);"
        "});};"
        "setInterval(() => { hideStubRows(); annotateLazyHeaders(); }, 200);"
        "const LazyLoadPlugin = () => ({"
        "afterLoad:function(system){setTimeout(()=>{"
        "for(const tag of LAZY_TAGS)system.layoutActions.show(['operations-tag',tag],false);"
        "},200);},"
        "statePlugins:{layout:{wrapActions:{show:(ori,sys)=>(...args)=>{"
        "const thing=args[0];const shown=args[1];let tag=null;"
        "if(Array.isArray(thing)){for(const t of thing)if(TAG_TO_PREFIX[t])tag=t;}"
        "if(shown!==false&&tag&&!warmedTags.has(tag)){warmedTags.add(tag);"
        "fetch('/lazy/warm/'+tag,{method:'POST',credentials:'include'}).then(r=>r.json()).then(d=>{"
        "if(!d.paths||Object.keys(d.paths).length===0)return;"
        "const cur=sys.specSelectors.specJson().toJS();"
        "const merged={};let inserted=false;"
        "for(const k in (cur.paths||{})){"
        "if(k===d.stub_path){for(const nk in d.paths)merged[nk]=d.paths[nk];inserted=true;}"
        "else{merged[k]=cur.paths[k];}}"
        "if(!inserted)Object.assign(merged,d.paths);"
        "cur.paths=merged;"
        "cur.components=cur.components||{};"
        "cur.components.schemas=Object.assign(cur.components.schemas||{},(d.components||{}).schemas||{});"
        "sys.specActions.updateSpec(JSON.stringify(cur));"
        "}).catch(()=>{});}"
        "return ori(...args);}}}}});"
    )

    def swagger_monkey_patch(*args, **kwargs):
        response = get_swagger_ui_html(
            *args,
            **kwargs,
            swagger_js_url=f"{custom_root_path_swagger_path}/swagger-ui-bundle.js",
            swagger_css_url=f"{custom_root_path_swagger_path}/swagger-ui.css",
            swagger_favicon_url=f"{custom_root_path_swagger_path}/favicon.png",
        )
        body = response.body.decode("utf-8")
        body = body.replace(
            "const ui = SwaggerUIBundle({",
            _lazy_plugin_js + 'const ui = SwaggerUIBundle({plugins:[LazyLoadPlugin],tagsSorter:"alpha",',
            1,
        )
        return HTMLResponse(content=body)

    applications.get_swagger_ui_html = swagger_monkey_patch


mount_swagger_ui()

docs_url = _get_docs_url()
root_redirect_url: Optional[str] = os.getenv("ROOT_REDIRECT_URL")
if docs_url != "/" and root_redirect_url is not None:

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url=root_redirect_url)  # type: ignore[arg-type]


from typing import Dict

user_api_base = None
user_model = None
user_debug = False
user_max_tokens = None
user_request_timeout = None
user_temperature = None
user_telemetry = True
user_config = None
user_headers = None
user_config_file_path: Optional[str] = None
local_logging = True  # writes logs to a local api_log.json file for debugging
experimental = False
#### GLOBAL VARIABLES ####
llm_router: Optional[Router] = None
llm_model_list: Optional[list] = None
general_settings: dict = {}
config_passthrough_endpoints: Optional[List[Dict[str, Any]]] = None
log_file = "api_log.json"
worker_config = None
master_key: Optional[str] = None
config_agents: Optional[List[AgentConfig]] = None
otel_logging = False
prisma_client: Optional[PrismaClient] = None
shared_aiohttp_session: Optional["ClientSession"] = None  # Global shared session for connection reuse
user_api_key_cache: UserApiKeyCache = UserApiKeyCache(
    default_in_memory_ttl=UserAPIKeyCacheTTLEnum.in_memory_cache_ttl.value
)
spend_counter_cache = DualCache(default_in_memory_ttl=UserAPIKeyCacheTTLEnum.in_memory_cache_ttl.value)
cli_sso_session_cache = DualCache(default_in_memory_ttl=CLI_SSO_SESSION_TTL_SECONDS)
model_max_budget_limiter = _PROXY_VirtualKeyModelMaxBudgetLimiter(dual_cache=user_api_key_cache)
litellm.logging_callback_manager.add_litellm_callback(model_max_budget_limiter)
redis_usage_cache: Optional[RedisCache] = None  # redis cache used for tracking spend, tpm/rpm limits
polling_via_cache_enabled: Union[Literal["all"], List[str], bool] = False
native_background_mode: List[str] = []  # Models that should use native provider background mode instead of polling
polling_cache_ttl: int = 3600  # Default 1 hour TTL for polling cache
user_custom_auth = None
user_custom_key_generate = None
# Sentinel: prevents PKCE-no-Redis advisory from re-logging on config hot-reload.
# Tests that need to reset it can patch 'litellm.proxy.proxy_server._pkce_no_redis_warning_emitted'.
_pkce_no_redis_warning_emitted: bool = False
_cp_no_redis_warning_emitted: bool = False
user_custom_key_update = None
user_custom_sso = None
user_custom_ui_sso_sign_in_handler = None
use_background_health_checks = None
use_shared_health_check = None
use_queue = False
health_check_interval = None
health_check_concurrency = None
health_check_details = None
health_check_results: Dict[str, Union[int, List[Dict[str, Any]]]] = {}
background_health_check_loop_active = False
background_health_check_cycle_seq = 0
queue: List = []
litellm_proxy_budget_name = LITELLM_PROXY_BUDGET_NAME
litellm_proxy_admin_name = LITELLM_PROXY_ADMIN_NAME
ui_access_mode: Union[Literal["admin", "all"], Dict] = "all"
proxy_budget_rescheduler_min_time = PROXY_BUDGET_RESCHEDULER_MIN_TIME
proxy_budget_rescheduler_max_time = PROXY_BUDGET_RESCHEDULER_MAX_TIME
proxy_batch_polling_interval = PROXY_BATCH_POLLING_INTERVAL
proxy_batch_write_at = PROXY_BATCH_WRITE_AT
proxy_config_reload_interval_seconds = PROXY_CONFIG_RELOAD_INTERVAL_SECONDS
litellm_master_key_hash = None
disable_spend_logs = False
jwt_handler = JWTHandler()
prompt_injection_detection_obj: Optional[_OPTIONAL_PromptInjectionDetection] = None
store_model_in_db: bool = False
open_telemetry_logger: Optional[OpenTelemetry] = None
### INITIALIZE GLOBAL LOGGING OBJECT ###
proxy_logging_obj: ProxyLogging = ProxyLogging(user_api_key_cache=user_api_key_cache, premium_user=premium_user)
### REDIS QUEUE ###
async_result = None
celery_app_conn = None
celery_fn = None  # Redis Queue for handling requests

# Global variables for model cost map reload scheduling
scheduler = None
last_model_cost_map_reload = None

# Global variable for anthropic beta headers reload scheduling
last_anthropic_beta_headers_reload = None


### DB WRITER ###
db_writer_client: Optional[AsyncHTTPHandler] = None
### logger ###


def _resolve_typed_dict_type(typ):
    """Resolve the actual TypedDict class from a potentially wrapped type."""
    from typing_extensions import _TypedDictMeta  # type: ignore

    origin = get_origin(typ)
    if origin is Union:  # Check if it's a Union (like Optional)
        for arg in get_args(typ):
            if isinstance(arg, _TypedDictMeta):
                return arg
    elif isinstance(typ, type) and isinstance(typ, dict):
        return typ
    return None


def _resolve_pydantic_type(typ) -> List:
    """Resolve the actual TypedDict class from a potentially wrapped type."""
    origin = get_origin(typ)
    typs = []
    if origin is Union:  # Check if it's a Union (like Optional)
        for arg in get_args(typ):
            if arg is not None and not isinstance(arg, type(None)) and "NoneType" not in str(arg):
                typs.append(arg)
    elif isinstance(typ, type) and isinstance(typ, BaseModel):
        return [typ]
    return typs


def load_from_azure_key_vault(use_azure_key_vault: bool = False):
    if use_azure_key_vault is False:
        return

    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        # Set your Azure Key Vault URI
        KVUri = os.getenv("AZURE_KEY_VAULT_URI", None)

        if KVUri is None:
            raise Exception("Error when loading keys from Azure Key Vault: AZURE_KEY_VAULT_URI is not set.")

        credential = DefaultAzureCredential()

        # Create the SecretClient using the credential
        client = SecretClient(vault_url=KVUri, credential=credential)

        litellm.secret_manager_client = client
        litellm._key_management_system = KeyManagementSystem.AZURE_KEY_VAULT
    except Exception as e:
        _error_str = str(e)
        verbose_proxy_logger.exception(
            "Error when loading keys from Azure Key Vault: %s .Ensure you run `pip install azure-identity azure-keyvault-secrets`",
            _error_str,
        )


def cost_tracking():
    global prisma_client
    if prisma_client is not None:
        litellm.logging_callback_manager.add_litellm_callback(_ProxyDBLogger())
        litellm.logging_callback_manager.add_litellm_async_success_callback(_ProxyDBLogger())


# Bounds authoritative DB re-reads when enforcing a budget against a
# stale-low spend counter: at most one DB read per counter per window.
SPEND_DB_FLOOR_CACHE_TTL_SECONDS = 5


def _fail_closed_budget_enforcement() -> bool:
    return general_settings.get("fail_closed_budget_enforcement") is True


def _raise_budget_unverifiable(counter_key: str) -> None:
    verbose_proxy_logger.warning(
        "fail_closed_budget_enforcement: rejecting request — spend for %s could "
        "not be verified against Redis or the database",
        counter_key,
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": (
                "Budget enforcement unavailable: current spend could not be "
                "verified against Redis or the database, and "
                "fail_closed_budget_enforcement is enabled, so the request was "
                "rejected to avoid exceeding the configured budget. Retry shortly."
            )
        },
    )


async def get_current_spend(
    counter_key: str,
    fallback_spend: float,
    max_budget: float | None = None,
    window_entity_type: str | None = None,
    window_entity_id: str | None = None,
    window_start: datetime | None = None,
    fallback_authoritative: bool = False,
) -> float:
    """
    Read current spend from the cross-pod spend counter.

    Reads Redis FIRST (authoritative cross-pod value), not DualCache's
    async_get_cache which returns in-memory first. This is critical:
    DualCache.async_get_cache returns stale per-pod values because each
    pod's in-memory cache is only updated by that pod's own increments.

    Fallback chain:
    1. Redis counter (cross-pod, authoritative)
    2. In-memory counter (single-instance or Redis failure)
    3. Reseed from authoritative DB spend (counter expired, cross-pod stale)
    4. Caller-supplied fallback (DB unavailable, cold start)

    When ``max_budget`` is supplied, the counter is re-checked against the
    authoritative recorded spend before a request is admitted. A Redis counter
    that survived a Redis restart can return a stale-low value loaded from an
    older RDB snapshot; that read is a hit (not a clean miss), so step 3 never
    runs and a key can leak spend past ``max_budget`` indefinitely. The
    authoritative source depends on the counter: primary key/team/user/org
    counters read the DB row; per-window counters (``window_start`` supplied)
    aggregate spend logs; end-user/tag counters have no DB row, so the caller's
    ``fallback_spend`` (loaded fresh in auth) is authoritative. The DB read is
    skipped for healthy primary counters (counter at or above recorded spend)
    and cached in-process for a few seconds, so a persistently stale counter
    drives at most one read per counter per window rather than one per request.
    """
    current, verified = await _read_spend_counter_estimate(counter_key=counter_key, fallback_spend=fallback_spend)
    if fallback_authoritative:
        verified = True

    if max_budget is None or current >= max_budget:
        return current

    # Cheap staleness signal for primary counters: the counter reads below the
    # spend this caller already knows about. Window counters have no such signal
    # (fallback is 0), so they always re-check, bounded by the cache. Strict mode
    # (fail_closed_budget_enforcement) always re-checks against the authoritative
    # source too, so a counter that is stale-low at the same time as the caller's
    # cached spend cannot slip through; the 5s cache keeps that bounded.
    is_window = window_start is not None
    if fallback_spend > current or is_window or _fail_closed_budget_enforcement():
        authoritative = await _authoritative_floor_spend(
            counter_key=counter_key,
            window_entity_type=window_entity_type,
            window_entity_id=window_entity_id,
            window_start=window_start,
        )
        if authoritative is not None:
            verified = True
            if authoritative > current:
                await _repair_stale_spend_counter(counter_key=counter_key, db_spend=authoritative)
                return authoritative
        elif fallback_spend > current:
            # end-user / tag counters have no DB row; fallback_spend is the
            # authoritative recorded value loaded in auth.
            return fallback_spend

    # Opt-in hard guarantee: when the spend backing this admit decision came
    # only from a per-pod cache (Redis and DB both unreadable), reject rather
    # than admit on an unverifiable budget. No-op unless the flag is set, so
    # default behavior is unchanged.
    if not verified and _fail_closed_budget_enforcement():
        _raise_budget_unverifiable(counter_key)

    return current


async def _repair_stale_spend_counter(counter_key: str, db_spend: float) -> None:
    """Raise a counter that has fallen below the authoritative DB spend (e.g.
    Redis restarted and reloaded an older snapshot) so every worker reads the
    corrected value directly instead of re-deriving it per request, and so a
    worker whose own cached spend is also stale still sees the true total.

    The write is monotonic: it only ever raises the counter, so a repair that
    carries a slightly-stale DB total cannot clobber a concurrent increment that
    already pushed the counter higher (which would let racing requests
    under-count). Redis enforces this atomically via async_set_max; the
    in-memory copy is guarded by a read-compare-write with no await in between,
    so it is atomic within the worker.
    """
    cached = spend_counter_cache.in_memory_cache.get_cache(key=counter_key)
    needs_update = True
    if cached is not None:
        try:
            needs_update = float(cached) < db_spend
        except (TypeError, ValueError):
            needs_update = True
    if needs_update:
        spend_counter_cache.in_memory_cache.set_cache(key=counter_key, value=db_spend)
    if spend_counter_cache.redis_cache is not None:
        try:
            await spend_counter_cache.redis_cache.async_set_max(key=counter_key, value=db_spend)
        except Exception:
            verbose_proxy_logger.debug(
                "Unable to repair stale spend counter %s in Redis",
                counter_key,
                exc_info=True,
            )


async def reseed_spend_counter_from_db(counter_key: str) -> None:
    """Recover a counter that the reservation reconcile found in an inconsistent
    state (missing, or where applying the reconcile delta would drive it
    negative) by reseeding it from the DB instead of deleting it.

    The DB row is a LAGGING authoritative floor, not post-request truth: the
    entity .spend column is flushed in batches (every PROXY_BATCH_WRITE_AT), so
    it can exclude this request's just-recorded cost and other buffered spend.
    That is fine here: the monotonic set-max can only RAISE a stale-low counter
    toward that floor (never lowers it or clobbers a concurrent increment), and
    the read-time floor (_authoritative_floor_spend) converges to the true total
    as the buffer flushes. The point is to restore enforcement to a real floor
    rather than leave the counter deleted and unenforced (the prior fail-open).
    Counters with no DB row (window/end-user/tag) are left untouched rather than
    deleted, so enforcement keeps reading whatever value they hold.
    """
    db_spend = await SpendCounterReseed.from_db(prisma_client=prisma_client, counter_key=counter_key)
    if db_spend is None:
        return
    await _repair_stale_spend_counter(counter_key=counter_key, db_spend=db_spend)


async def _authoritative_floor_spend(
    counter_key: str,
    window_entity_type: str | None = None,
    window_entity_id: str | None = None,
    window_start: datetime | None = None,
) -> float | None:
    marker_key = f"spend_db_floor:{counter_key}"
    cached = spend_counter_cache.in_memory_cache.get_cache(key=marker_key)
    if cached is not None:
        return float(cached)

    db_spend = await SpendCounterReseed.from_db(prisma_client=prisma_client, counter_key=counter_key)
    if (
        db_spend is None
        and window_entity_type is not None
        and window_entity_id is not None
        and window_start is not None
    ):
        db_spend = await SpendCounterReseed.window_from_spend_logs(
            prisma_client=prisma_client,
            entity_type=window_entity_type,
            entity_id=window_entity_id,
            window_start=window_start,
        )
    if db_spend is None:
        return None

    spend_counter_cache.in_memory_cache.set_cache(
        key=marker_key,
        value=db_spend,
        ttl=SPEND_DB_FLOOR_CACHE_TTL_SECONDS,
    )
    return db_spend


async def _read_spend_counter_estimate(counter_key: str, fallback_spend: float) -> tuple[float, bool]:
    """Return (spend, authoritative). ``authoritative`` is True when the value
    came from Redis or a fresh DB read (cross-pod truth), False when it came
    from the per-pod in-memory copy or the caller's fallback. Only the
    fail-closed path reads the flag; normal callers ignore it."""
    # 1. Redis first (cross-pod authoritative). On clean miss, skip
    # in-memory: per-pod in-memory only has this pod's writes, so it
    # would mask cross-pod increments.
    redis_clean_miss = False
    if spend_counter_cache.redis_cache is not None:
        try:
            val = await spend_counter_cache.redis_cache.async_get_cache(key=counter_key)
            if val is not None:
                return float(val), True
            redis_clean_miss = True
        except Exception as e:
            verbose_proxy_logger.debug(
                "get_current_spend: Redis read failed for %s, falling back to in-memory: %s",
                counter_key,
                e,
            )

    # 2. In-memory only when Redis is unreachable.
    if not redis_clean_miss:
        val = spend_counter_cache.in_memory_cache.get_cache(key=counter_key)
        if val is not None:
            return float(val), False

    # 3. Reseed from DB - fallback_spend lags cross-pod, would allow bypass.
    db_spend = await SpendCounterReseed.coalesced(
        prisma_client=prisma_client,
        spend_counter_cache=spend_counter_cache,
        counter_key=counter_key,
    )
    if db_spend is not None:
        return db_spend, True

    # 4. Caller-supplied fallback (DB unavailable).
    return fallback_spend, False


async def increment_spend_counters(
    token: Optional[str],
    team_id: Optional[str],
    user_id: Optional[str],
    response_cost: Optional[float],
    org_id: Optional[str] = None,
    budget_reservation: Optional[dict] = None,
    end_user_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    """
    Atomically increment spend counters for budget enforcement.

    Uses spend_counter_cache (DualCache with Redis backend when available)
    so counters are shared across all pods. Budget check functions read
    from these counters via get_current_spend() (Redis-first).

    Awaited (not create_task) in the cost callback, so the counter is
    updated before the next request's auth check runs.
    """
    reserved_counter_keys = await _reconcile_budget_reservation_for_counter_update(
        budget_reservation=budget_reservation,
        response_cost=response_cost,
    )

    if response_cost is None or response_cost == 0:
        if budget_reservation is not None:
            budget_reservation["finalized"] = True
        return

    cost: float = response_cost

    async def _key_scope(key_token: str) -> None:
        # key_token arrives pre-hashed from metadata["user_api_key"] (auth flow
        # hashes raw "sk-..." keys before they reach the callback). The
        # startswith("sk-") check is a safety net matching update_cache —
        # if a raw key somehow arrives, hash it; otherwise use as-is to
        # avoid double-hashing (budget checks read valid_token.token which
        # is single-hashed).
        hashed_token = (
            hash_token(token=key_token) if isinstance(key_token, str) and key_token.startswith("sk-") else key_token
        )
        key_counter_key = f"spend:key:{hashed_token}"
        if key_counter_key not in reserved_counter_keys:
            await _init_and_increment_spend_counter(
                counter_key=key_counter_key,
                source_cache_key=hashed_token,
                increment=cost,
            )

        key_obj = await user_api_key_cache.async_get_cache(key=hashed_token)
        if key_obj is None:
            return
        key_budget_limits = getattr(key_obj, "budget_limits", None) or (
            key_obj.get("budget_limits") if isinstance(key_obj, dict) else None
        )
        if isinstance(key_budget_limits, str):
            key_budget_limits = json.loads(key_budget_limits)
        if not isinstance(key_budget_limits, list):
            return
        for window in key_budget_limits:
            duration = window["budget_duration"] if isinstance(window, dict) else window.budget_duration
            key_window_counter = f"spend:key:{hashed_token}:window:{duration}"
            if key_window_counter not in reserved_counter_keys:
                await _init_and_increment_window_spend_counter(
                    counter_key=key_window_counter,
                    entity_type="Key",
                    entity_id=hashed_token,
                    window_start=get_budget_window_start(window),
                    increment=cost,
                )

    async def _team_scope(scope_team_id: str) -> None:
        team_counter_key = f"spend:team:{scope_team_id}"
        if team_counter_key not in reserved_counter_keys:
            await _init_and_increment_spend_counter(
                counter_key=team_counter_key,
                source_cache_key=f"team_id:{scope_team_id}",
                increment=cost,
            )

        team_obj = await user_api_key_cache.async_get_cache(key=f"team_id:{scope_team_id}")
        if team_obj is None:
            return
        team_budget_limits = getattr(team_obj, "budget_limits", None) or (
            team_obj.get("budget_limits") if isinstance(team_obj, dict) else None
        )
        if isinstance(team_budget_limits, str):
            team_budget_limits = json.loads(team_budget_limits)
        if not isinstance(team_budget_limits, list):
            return
        for window in team_budget_limits:
            duration = window["budget_duration"] if isinstance(window, dict) else window.budget_duration
            team_window_counter = f"spend:team:{scope_team_id}:window:{duration}"
            if team_window_counter not in reserved_counter_keys:
                await _init_and_increment_window_spend_counter(
                    counter_key=team_window_counter,
                    entity_type="Team",
                    entity_id=scope_team_id,
                    window_start=get_budget_window_start(window),
                    increment=cost,
                )

    async def _team_member_scope(scope_user_id: str, scope_team_id: str) -> None:
        team_member_counter_key = f"spend:team_member:{scope_user_id}:{scope_team_id}"
        if team_member_counter_key in reserved_counter_keys:
            return
        await _init_and_increment_spend_counter(
            counter_key=team_member_counter_key,
            source_cache_key=f"team_membership:{scope_user_id}:{scope_team_id}",
            increment=cost,
        )

    async def _user_scope(scope_user_id: str) -> None:
        user_counter_key = f"spend:user:{scope_user_id}"
        if user_counter_key in reserved_counter_keys:
            return
        await _init_and_increment_spend_counter(
            counter_key=user_counter_key,
            source_cache_key=scope_user_id,
            increment=cost,
        )

    scope_coros = tuple(
        coro
        for coro in (
            _key_scope(token) if token is not None else None,
            _team_scope(team_id) if team_id is not None else None,
            _team_member_scope(user_id, team_id) if user_id is not None and team_id is not None else None,
            _user_scope(user_id) if user_id is not None else None,
            _increment_end_user_and_tag_spend_counters(
                end_user_id=end_user_id,
                tags=tags,
                response_cost=cost,
                reserved_counter_keys=reserved_counter_keys,
            )
            if end_user_id is not None or tags is not None
            else None,
            _increment_org_spend_counter(
                org_id=org_id,
                response_cost=cost,
                reserved_counter_keys=reserved_counter_keys,
            )
            if org_id is not None
            else None,
        )
        if coro is not None
    )

    # return_exceptions so a failing scope does not leave its siblings running
    # as orphaned tasks that race the caller's reservation-counter invalidation;
    # all scopes settle, then the first error propagates as before.
    scope_results = await asyncio.gather(*scope_coros, return_exceptions=True)
    scope_errors = [r for r in scope_results if isinstance(r, BaseException)]
    if scope_errors:
        raise scope_errors[0]

    if budget_reservation is not None:
        budget_reservation["finalized"] = True


async def _reconcile_budget_reservation_for_counter_update(
    budget_reservation: Optional[dict],
    response_cost: Optional[float],
) -> Set[str]:
    if budget_reservation is None:
        return set()

    from litellm.proxy.spend_tracking.budget_reservation import (
        get_reserved_counter_keys,
        invalidate_budget_reservation_counters,
        reconcile_budget_reservation,
    )

    reserved_counter_keys = get_reserved_counter_keys(budget_reservation=budget_reservation)
    try:
        await reconcile_budget_reservation(
            budget_reservation=budget_reservation,
            actual_cost=response_cost or 0.0,
            finalize=False,
        )
    except Exception:
        verbose_proxy_logger.warning(
            "Failed to reconcile budget reservation after persisted spend; invalidating reserved counters and falling back to direct increment",
            exc_info=True,
        )
        try:
            await invalidate_budget_reservation_counters(budget_reservation=budget_reservation)
        except Exception:
            verbose_proxy_logger.exception(
                "Failed to invalidate reserved counters after reservation reconciliation failed"
            )
        return set()
    return reserved_counter_keys


async def _increment_end_user_and_tag_spend_counters(
    end_user_id: Optional[str],
    tags: Optional[List[str]],
    response_cost: float,
    reserved_counter_keys: Set[str],
) -> None:
    if end_user_id is not None:
        await _init_and_increment_unreserved_spend_counter(
            counter_key=f"spend:end_user:{end_user_id}",
            source_cache_key=f"end_user_id:{end_user_id}",
            increment=response_cost,
            reserved_counter_keys=reserved_counter_keys,
        )

    if tags is None:
        return

    seen_tags: Set[str] = set()
    for tag_name in tags:
        if not tag_name or not isinstance(tag_name, str) or tag_name in seen_tags:
            continue
        seen_tags.add(tag_name)
        await _init_and_increment_unreserved_spend_counter(
            counter_key=f"spend:tag:{tag_name}",
            source_cache_key=f"tag:{tag_name}",
            increment=response_cost,
            reserved_counter_keys=reserved_counter_keys,
        )


async def _increment_org_spend_counter(
    org_id: Optional[str],
    response_cost: float,
    reserved_counter_keys: Set[str],
) -> None:
    if org_id is None:
        return

    await _init_and_increment_unreserved_spend_counter(
        counter_key=f"spend:org:{org_id}",
        source_cache_key=[f"org_id:{org_id}:with_budget", f"org_id:{org_id}"],
        increment=response_cost,
        reserved_counter_keys=reserved_counter_keys,
    )


async def _init_and_increment_unreserved_spend_counter(
    counter_key: str,
    source_cache_key: Union[str, List[str]],
    increment: float,
    reserved_counter_keys: Set[str],
) -> None:
    if counter_key in reserved_counter_keys:
        return

    await _init_and_increment_spend_counter(
        counter_key=counter_key,
        source_cache_key=source_cache_key,
        increment=increment,
    )


async def _init_and_increment_spend_counter(
    counter_key: str,
    source_cache_key: Union[str, List[str]],
    increment: float,
):
    """
    Initialize counter from the authoritative DB spend value if not yet
    set, then atomically increment in both in-memory and Redis.

    On first access per pod:
    1. Check spend_counter_cache (in-memory -> Redis via DualCache)
    2. If not found, reseed from the DB via `SpendCounterReseed.coalesced`.
       Falls back to the cached object's `.spend` via user_api_key_cache
       only if prisma is unavailable, since that value can lag the flusher.
    3. Seed counter via async_increment_cache (not async_set_cache) to avoid a
       check-then-set race: if two pods cold-start simultaneously, both may see
       the counter as absent and seed it. Using increment means the worst case
       is over-counting (conservative, blocks slightly early) rather than
       under-counting (would allow overspend).
    4. Increment atomically (both in-memory + Redis)
    """
    await _ensure_spend_counter_initialized(
        counter_key=counter_key,
        source_cache_key=source_cache_key,
    )
    await _increment_spend_counter_cache(counter_key=counter_key, increment=increment)


async def _init_and_increment_window_spend_counter(
    counter_key: str,
    entity_type: str,
    entity_id: str,
    window_start: Optional[datetime],
    increment: float,
):
    if window_start is None:
        verbose_proxy_logger.warning(
            "Skipping spend counter increment for invalid budget window %s",
            counter_key,
        )
        return

    initialized = await _ensure_window_spend_counter_initialized(
        counter_key=counter_key,
        entity_type=entity_type,
        entity_id=entity_id,
        window_start=window_start,
    )
    if initialized is False:
        return
    await _increment_spend_counter_cache(counter_key=counter_key, increment=increment)


async def _ensure_spend_counter_initialized(
    counter_key: str,
    source_cache_key: Union[str, List[str]],
):
    is_warm = await _is_spend_counter_cache_warm(counter_key=counter_key)
    if is_warm is False:
        # Shares the per-counter lock with get_current_spend.
        db_spend = await SpendCounterReseed.coalesced(
            prisma_client=prisma_client,
            spend_counter_cache=spend_counter_cache,
            counter_key=counter_key,
            require_cache_warm=True,
        )
        if db_spend is None:
            # DB unavailable - fall back to in-process cache (may be stale).
            base_spend = await _get_source_cache_base_spend(source_cache_key=source_cache_key)
            if base_spend > 0:
                await _increment_spend_counter_cache(counter_key=counter_key, increment=base_spend)


async def _get_source_cache_base_spend(
    source_cache_key: Union[str, List[str]],
) -> float:
    source_cache_keys = [source_cache_key] if isinstance(source_cache_key, str) else source_cache_key
    for cache_key in source_cache_keys:
        source = await user_api_key_cache.async_get_cache(key=cache_key)
        if source is None:
            continue
        if isinstance(source, dict):
            return float(source.get("spend", 0.0) or 0.0)
        return float(getattr(source, "spend", 0.0) or 0.0)
    return 0.0


async def _ensure_window_spend_counter_initialized(
    counter_key: str,
    entity_type: str,
    entity_id: str,
    window_start: datetime,
) -> bool:
    is_warm = await _is_spend_counter_cache_warm(counter_key=counter_key)
    if is_warm is True:
        return True

    window_spend = await SpendCounterReseed.coalesced_window(
        prisma_client=prisma_client,
        spend_counter_cache=spend_counter_cache,
        counter_key=counter_key,
        entity_type=entity_type,
        entity_id=entity_id,
        window_start=window_start,
    )
    if window_spend is None:
        verbose_proxy_logger.warning(
            "Skipping cold spend counter seed for %s because window spend could not be loaded",
            counter_key,
        )
        return False
    return True


async def _is_spend_counter_cache_warm(counter_key: str) -> bool:
    if spend_counter_cache.redis_cache is not None:
        try:
            current_value = await spend_counter_cache.redis_cache.async_get_cache(
                key=counter_key,
            )
            if current_value is None:
                return False
            spend_counter_cache.in_memory_cache.set_cache(
                key=counter_key,
                value=current_value,
            )
            return True
        except Exception as e:
            verbose_proxy_logger.debug(
                "Unable to read Redis spend counter %s before initialization, falling back to in-memory: %s",
                counter_key,
                e,
            )

    return spend_counter_cache.in_memory_cache.get_cache(key=counter_key) is not None


async def _increment_spend_counter_cache(counter_key: str, increment: float):
    if spend_counter_cache.redis_cache is not None:
        try:
            current_value = await spend_counter_cache.redis_cache.async_increment(
                key=counter_key,
                value=increment,
                refresh_ttl=True,
            )
        except Exception:
            await _invalidate_spend_counter(counter_key=counter_key)
            raise
        spend_counter_cache.in_memory_cache.set_cache(
            key=counter_key,
            value=current_value,
        )
        return current_value

    return await spend_counter_cache.async_increment_cache(
        key=counter_key,
        value=increment,
        refresh_ttl=True,
    )


async def _invalidate_spend_counter(counter_key: str):
    spend_counter_cache.in_memory_cache.delete_cache(key=counter_key)
    if spend_counter_cache.redis_cache is not None:
        try:
            await spend_counter_cache.redis_cache.async_delete_cache(key=counter_key)
        except Exception:
            verbose_proxy_logger.debug(
                "Unable to delete stale spend counter %s after increment failure",
                counter_key,
                exc_info=True,
            )


async def update_cache(
    token: Optional[str],
    user_id: Optional[str],
    end_user_id: Optional[str],
    team_id: Optional[str],
    response_cost: Optional[float],
    parent_otel_span: Optional[Span],  # type: ignore
    tags: Optional[List[str]] = None,
):
    """
    Use this to update the cache with new user spend.

    Put any alerting logic in here.
    """

    values_to_update_in_cache: List[Tuple[Any, Any]] = []

    ### UPDATE KEY SPEND ###
    async def _update_key_cache(token: str, response_cost: float):
        # Fetch the existing cost for the given token
        if isinstance(token, str) and token.startswith("sk-"):
            hashed_token = hash_token(token=token)
        else:
            hashed_token = token
        verbose_proxy_logger.debug("_update_key_cache: hashed_token=%s", hashed_token)
        existing_spend_obj = await user_api_key_cache.async_get_cache(key=hashed_token, model_type=UserAPIKeyAuth)
        verbose_proxy_logger.debug(f"_update_key_cache: existing_spend_obj={existing_spend_obj}")
        if existing_spend_obj is None:
            return

        existing_spend = existing_spend_obj.spend or 0.0
        # Calculate the new cost by adding the existing cost and response_cost
        new_spend = existing_spend + response_cost

        ## CHECK IF USER PROJECTED SPEND > SOFT LIMIT
        if (
            existing_spend_obj.soft_budget_cooldown is False
            and existing_spend_obj.soft_budget is not None
            and (
                _is_projected_spend_over_limit(
                    current_spend=new_spend,
                    soft_budget_limit=existing_spend_obj.soft_budget,
                )
                is True
            )
        ):
            projected_spend, projected_exceeded_date = _get_projected_spend_over_limit(
                current_spend=new_spend,
                soft_budget_limit=existing_spend_obj.soft_budget,
            )  # type: ignore
            soft_limit = existing_spend_obj.soft_budget
            call_info = CallInfo(
                token=existing_spend_obj.token or "",
                spend=new_spend,
                key_alias=existing_spend_obj.key_alias,
                max_budget=soft_limit,
                user_id=existing_spend_obj.user_id,
                projected_spend=projected_spend,
                projected_exceeded_date=str(projected_exceeded_date),
                event_group=Litellm_EntityType.KEY,
            )
            # alert user
            asyncio.create_task(
                proxy_logging_obj.budget_alerts(
                    type="projected_limit_exceeded",
                    user_info=call_info,
                )
            )
            # set cooldown on alert

    ### UPDATE USER SPEND ###
    async def _update_user_cache():
        ## UPDATE CACHE FOR USER ID + GLOBAL PROXY
        if response_cost is None:
            return
        user_ids = [user_id]
        try:
            for _id in user_ids:
                # Fetch the existing cost for the given user
                if _id is None:
                    continue
                cached_user = await user_api_key_cache.async_get_cache(key=_id)
                if cached_user is None:
                    # do nothing if there is no cache value
                    return
                existing_spend_obj = CacheCodec.deserialize(cached_user, LiteLLM_UserTable)
                if existing_spend_obj is None:
                    return
                verbose_proxy_logger.debug(
                    f"_update_user_db: existing spend: {existing_spend_obj}; response_cost: {response_cost}"
                )

                existing_spend = existing_spend_obj.spend or 0.0
                # Calculate the new cost by adding the existing cost and response_cost
                new_spend = existing_spend + response_cost

                existing_spend_obj.spend = new_spend
                values_to_update_in_cache.append(
                    (
                        _id,
                        CacheCodec.serialize(existing_spend_obj, model_type=LiteLLM_UserTable),
                    )
                )
            ## UPDATE GLOBAL PROXY ##
            global_proxy_spend = await user_api_key_cache.async_get_cache(key=GLOBAL_PROXY_SPEND_CACHE_KEY)
            if global_proxy_spend is None:
                # do nothing if not in cache
                return
            elif response_cost is not None and global_proxy_spend is not None:
                increment = global_proxy_spend + response_cost
                values_to_update_in_cache.append((GLOBAL_PROXY_SPEND_CACHE_KEY, increment))
        except Exception as e:
            verbose_proxy_logger.warning(
                "Spend tracking - failed to update user spend in cache. "
                "Budget enforcement may use stale spend values. "
                "user_id=%s, response_cost=%s - %s\n%s",
                user_id,
                response_cost,
                str(e),
                traceback.format_exc(),
            )

    ### UPDATE END-USER SPEND ###
    async def _update_end_user_cache():
        if end_user_id is None or response_cost is None:
            return

        _id = "end_user_id:{}".format(end_user_id)
        try:
            # Fetch the existing cost for the given user
            cached_end_user = await user_api_key_cache.async_get_cache(key=_id)
            if cached_end_user is None:
                # if user does not exist in LiteLLM_UserTable, create a new user
                # do nothing if end-user not in api key cache
                return
            existing_spend_obj = CacheCodec.deserialize(cached_end_user, LiteLLM_EndUserTable)
            if existing_spend_obj is None:
                return
            verbose_proxy_logger.debug(
                f"_update_end_user_db: existing spend: {existing_spend_obj}; response_cost: {response_cost}"
            )

            existing_spend = existing_spend_obj.spend or 0.0
            # Calculate the new cost by adding the existing cost and response_cost
            new_spend = existing_spend + response_cost

            existing_spend_obj.spend = new_spend
            values_to_update_in_cache.append(
                (
                    _id,
                    CacheCodec.serialize(existing_spend_obj, model_type=LiteLLM_EndUserTable),
                )
            )
        except Exception as e:
            verbose_proxy_logger.warning(
                "Spend tracking - failed to update end user spend in cache. "
                "Budget enforcement may use stale spend values. "
                "end_user_id=%s, response_cost=%s - %s\n%s",
                end_user_id,
                response_cost,
                str(e),
                traceback.format_exc(),
            )

    ### UPDATE TEAM SPEND ###
    async def _update_team_cache():
        if team_id is None or response_cost is None:
            return

        _id = "team_id:{}".format(team_id)
        try:
            cached_team = await user_api_key_cache.async_get_cache(key=_id)
            if cached_team is None:
                # do nothing if team not in api key cache
                return
            existing_spend_obj: Optional[LiteLLM_TeamTableCachedObj] = CacheCodec.deserialize(
                cached_team, LiteLLM_TeamTableCachedObj
            )
            if existing_spend_obj is None:
                return
            verbose_proxy_logger.debug(
                f"_update_team_db: existing spend: {existing_spend_obj}; response_cost: {response_cost}"
            )

            existing_spend: float = existing_spend_obj.spend or 0.0
            # Calculate the new cost by adding the existing cost and response_cost
            new_spend = existing_spend + response_cost

            existing_spend_obj.spend = new_spend
            values_to_update_in_cache.append(
                (
                    _id,
                    CacheCodec.serialize(existing_spend_obj, model_type=LiteLLM_TeamTableCachedObj),
                )
            )
        except Exception as e:
            verbose_proxy_logger.warning(
                "Spend tracking - failed to update team spend in cache. "
                "Budget enforcement may use stale spend values. "
                "team_id=%s, response_cost=%s - %s\n%s",
                team_id,
                response_cost,
                str(e),
                traceback.format_exc(),
            )

    ### UPDATE TAG SPEND ###
    async def _update_tag_cache():
        """
        Update the tag cache with the new spend.
        """
        if tags is None or response_cost is None:
            return

        try:
            for tag_name in tags:
                if not tag_name or not isinstance(tag_name, str):
                    continue

                cache_key = f"tag:{tag_name}"
                # Fetch the existing tag object from cache
                cached_tag = await user_api_key_cache.async_get_cache(key=cache_key)
                if cached_tag is None:
                    # do nothing if tag not in api key cache
                    continue

                existing_tag_obj = CacheCodec.deserialize(cached_tag, LiteLLM_TagTable)
                if existing_tag_obj is None:
                    continue

                verbose_proxy_logger.debug(
                    f"_update_tag_cache: existing spend for tag={tag_name}: {existing_tag_obj}; response_cost: {response_cost}"
                )

                existing_spend = existing_tag_obj.spend or 0.0
                # Calculate the new cost by adding the existing cost and response_cost
                new_spend = existing_spend + response_cost

                existing_tag_obj.spend = new_spend
                values_to_update_in_cache.append(
                    (
                        cache_key,
                        CacheCodec.serialize(existing_tag_obj, model_type=LiteLLM_TagTable),
                    )
                )
        except Exception as e:
            verbose_proxy_logger.warning(
                "Spend tracking - failed to update tag spend in cache. "
                "Budget enforcement may use stale spend values. "
                "tags=%s, response_cost=%s - %s\n%s",
                tags,
                response_cost,
                str(e),
                traceback.format_exc(),
            )

    if token is not None and response_cost is not None:
        await _update_key_cache(token=token, response_cost=response_cost)

    if user_id is not None:
        await _update_user_cache()

    if end_user_id is not None:
        await _update_end_user_cache()

    if team_id is not None:
        await _update_team_cache()

    if tags is not None:
        await _update_tag_cache()

    global_proxy_spend_key = GLOBAL_PROXY_SPEND_CACHE_KEY
    local_object_updates = tuple((k, v) for k, v in values_to_update_in_cache if k != global_proxy_spend_key)
    shared_scalar_updates = tuple((k, v) for k, v in values_to_update_in_cache if k == global_proxy_spend_key)

    if local_object_updates:
        asyncio.create_task(
            user_api_key_cache.async_set_cache_pipeline(
                cache_list=list(local_object_updates),
                ttl=get_management_object_ttl(user_api_key_cache),
                litellm_parent_otel_span=parent_otel_span,
                local_only=True,
            )
        )
    if shared_scalar_updates:
        asyncio.create_task(
            user_api_key_cache.async_set_cache_pipeline(
                cache_list=list(shared_scalar_updates),
                ttl=get_management_object_ttl(user_api_key_cache),
                litellm_parent_otel_span=parent_otel_span,
            )
        )


def run_ollama_serve():
    try:
        command = ["ollama", "serve"]

        with open(os.devnull, "w") as devnull:
            subprocess.Popen(command, stdout=devnull, stderr=devnull)
    except Exception as e:
        verbose_proxy_logger.debug(f"""
            LiteLLM Warning: proxy started with `ollama` model\n`ollama serve` failed with Exception{e}. \nEnsure you run `ollama serve`
        """)


def _get_process_rss_mb() -> Optional[float]:
    """
    Get process RSS memory in MB.
    On Linux, ru_maxrss is in KB. On macOS, ru_maxrss is in bytes.
    """
    try:
        import resource

        ru_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return float(ru_maxrss) / (1024 * 1024)
        return float(ru_maxrss) / 1024
    except Exception:
        return None


def _rss_mb_for_log() -> str:
    rss_mb = _get_process_rss_mb()
    if rss_mb is None:
        return "unknown"
    return f"{rss_mb:.2f}"


def _is_unexpected_keyword_argument_type_error(exc: BaseException) -> bool:
    """True when ``exc`` is a TypeError from passing a kwarg the callee does not accept."""
    return isinstance(exc, TypeError) and ("unexpected keyword argument" in str(exc).lower())


async def _run_direct_health_check_with_instrumentation(
    model_list: list,
    details: Optional[bool],
    max_concurrency: Optional[int],
    instrumentation_context: dict,
):
    """Call ``perform_health_check``, retrying with fewer kwargs on unexpected-kw TypeErrors."""
    _hc_filter = health_check_filter_kwargs_from_general_settings(general_settings)
    last_type_error: Optional[TypeError] = None
    for extra_kwargs in (
        {
            "instrumentation_context": instrumentation_context,
            **_hc_filter,
        },
        {"instrumentation_context": instrumentation_context},
        dict(_hc_filter),
        {},
    ):
        try:
            return await perform_health_check(
                model_list=model_list,
                details=details,
                max_concurrency=max_concurrency,
                **extra_kwargs,
            )
        except TypeError as e:
            if not _is_unexpected_keyword_argument_type_error(e):
                raise
            last_type_error = e
    assert last_type_error is not None
    raise last_type_error


def _schedule_background_health_check_db_save(
    prisma_client,
    shared_health_manager,
    model_list: list,
    healthy_endpoints: list,
    unhealthy_endpoints: list,
):
    """Fire-and-forget: persist health check results to DB if prisma is available."""
    if prisma_client is None:
        return
    import time as time_module

    from litellm.proxy.health_endpoints._health_endpoints import (
        _save_background_health_checks_to_db,
    )

    checked_by = shared_health_manager.pod_id if shared_health_manager is not None else "background_health_check"
    start_time = time_module.time()
    asyncio.create_task(
        _save_background_health_checks_to_db(
            prisma_client,
            model_list,
            healthy_endpoints,
            unhealthy_endpoints,
            start_time,
            checked_by=checked_by,
        )
    )


def _get_endpoint_exception_status(endpoint: dict, exceptions: dict) -> int:
    """Return the HTTP status code for an unhealthy endpoint.

    Prefers the live exception object in `exceptions` (direct health check path).
    Falls back to the `exception_status` integer stored on the endpoint dict
    (shared-cache path, where exception objects are not available).
    """
    model_id = endpoint.get("model_id")
    exc = exceptions.get(model_id) if model_id else None
    if exc is not None:
        return getattr(exc, "status_code", 500)
    return endpoint.get("exception_status", 500)


def _write_health_state_to_router_cache(
    healthy_endpoints: list,
    unhealthy_endpoints: list,
    exceptions_by_model_id: Optional[dict] = None,
) -> None:
    """
    Write deployment health states to the router's health state cache
    for health-check-driven routing. No-op if the feature is disabled.
    """
    from litellm.proxy.health_check import build_deployment_health_states
    from litellm.router_utils.cooldown_handlers import _set_cooldown_deployments
    from litellm.router_utils.router_callbacks.track_deployment_metrics import (
        increment_deployment_failures_for_current_minute,
    )

    _exceptions: dict = exceptions_by_model_id or {}

    try:
        if llm_router is None or not llm_router.enable_health_check_routing:
            return

        # When health_check_ignore_transient_errors is set, treat 429/408
        # endpoints as healthy so they are not filtered from routing.
        _effective_unhealthy = unhealthy_endpoints
        if llm_router.health_check_ignore_transient_errors:
            _effective_unhealthy = [
                ep for ep in unhealthy_endpoints if _get_endpoint_exception_status(ep, _exceptions) not in (429, 408)
            ]

        states = build_deployment_health_states(
            healthy_endpoints=healthy_endpoints,
            unhealthy_endpoints=_effective_unhealthy,
        )
        if states:
            llm_router.health_state_cache.set_deployment_health_states(states)
            verbose_proxy_logger.debug(
                "health_check_routing_state_updated healthy=%d unhealthy=%d",
                sum(1 for s in states.values() if s.get("is_healthy")),
                sum(1 for s in states.values() if not s.get("is_healthy")),
            )

        for endpoint in unhealthy_endpoints:
            model_id = endpoint.get("model_id")
            if not model_id:
                continue

            original_exception = _exceptions.get(model_id)
            if original_exception is None:
                continue

            exception_status = getattr(original_exception, "status_code", 500)

            if llm_router.health_check_ignore_transient_errors and exception_status in (
                429,
                408,
            ):
                continue

            increment_deployment_failures_for_current_minute(
                litellm_router_instance=llm_router,
                deployment_id=model_id,
            )

            _set_cooldown_deployments(
                litellm_router_instance=llm_router,
                original_exception=original_exception,
                exception_status=exception_status,
                deployment=model_id,
                time_to_cooldown=llm_router.cooldown_time,
            )

    except Exception as e:
        verbose_proxy_logger.warning("Failed to write health state to router cache: %s", str(e))


_ADAPTIVE_ROUTER_FLUSH_INTERVAL_SECONDS = 10


async def _adaptive_router_flusher_loop():
    """
    Drain every AdaptiveRouter's in-memory state + session aggregators into
    Postgres on a fixed cadence. Hot-path writes go to memory; this loop is
    the only writer to the adaptive router DB tables.
    """
    global llm_router, prisma_client
    while True:
        try:
            await asyncio.sleep(_ADAPTIVE_ROUTER_FLUSH_INTERVAL_SECONDS)
            adaptive_routers = getattr(llm_router, "adaptive_routers", None) or {}
            if not adaptive_routers or prisma_client is None:
                continue
            for tagged_routers in adaptive_routers.values():
                for tagged in tagged_routers:
                    ar = tagged.strategy
                    # Lazy state load: covers adaptive routers registered via
                    # `/config/reload` after proxy boot.
                    if not getattr(ar, "_state_loaded", False):
                        try:
                            await ar.load_state_from_db(prisma_client)
                        finally:
                            ar._state_loaded = True
                    await ar.queue.flush_state_to_db(prisma_client)
                    await ar.queue.flush_session_to_db(prisma_client)
        except asyncio.CancelledError:
            raise
        except Exception:
            verbose_proxy_logger.exception("adaptive_router flusher iteration failed")


async def _run_background_health_check():
    """
    Periodically run health checks in the background on the endpoints.

    Update health_check_results, based on this.
    Uses shared health check state when Redis is available to coordinate across pods.
    """
    global health_check_results, llm_model_list, health_check_interval
    global health_check_concurrency, health_check_details, use_shared_health_check
    global redis_usage_cache, prisma_client
    global background_health_check_loop_active, background_health_check_cycle_seq

    if health_check_interval is None or not isinstance(health_check_interval, int) or health_check_interval <= 0:
        return

    if background_health_check_loop_active:
        verbose_proxy_logger.warning(
            "background_health_check_loop_overlap_detected existing_loop_active=true interval_seconds=%s max_concurrency=%s shared=%s",
            health_check_interval,
            health_check_concurrency,
            use_shared_health_check,
        )
    background_health_check_loop_active = True
    verbose_proxy_logger.info(
        "background_health_check_loop_started interval_seconds=%s max_concurrency=%s shared=%s details=%s thread_count=%d rss_mb=%s",
        health_check_interval,
        health_check_concurrency,
        use_shared_health_check,
        health_check_details,
        threading.active_count(),
        _rss_mb_for_log(),
    )

    # Initialize shared health check manager if Redis is available and feature is enabled
    shared_health_manager = None
    if use_shared_health_check and redis_usage_cache is not None:
        from litellm.proxy.health_check_utils.shared_health_check_manager import (
            SharedHealthCheckManager,
        )

        shared_health_manager = SharedHealthCheckManager(
            redis_cache=redis_usage_cache,
            health_check_ttl=DEFAULT_SHARED_HEALTH_CHECK_TTL,
            lock_ttl=DEFAULT_SHARED_HEALTH_CHECK_LOCK_TTL,
        )
        verbose_proxy_logger.info("Initialized shared health check manager")

    while True:
        background_health_check_cycle_seq += 1
        cycle_id = f"bg-{background_health_check_cycle_seq}"
        cycle_start_time = time.monotonic()

        # make 1 deep copy of llm_model_list on every health check iteration
        _llm_model_list = copy.deepcopy(llm_model_list) or []
        model_count_total = len(_llm_model_list)

        # filter out models that have disabled background health checks
        _llm_model_list = [
            m for m in _llm_model_list if not m.get("model_info", {}).get("disable_background_health_check", False)
        ]
        model_count_enabled = len(_llm_model_list)
        expected_peak_in_flight = model_count_enabled
        if isinstance(health_check_concurrency, int) and health_check_concurrency > 0 and model_count_enabled > 0:
            expected_peak_in_flight = min(model_count_enabled, health_check_concurrency)

        verbose_proxy_logger.debug(
            "background_health_check_cycle_start cycle_id=%s model_count_total=%d model_count_enabled=%d interval_seconds=%s max_concurrency=%s expected_peak_in_flight=%d shared=%s thread_count=%d rss_mb=%s",
            cycle_id,
            model_count_total,
            model_count_enabled,
            health_check_interval,
            health_check_concurrency,
            expected_peak_in_flight,
            shared_health_manager is not None,
            threading.active_count(),
            _rss_mb_for_log(),
        )

        instrumentation_context = {
            "enabled": True,
            "source": "proxy_background_loop",
            "cycle_id": cycle_id,
        }

        # Use shared health check if available, otherwise fall back to direct health check
        # Convert health_check_details to bool for perform_shared_health_check (defaults to True if None)
        details_bool = health_check_details if health_check_details is not None else True
        _hc_filter = health_check_filter_kwargs_from_general_settings(general_settings)

        if shared_health_manager is not None:
            try:
                (
                    healthy_endpoints,
                    unhealthy_endpoints,
                    _exceptions_by_model_id,
                ) = await shared_health_manager.perform_shared_health_check(
                    model_list=_llm_model_list,
                    details=details_bool,
                    max_concurrency=health_check_concurrency,
                    **_hc_filter,
                )
            except Exception as e:
                verbose_proxy_logger.error(
                    "Error in shared health check, falling back to direct health check: %s",
                    str(e),
                )
                (
                    healthy_endpoints,
                    unhealthy_endpoints,
                    _exceptions_by_model_id,
                ) = await _run_direct_health_check_with_instrumentation(
                    _llm_model_list,
                    details_bool,
                    health_check_concurrency,
                    instrumentation_context,
                )
        else:
            (
                healthy_endpoints,
                unhealthy_endpoints,
                _exceptions_by_model_id,
            ) = await _run_direct_health_check_with_instrumentation(
                _llm_model_list,
                details_bool,
                health_check_concurrency,
                instrumentation_context,
            )

        # Update the global variable with the health check results
        health_check_results["healthy_endpoints"] = healthy_endpoints
        health_check_results["unhealthy_endpoints"] = unhealthy_endpoints
        health_check_results["healthy_count"] = len(healthy_endpoints)
        health_check_results["unhealthy_count"] = len(unhealthy_endpoints)
        cycle_duration_ms = (time.monotonic() - cycle_start_time) * 1000
        verbose_proxy_logger.debug(
            "background_health_check_cycle_complete cycle_id=%s model_count_enabled=%d healthy_count=%d unhealthy_count=%d duration_ms=%.2f interval_seconds=%s thread_count=%d rss_mb=%s",
            cycle_id,
            model_count_enabled,
            len(healthy_endpoints),
            len(unhealthy_endpoints),
            cycle_duration_ms,
            health_check_interval,
            threading.active_count(),
            _rss_mb_for_log(),
        )
        if cycle_duration_ms > (health_check_interval * 1000):
            verbose_proxy_logger.warning(
                "background_health_check_cycle_duration_exceeded_interval cycle_id=%s duration_ms=%.2f interval_seconds=%s",
                cycle_id,
                cycle_duration_ms,
                health_check_interval,
            )

        # Save background health checks to database (non-blocking)
        _schedule_background_health_check_db_save(
            prisma_client,
            shared_health_manager,
            _llm_model_list,
            healthy_endpoints,
            unhealthy_endpoints,
        )

        # Write health state to router cache for health-check-driven routing
        _write_health_state_to_router_cache(healthy_endpoints, unhealthy_endpoints, _exceptions_by_model_id)

        await asyncio.sleep(health_check_interval)


class StreamingCallbackError(Exception):
    pass


# Fields in ``litellm_settings`` / ``general_settings`` whose values flow
# into ``get_instance_fn`` during config load. Remote-URL values
# (``s3://`` / ``gcs://``) are scrubbed from these when the value
# originates from a DB-overlay merge: at the point ``get_instance_fn``
# is invoked, ``config_file_path`` is non-None (the YAML load chain is
# active), so the runtime gate cannot distinguish a YAML-sourced value
# from a DB-sourced value. Scrubbing at the merge boundary closes that
# gap without tracking source on every config dict entry.
_DB_OVERLAY_REMOTE_MODULE_STR_FIELDS: Dict[str, Tuple[str, ...]] = {
    "litellm_settings": ("post_call_rules",),
    "general_settings": (
        "custom_auth",
        "custom_key_generate",
        "custom_key_update",
        "custom_sso",
        "custom_ui_sso_sign_in_handler",
    ),
}
_DB_OVERLAY_REMOTE_MODULE_LIST_FIELDS: Dict[str, Tuple[str, ...]] = {
    "litellm_settings": (
        "callbacks",
        "success_callback",
        "failure_callback",
        "audit_log_callbacks",
    ),
}


def _is_remote_module_url(value: Any) -> bool:
    return isinstance(value, str) and (value.startswith("s3://") or value.startswith("gcs://"))


def _scrub_db_overlay_remote_module_loads(section: str, db_value: Any) -> Any:
    """Strip ``s3://`` / ``gcs://`` entries from the DB-overlay value for
    fields whose contents reach ``get_instance_fn``. The same scheme is
    allowed from a YAML config (the documented operator flow) but a
    DB-overlay write would otherwise smuggle the same payload through
    the YAML-load chain and reach ``_load_instance_from_remote_storage``."""
    if not isinstance(db_value, dict):
        return db_value
    str_fields = _DB_OVERLAY_REMOTE_MODULE_STR_FIELDS.get(section, ())
    list_fields = _DB_OVERLAY_REMOTE_MODULE_LIST_FIELDS.get(section, ())
    if not str_fields and not list_fields and section != "general_settings":
        return db_value
    sanitized = copy.deepcopy(db_value)
    for field in str_fields:
        v = sanitized.get(field)
        if _is_remote_module_url(v):
            verbose_proxy_logger.warning(
                "Refused remote-URL value for DB-overlay %s.%s=%r; only "
                "config.yaml entries may reference s3:// / gcs:// modules.",
                section,
                field,
                v,
            )
            sanitized[field] = None
    for field in list_fields:
        v = sanitized.get(field)
        if isinstance(v, list):
            cleaned = [item for item in v if not _is_remote_module_url(item)]
            if len(cleaned) != len(v):
                verbose_proxy_logger.warning(
                    "Refused %d remote-URL entries from DB-overlay %s.%s; "
                    "only config.yaml entries may reference s3:// / gcs:// "
                    "modules.",
                    len(v) - len(cleaned),
                    section,
                    field,
                )
                sanitized[field] = cleaned
    # ``custom_provider_map`` is a list of dicts with ``custom_handler`` —
    # walk it explicitly.
    if section == "litellm_settings":
        cpm = sanitized.get("custom_provider_map")
        if isinstance(cpm, list):
            for item in cpm:
                if isinstance(item, dict) and _is_remote_module_url(item.get("custom_handler")):
                    verbose_proxy_logger.warning(
                        "Refused remote-URL custom_handler from DB-overlay litellm_settings.custom_provider_map: %r",
                        item.get("custom_handler"),
                    )
                    item["custom_handler"] = None
    # ``litellm_settings.guardrails`` is a list of single-key dicts in
    # v1 ({guardrail_name: {callbacks: [...], default_on: bool}}) or a
    # list of v2 entries ({guardrail_name, litellm_params: {guardrail:
    # "module.path", callbacks: [...]}}). Both shapes terminate in
    # ``callbacks`` (a list) or ``guardrail`` (a single dotted name)
    # that flow into ``get_instance_fn`` during config load.
    if section == "litellm_settings":
        pass
    return sanitized


def _normalize_user_url_validation(value: object) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, str):
        return str_to_bool(value)
    return bool(value)


def _apply_ssrf_general_settings(settings: Mapping[str, object]) -> None:
    if "user_url_allowed_hosts" in settings:
        litellm.user_url_allowed_hosts = cast(list[str], settings["user_url_allowed_hosts"])

    user_url_validation = _normalize_user_url_validation(settings.get("user_url_validation"))
    if user_url_validation is not None:
        litellm.user_url_validation = user_url_validation

    if "provider_url_destination_allowed_hosts" in settings:
        litellm.provider_url_destination_allowed_hosts = cast(
            list[str], settings["provider_url_destination_allowed_hosts"]
        )


def _set_redis_usage_cache(coordination_redis_cache: RedisCache | None) -> None:
    """Publish the resolved coordination Redis to the consumers that read it directly."""
    global redis_usage_cache
    redis_usage_cache = coordination_redis_cache


def _resolve_coordination_redis_env_refs(raw_params: Mapping[str, object]) -> dict[str, object]:
    """Resolve `os.environ/VAR` references in a coordination_redis block."""
    return {
        key: (get_secret(value) if isinstance(value, str) and value.startswith("os.environ/") else value)
        for key, value in raw_params.items()
    }


def _build_redis_usage_cache(redis_params: Mapping[str, object]) -> RedisCache:
    """
    Builds the proxy's coordination Redis client from resolved connection
    params. Cluster-mode targets (explicit `startup_nodes` or the
    REDIS_CLUSTER_NODES env var) get a `RedisClusterCache`, so consumers that
    branch on cluster mode (e.g. the v3 rate limiter) take the cluster path;
    everything else (host/url/sentinel) gets a plain `RedisCache`.
    """
    startup_nodes = redis_params.get("startup_nodes")
    if startup_nodes is None:
        env_cluster_nodes = get_secret_str("REDIS_CLUSTER_NODES")
        if env_cluster_nodes is not None:
            startup_nodes = json.loads(env_cluster_nodes)
    non_node_params = {key: value for key, value in redis_params.items() if key != "startup_nodes"}
    if startup_nodes:
        return RedisClusterCache(startup_nodes=startup_nodes, **non_node_params)
    return RedisCache(**non_node_params)


def _environment_has_redis_connection_target() -> bool:
    """
    Whether the REDIS_* environment variables name a Redis to connect to (host,
    url, cluster nodes, or sentinel nodes). Read-only: callers that only need to
    know whether the env fallback would apply use this instead of building a
    client.
    """
    redis_env_kwargs = litellm._redis._redis_kwargs_from_environment()
    return (
        "host" in redis_env_kwargs
        or "url" in redis_env_kwargs
        or get_secret_str("REDIS_CLUSTER_NODES") is not None
        or get_secret_str("REDIS_SENTINEL_NODES") is not None
    )


def _build_redis_usage_cache_from_environment() -> RedisCache | None:
    """
    Builds a standalone coordination Redis from REDIS_* environment variables.

    Lets the proxy's coordination Redis (cross-pod tpm/rpm rate limits, spend
    tracking, pod lock manager) run when the response-cache backend is not a
    plain Redis KV cache (e.g. a semantic cache, disk, or s3).

    Returns None when the environment carries no connection target (host, url,
    cluster nodes, or sentinel nodes).
    """
    if not _environment_has_redis_connection_target():
        return None
    return _build_redis_usage_cache(litellm._redis._redis_kwargs_from_environment())


def _attach_redis_usage_cache(redis_cache: RedisCache, enable_redis_auth_cache: bool) -> None:
    """
    Wires an established coordination Redis into the proxy-level caches that
    consume it directly: the spend counter cache, the CLI SSO login-session
    cache, the cluster-wide config cache, and (only when opted in) the
    virtual-key auth cache.

    The CLI SSO login-session cache is always backed by Redis when available so
    that the browser SSO flow behind `lite login` survives landing on different
    workers; it must not be gated behind enable_redis_auth_cache.
    """
    spend_counter_cache.attach_redis_cache(
        redis_cache,
        default_redis_ttl=litellm.default_redis_ttl,
    )
    cli_sso_session_cache.attach_redis_cache(
        redis_cache,
        default_redis_ttl=CLI_SSO_SESSION_TTL_SECONDS,
    )
    if enable_redis_auth_cache is True:
        user_api_key_cache.attach_redis_cache(
            redis_cache,
            default_redis_ttl=litellm.default_redis_ttl,
        )
        verbose_proxy_logger.info(
            "enable_redis_auth_cache=True: attached Redis to "
            "user_api_key_cache — virtual-key lookups are now "
            "shared across all proxy workers."
        )
    else:
        verbose_proxy_logger.info(
            "enable_redis_auth_cache is not set: user_api_key_cache "
            "remains in-memory only (per-worker). Set "
            "litellm_settings.enable_redis_auth_cache: true to share "
            "the auth cache across workers and reduce DB load."
        )
    litellm_config_cache.redis_cache = redis_cache


def resolve_routing_plugins(
    plugin_paths: list,
    config_file_path: str | None,
    source_label: str,
) -> list:
    """
    Resolves a list of routing-plugin entries to live `RoutingPlugin` instances.
    Each string entry is resolved through `get_instance_fn` (the same dotted-path
    convention `litellm_settings.callbacks` uses, which resolves both local module
    files next to the config and modules installed as Python packages); non-string
    entries are assumed to already be instances and passed through. Raises at
    config-load time if any entry resolves to something that doesn't implement
    `RoutingPlugin`, rather than deferring to a confusing `AttributeError` on the
    first request that reaches the plugin pipeline. `source_label` names the config
    key being resolved so the error points the operator at the right place.
    """
    resolved_plugins = [
        get_instance_fn(value=plugin_path, config_file_path=config_file_path)
        if isinstance(plugin_path, str)
        else plugin_path
        for plugin_path in plugin_paths
    ]
    for plugin_path, resolved_plugin in zip(plugin_paths, resolved_plugins):
        # `@runtime_checkable` only checks that `run` exists as an attribute, not that
        # it's a coroutine function -- a synchronous `def run(self, context)` would pass
        # isinstance() here and only fail at request time with a confusing `TypeError:
        # object RoutingContext can't be used in 'await' expression`.
        if not isinstance(resolved_plugin, RoutingPlugin) or not inspect.iscoroutinefunction(
            getattr(resolved_plugin, "run", None)
        ):
            raise ValueError(
                f"{source_label} entry {plugin_path!r} resolved to {resolved_plugin!r}, which does "
                "not implement the RoutingPlugin interface (an async `run(context)` method). Fix the "
                "referenced module before starting the proxy."
            )
    return resolved_plugins


def resolve_complexity_router_plugins(
    model_name: str,
    complexity_router_config: dict,
    config_file_path: str | None,
) -> None:
    """
    Resolves `complexity_router_config["plugins"]` dotted-path strings to live
    instances in place, via `resolve_routing_plugins`.
    """
    plugin_paths = complexity_router_config.get("plugins")
    if not isinstance(plugin_paths, list):
        return

    complexity_router_config["plugins"] = resolve_routing_plugins(
        plugin_paths=plugin_paths,
        config_file_path=config_file_path,
        source_label=f"complexity_router_config.plugins on model {model_name!r}",
    )


class ProxyConfig:
    """
    Abstraction class on top of config loading/updating logic. Gives us one place to control all config updating logic.
    """

    def __init__(self) -> None:
        self.config: Dict[str, Any] = {}
        self._last_semantic_filter_config: Optional[Dict[str, Any]] = None
        self._last_hashicorp_vault_config: Optional[Dict[str, Any]] = None
        self.worker_registry: List["WorkerRegistryEntry"] = []

    def is_yaml(self, config_file_path: str) -> bool:
        if not os.path.isfile(config_file_path):
            return False

        _, file_extension = os.path.splitext(config_file_path)
        return file_extension.lower() == ".yaml" or file_extension.lower() == ".yml"

    def _load_yaml_file(self, file_path: str) -> dict:
        """
        Load and parse a YAML file
        """
        try:
            with open(file_path, "r") as file:
                return yaml.safe_load(file) or {}
        except Exception as e:
            raise Exception(f"Error loading yaml file {file_path}: {str(e)}")

    async def _get_config_from_file(self, config_file_path: Optional[str] = None) -> dict:
        """
        Given a config file path, load the config from the file.
        Args:
            config_file_path (str): path to the config file
        Returns:
            dict: config
        """
        global prisma_client, user_config_file_path

        file_path = config_file_path or user_config_file_path
        if config_file_path is not None:
            user_config_file_path = config_file_path
        # Load existing config
        ## Yaml
        if os.path.exists(f"{file_path}"):
            with open(f"{file_path}", "r") as config_file:
                config = yaml.safe_load(config_file)
        elif file_path is not None:
            raise Exception(f"Config file not found: {file_path}")
        else:
            config = {
                "model_list": [],
                "general_settings": {},
                "router_settings": {},
                "litellm_settings": {},
            }

        if config is None:
            raise Exception("Config cannot be None or Empty.")
        # Process includes
        config = self._process_includes(config=config, base_dir=os.path.dirname(os.path.abspath(file_path or "")))

        # verbose_proxy_logger.debug(f"loaded config={json.dumps(config, indent=4)}")
        return config

    def _process_includes(self, config: dict, base_dir: str) -> dict:
        """
        Process includes by appending their contents to the main config

        Handles nested config.yamls with `include` section

        Example config: This will get the contents from files in `include` and append it
        ```yaml
        include:
            - model_config.yaml

        litellm_settings:
            callbacks: ["prometheus"]
        ```
        """
        if "include" not in config:
            return config

        if not isinstance(config["include"], list):
            raise ValueError("'include' must be a list of file paths")

        # Load and append all included files
        for include_file in config["include"]:
            file_path = os.path.join(base_dir, include_file)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Included file not found: {file_path}")

            included_config = self._load_yaml_file(file_path)
            # Simply update/extend the main config with included config
            for key, value in included_config.items():
                if isinstance(value, list) and key in config:
                    config[key].extend(value)
                else:
                    config[key] = value

        # Remove the include directive
        del config["include"]
        return config

    async def save_config(self, new_config: dict, include_env_vars: bool = False):
        global prisma_client, general_settings, user_config_file_path, store_model_in_db
        # Load existing config
        ## DB - writes valid config to db
        """
        - Do not write restricted params like 'api_key' to the database
        - if api_key is passed, save that to the local environment or connected secret manage (maybe expose `litellm.save_secret()`)
        """

        if prisma_client is not None and (
            general_settings.get("store_model_in_db", False) is True or store_model_in_db
        ):
            # if using - db for config - models are in ModelTable

            # Make a copy to avoid mutating the original config
            config_to_save = new_config.copy()

            # environment_variables are persisted to the DB only when a caller
            # explicitly opts in. Most callers reach save_config after
            # get_config() merged YAML + OS env into new_config (with
            # os.environ/ placeholders already resolved to plaintext), so
            # persisting them here would snapshot file/container env vars into
            # a config row that then shadows those sources on every restart.
            # The dedicated /config/update path writes env vars directly, so
            # no current caller needs include_env_vars=True.
            if not include_env_vars:
                config_to_save.pop("environment_variables", None)

            # SECURITY: Always encrypt environment_variables before DB write.
            # _encrypt_env_variables_for_db is idempotent — a caller that
            # already encrypted the values (or re-submitted ciphertext read
            # back from the DB) will not get a stacked second layer.
            if "environment_variables" in config_to_save and config_to_save["environment_variables"]:
                config_to_save["environment_variables"] = self._encrypt_env_variables_for_db(
                    environment_variables=config_to_save["environment_variables"]
                )

            config_to_save.pop("model_list", None)
            await prisma_client.insert_data(data=config_to_save, table_name="config")
        else:
            # Save the updated config - if user is not using a dB
            ## YAML
            with open(f"{user_config_file_path}", "w") as config_file:
                yaml.dump(new_config, config_file, default_flow_style=False)

    async def save_environment_variables(self, updates: dict[str, str | None]) -> None:
        """Persist specific environment variables to the DB config row.

        Each key in ``updates`` is written to the ``environment_variables``
        config row; a ``None`` value deletes that key. Env vars the caller does
        not name are preserved, so a caller that owns a couple of keys can
        update just those without snapshotting unrelated (YAML/OS-sourced)
        values the way a full ``save_config`` write would. No-op when config is
        not DB-backed.
        """
        global prisma_client, general_settings, store_model_in_db
        if prisma_client is None or not (general_settings.get("store_model_in_db", False) is True or store_model_in_db):
            return

        row = await ConfigRepository(prisma_client).table.find_first(where={"param_name": "environment_variables"})
        existing: dict = dict(row.param_value) if row is not None and row.param_value is not None else {}

        to_set = {k: v for k, v in updates.items() if v is not None}
        encrypted = self._encrypt_env_variables_for_db(environment_variables=to_set) if to_set else {}
        deleted_keys = {k for k, v in updates.items() if v is None}
        merged = {**{k: v for k, v in existing.items() if k not in deleted_keys}, **encrypted}

        serialized = json.dumps(merged)
        await ConfigRepository(prisma_client).table.upsert(
            where={"param_name": "environment_variables"},
            data={
                "create": {"param_name": "environment_variables", "param_value": serialized},
                "update": {"param_value": serialized},
            },
        )
        await invalidate_config_param("environment_variables")

    def _check_for_os_environ_vars(
        self, config: dict, depth: int = 0, max_depth: int = DEFAULT_MAX_RECURSE_DEPTH
    ) -> dict:
        """
        Check for os.environ/ variables in the config and replace them with the actual values.
        Includes a depth limit to prevent infinite recursion.

        Args:
            config (dict): The configuration dictionary to process.
            depth (int): Current recursion depth.
            max_depth (int): Maximum allowed recursion depth.

        Returns:
            dict: Processed configuration dictionary.
        """
        if depth > max_depth:
            verbose_proxy_logger.warning(f"Maximum recursion depth ({max_depth}) reached while processing config.")
            return config

        for key, value in config.items():
            if isinstance(value, dict):
                config[key] = self._check_for_os_environ_vars(config=value, depth=depth + 1, max_depth=max_depth)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        item = self._check_for_os_environ_vars(config=item, depth=depth + 1, max_depth=max_depth)
            # if the value is a string and starts with "os.environ/" - then it's an environment variable
            elif isinstance(value, str) and value.startswith("os.environ/"):
                config[key] = get_secret(value)
        return config

    def _get_team_config(self, team_id: str, all_teams_config: List[Dict]) -> Dict:
        team_config: dict = {}
        for team in all_teams_config:
            if "team_id" not in team:
                raise Exception(f"team_id missing from team: {SENSITIVE_DATA_MASKER.mask_dict(team)}")
            if team_id == team["team_id"]:
                team_config = team
                break
        for k, v in team_config.items():
            if isinstance(v, str) and v.startswith("os.environ/"):
                team_config[k] = get_secret(v)
        return team_config

    def load_team_config(self, team_id: str):
        """
        - for a given team id
        - return the relevant completion() call params
        """

        # load existing config
        config = self.get_config_state()

        ## LITELLM MODULE SETTINGS (e.g. litellm.drop_params=True,..)
        litellm_settings = config.get("litellm_settings", {})
        all_teams_config = litellm_settings.get("default_team_settings", None)
        if all_teams_config is None:
            return {}
        team_config = self._get_team_config(team_id=team_id, all_teams_config=all_teams_config)
        return team_config

    def _init_coordination_redis(self, config: dict) -> RedisCache | None:
        """
        Builds the coordination Redis from `general_settings.coordination_redis`
        when present, attaching it to the proxy-level caches. Runs before cache
        init, so an explicit block takes precedence over borrowing the
        response-cache Redis and over the REDIS_* env fallback. Returns the
        built client (None when the block is absent) for the caller to publish.
        """
        settings = config.get("general_settings") or {}
        litellm_settings = config.get("litellm_settings") or {}
        raw_params = settings.get("coordination_redis")
        if raw_params is None:
            return None
        if not isinstance(raw_params, dict):
            raise ValueError("general_settings.coordination_redis must be a mapping of Redis connection params")

        coordination_params = CoordinationRedisParams(**_resolve_coordination_redis_env_refs(raw_params))
        if not coordination_params.has_connection_target():
            raise ValueError(
                "general_settings.coordination_redis needs a connection target: "
                "set one of host, url, startup_nodes, or sentinel_nodes"
            )

        coordination_redis_cache = _build_redis_usage_cache(coordination_params.model_dump(exclude_none=True))
        _attach_redis_usage_cache(
            coordination_redis_cache,
            enable_redis_auth_cache=litellm_settings.get("enable_redis_auth_cache", False) is True,
        )
        verbose_proxy_logger.info(
            "coordination_redis: using a standalone Redis from general_settings "
            "for usage tracking, rate limiting, and cross-pod coordination."
        )
        return coordination_redis_cache

    def _init_cache(
        self,
        cache_params: dict,
        enable_redis_auth_cache: bool = False,
    ) -> RedisCache | None:
        """
        Initializes the response cache and resolves the coordination Redis.

        Returns the coordination Redis for the caller to publish: an explicit
        coordination_redis block already set wins, else a plain-Redis response
        cache backend is borrowed, else the REDIS_* environment fallback applies.
        """
        from litellm import Cache

        if "default_in_memory_ttl" in cache_params:
            litellm.default_in_memory_ttl = cache_params["default_in_memory_ttl"]

        if "default_redis_ttl" in cache_params:
            litellm.default_redis_ttl = cache_params["default_redis_ttl"]

        litellm.cache = Cache(**cache_params)

        resolved_usage_cache = redis_usage_cache
        cache_backend = litellm.cache.cache if litellm.cache is not None else None
        if resolved_usage_cache is None:
            if isinstance(cache_backend, (RedisCache, RedisClusterCache)):
                ## INIT PROXY REDIS USAGE CLIENT ##
                resolved_usage_cache = cache_backend
            else:
                resolved_usage_cache = _build_redis_usage_cache_from_environment()
                if resolved_usage_cache is not None:
                    verbose_proxy_logger.info(
                        "Cache backend %s is not a Redis KV cache; built a standalone "
                        "Redis from REDIS_* environment variables for usage tracking, "
                        "rate limiting, and cross-pod coordination.",
                        type(cache_backend).__name__,
                    )

        if resolved_usage_cache is not None:
            # Note: PKCE verifier storage uses redis_usage_cache directly (not
            # user_api_key_cache) to avoid routing all API-key lookups through Redis.
            _attach_redis_usage_cache(resolved_usage_cache, enable_redis_auth_cache)
        elif litellm_config_cache.redis_cache is None:
            verbose_proxy_logger.info("litellm_config_cache: no Redis configured; cluster-wide cache sharing disabled.")
        return resolved_usage_cache

    def switch_on_llm_response_caching(self):
        """
        Enable caching on the router by setting cache_responses=True.
        This ensures caching works without needing caching=True in request body.
        Router passes caching=self.cache_responses to litellm.completion()
        """
        global llm_router
        import litellm

        if llm_router is not None and litellm.cache is not None and llm_router.cache_responses is not True:
            llm_router.cache_responses = True
            verbose_proxy_logger.debug("Set router.cache_responses=True after initializing cache")

    async def get_config(self, config_file_path: Optional[str] = None) -> dict:
        """
        Load config file
        Supports reading from:
        - .yaml file paths
        - LiteLLM connected DB
        - GCS
        - S3

        Args:
            config_file_path (str): path to the config file
        Returns:
            dict: config

        """
        global prisma_client, store_model_in_db
        # Load existing config

        if os.environ.get("LITELLM_CONFIG_BUCKET_NAME") is not None:
            bucket_name = os.environ.get("LITELLM_CONFIG_BUCKET_NAME")
            object_key = os.environ.get("LITELLM_CONFIG_BUCKET_OBJECT_KEY")
            bucket_type = os.environ.get("LITELLM_CONFIG_BUCKET_TYPE")
            verbose_proxy_logger.debug("bucket_name: %s, object_key: %s", bucket_name, object_key)
            if bucket_type == "gcs":
                config = await get_config_file_contents_from_gcs(bucket_name=bucket_name, object_key=object_key)
            else:
                config = get_file_contents_from_s3(bucket_name=bucket_name, object_key=object_key)

            if config is None:
                raise Exception("Unable to load config from given source.")
        else:
            # default to file

            config = await self._get_config_from_file(config_file_path=config_file_path)

        ## UPDATE CONFIG WITH DB
        if prisma_client is not None and store_model_in_db is True:
            config = await self._update_config_from_db(
                config=config,
                prisma_client=prisma_client,
                store_model_in_db=store_model_in_db,
            )

        ## PRINT YAML FOR CONFIRMING IT WORKS
        printed_yaml = copy.deepcopy(config)
        printed_yaml.pop("environment_variables", None)

        config = self._check_for_os_environ_vars(config=config)

        self.update_config_state(config=config)

        return config

    def update_config_state(self, config: dict):
        self.config = config

    def get_config_state(self):
        """
        Returns a deep copy of the config,

        Do this, to avoid mutating the config state outside of allowed methods
        """
        try:
            return copy.deepcopy(self.config)
        except Exception as e:
            verbose_proxy_logger.debug(
                "ProxyConfig:get_config_state(): Error returning copy of config state. self.config={}\nError: {}".format(
                    self.config, e
                )
            )
            return {}

    def load_credential_list(self, config: dict) -> List[CredentialItem]:
        """
        Load the credential list from the database
        """
        credential_list_dict = config.get("credential_list")
        credential_list = []
        if credential_list_dict:
            credential_list = [CredentialItem(**cred) for cred in credential_list_dict]
        return credential_list

    def parse_search_tools(self, config: dict) -> Optional[List[SearchToolTypedDict]]:
        """
        Parse and validate search tools from config.
        Loads environment variables and casts to SearchToolTypedDict.

        Args:
            config: Config dictionary containing search_tools

        Returns:
            List of validated SearchToolTypedDict or None if not configured
        """
        search_tools_raw = config.get("search_tools", None)
        if not search_tools_raw:
            # Check in general_settings
            general_settings = config.get("general_settings", {})
            if general_settings:
                search_tools_raw = general_settings.get("search_tools", None)

        if not search_tools_raw:
            return None

        search_tools_parsed: List[SearchToolTypedDict] = []

        print(  # noqa: T201
            "\033[32mLiteLLM: Proxy initialized with Search Tools:\033[0m"
        )

        for search_tool in search_tools_raw:
            # Display loaded search tool
            search_tool_name = search_tool.get("search_tool_name", "")
            search_provider = search_tool.get("litellm_params", {}).get("search_provider", "")
            print(  # noqa: T201
                f"\033[32m    {search_tool_name} ({search_provider})\033[0m"
            )

            # Handle os.environ/ variables in litellm_params
            litellm_params = search_tool.get("litellm_params", {})
            if litellm_params:
                for k, v in litellm_params.items():
                    if isinstance(v, str) and v.startswith("os.environ/"):
                        _v = v.replace("os.environ/", "")
                        v = get_secret(_v)
                        litellm_params[k] = v
                search_tool["litellm_params"] = litellm_params

            # Cast to SearchToolTypedDict for type safety
            try:
                search_tool_typed: SearchToolTypedDict = SearchToolTypedDict(**search_tool)  # type: ignore
                search_tools_parsed.append(search_tool_typed)
            except Exception as e:
                verbose_proxy_logger.error(f"Error parsing search tool {search_tool_name}: {str(e)}")
                continue

        return search_tools_parsed if search_tools_parsed else None

    # Environment variable keys that must not be overridden via config because
    # they can alter process execution, library loading, or network routing.
    _BLOCKED_ENV_KEYS: Set[str] = {
        "PATH",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "DYLD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONHOME",
        "HOME",
        "USER",
        "SHELL",
        "LOGNAME",
        "NO_PROXY",
        "no_proxy",
    }

    def _load_environment_variables(self, config: dict):
        ## ENVIRONMENT VARIABLES
        global premium_user
        environment_variables = config.get("environment_variables", None)
        if environment_variables:
            for key, value in environment_variables.items():
                if key in self._BLOCKED_ENV_KEYS:
                    verbose_proxy_logger.warning("Skipping blocked environment variable key: %s", key)
                    continue
                #########################################################
                # handles this scenario:
                # ```yaml
                # environment_variables:
                #     ARIZE_ENDPOINT: os.environ/ARIZE_ENDPOINT
                # ```
                #########################################################
                if isinstance(value, str) and value.startswith("os.environ/"):
                    resolved_secret_string: Optional[str] = get_secret_str(secret_name=value)
                    if resolved_secret_string is not None:
                        os.environ[key] = resolved_secret_string
                else:
                    #########################################################
                    # handles this scenario:
                    # ```yaml
                    # environment_variables:
                    #     ARIZE_ENDPOINT: https://otlp.arize.com/v1
                    # ```
                    #########################################################
                    os.environ[key] = str(value)

            # check if litellm_license in general_settings
            if "LITELLM_LICENSE" in environment_variables:
                _license_check.license_str = os.getenv("LITELLM_LICENSE", None)
                premium_user = _license_check.is_premium()
        return

    async def load_config(self, router: Optional[litellm.Router], config_file_path: str):
        """
        Load config values into proxy global state
        """
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
            use_queue, \
            proxy_budget_rescheduler_max_time, \
            proxy_budget_rescheduler_min_time, \
            ui_access_mode, \
            litellm_master_key_hash, \
            proxy_batch_write_at, \
            disable_spend_logs, \
            prompt_injection_detection_obj, \
            redis_usage_cache, \
            store_model_in_db, \
            premium_user, \
            open_telemetry_logger, \
            health_check_details, \
            proxy_batch_polling_interval, \
            proxy_config_reload_interval_seconds, \
            config_passthrough_endpoints

        config: dict = await self.get_config(config_file_path=config_file_path)

        self._load_environment_variables(config=config)

        ## Coordination Redis (before cache init, so the explicit block wins)
        coordination_redis_cache = self._init_coordination_redis(config=config)
        if coordination_redis_cache is not None:
            _set_redis_usage_cache(coordination_redis_cache)

        ## Callback settings
        callback_settings = config.get("callback_settings", {})
        if callback_settings:
            litellm.callback_settings = callback_settings

        ## LITELLM MODULE SETTINGS (e.g. litellm.drop_params=True,..)
        litellm_settings = config.get("litellm_settings", None)
        if litellm_settings is None:
            litellm_settings = {}
        if litellm_settings:
            # ANSI escape code for blue text
            blue_color_code = "\033[94m"
            reset_color_code = "\033[0m"
            for key, value in litellm_settings.items():
                if key == "cache" and value is True:
                    print(f"{blue_color_code}\nSetting Cache on Proxy")  # noqa: T201
                    from litellm.caching.caching import Cache

                    cache_params = {}
                    if "cache_params" in litellm_settings:
                        cache_params_in_config = litellm_settings["cache_params"]
                        # overwrite cache_params with cache_params_in_config
                        cache_params.update(cache_params_in_config)

                    cache_type = cache_params.get("type", "redis")

                    verbose_proxy_logger.debug("passed cache type=%s", cache_type)

                    if (cache_type == "redis" or cache_type == "redis-semantic") and len(cache_params.keys()) == 0:
                        cache_host = get_secret("REDIS_HOST", None)
                        cache_port = get_secret("REDIS_PORT", None)
                        cache_password = None
                        cache_params.update(
                            {
                                "type": cache_type,
                                "host": cache_host,
                                "port": cache_port,
                            }
                        )

                        if get_secret("REDIS_PASSWORD", None) is not None:
                            cache_password = get_secret("REDIS_PASSWORD", None)
                            cache_params.update(
                                {
                                    "password": cache_password,
                                }
                            )

                        # Assuming cache_type, cache_host, cache_port, and cache_password are strings
                        verbose_proxy_logger.debug(
                            "%sCache Type:%s %s",
                            blue_color_code,
                            reset_color_code,
                            cache_type,
                        )
                        verbose_proxy_logger.debug(
                            "%sCache Host:%s %s",
                            blue_color_code,
                            reset_color_code,
                            cache_host,
                        )
                        verbose_proxy_logger.debug(
                            "%sCache Port:%s %s",
                            blue_color_code,
                            reset_color_code,
                            cache_port,
                        )
                        verbose_proxy_logger.debug(
                            "%sCache Password:%s %s",
                            blue_color_code,
                            reset_color_code,
                            cache_password,
                        )

                    # users can pass os.environ/ variables on the proxy - we should read them from the env
                    for key, value in cache_params.items():
                        if isinstance(value, str) and value.startswith("os.environ/"):
                            cache_params[key] = get_secret(value)

                    ## to pass a complete url, or set ssl=True, etc. just set it as `os.environ[REDIS_URL] = <your-redis-url>`, _redis.py checks for REDIS specific environment variables
                    _set_redis_usage_cache(
                        self._init_cache(
                            cache_params=cache_params,
                            enable_redis_auth_cache=litellm_settings.get("enable_redis_auth_cache", False) is True,
                        )
                    )
                    if litellm.cache is not None:
                        verbose_proxy_logger.debug(f"{blue_color_code}Set Cache on LiteLLM Proxy{reset_color_code}")
                elif key == "cache" and value is False:
                    pass
                elif key == "global_prompt_directory":
                    from litellm.integrations.dotprompt import (
                        set_global_prompt_directory,
                    )

                    set_global_prompt_directory(value)
                    verbose_proxy_logger.info(
                        f"{blue_color_code}Set Global Prompt Directory on LiteLLM Proxy{reset_color_code}"
                    )
                elif key == "global_bitbucket_config":
                    from litellm.integrations.bitbucket import (
                        set_global_bitbucket_config,
                    )

                    set_global_bitbucket_config(value)
                    verbose_proxy_logger.info(
                        f"{blue_color_code}Set Global BitBucket Config on LiteLLM Proxy{reset_color_code}"
                    )
                elif key == "global_gitlab_config":
                    from litellm.integrations.gitlab import set_global_gitlab_config

                    set_global_gitlab_config(value)
                    verbose_proxy_logger.info(
                        f"{blue_color_code}Set Global Gitlab Config on LiteLLM Proxy{reset_color_code}"
                    )
                elif key == "priority_reservation_settings":
                    from litellm.types.utils import PriorityReservationSettings

                    litellm.priority_reservation_settings = PriorityReservationSettings(**value)
                elif key == "callbacks":
                    initialize_callbacks_on_proxy(
                        value=value,
                        premium_user=premium_user,
                        config_file_path=config_file_path,
                        litellm_settings=litellm_settings,
                        callback_specific_params=callback_settings,
                    )

                elif key == "model_group_settings":
                    from litellm.types.router import ModelGroupSettings

                    litellm.model_group_settings = ModelGroupSettings(**value)

                elif key == "post_call_rules":
                    litellm.post_call_rules = [get_instance_fn(value=value, config_file_path=config_file_path)]
                    verbose_proxy_logger.debug(f"litellm.post_call_rules: {litellm.post_call_rules}")
                elif key == "max_budget":
                    litellm.max_budget = float(value)
                elif key == "max_internal_user_budget":
                    litellm.max_internal_user_budget = float(value)  # type: ignore
                elif key == "default_max_internal_user_budget":
                    litellm.default_max_internal_user_budget = float(value)
                    if litellm.max_internal_user_budget is None:
                        litellm.max_internal_user_budget = litellm.default_max_internal_user_budget
                elif key == "default_internal_user_params" and isinstance(value, dict):
                    litellm.default_internal_user_params = (
                        {**value, "max_budget": float(value["max_budget"])}
                        if value.get("max_budget") is not None
                        else value
                    )
                    verbose_proxy_logger.debug(
                        f"{blue_color_code} setting litellm.{key}={_redact_general_setting_value(key, litellm.default_internal_user_params, is_full_admin=False)}{reset_color_code}"
                    )
                elif key == "custom_provider_map":
                    from litellm.utils import custom_llm_setup

                    litellm.custom_provider_map = [
                        {
                            "provider": item["provider"],
                            "custom_handler": get_instance_fn(
                                value=item["custom_handler"],
                                config_file_path=config_file_path,
                            ),
                        }
                        for item in value
                    ]

                    custom_llm_setup()
                elif key == "success_callback":
                    litellm.success_callback = []

                    # initialize success callbacks
                    for callback in value:
                        # user passed custom_callbacks.async_on_succes_logger. They need us to import a function
                        if "." in callback:
                            litellm.logging_callback_manager.add_litellm_success_callback(
                                get_instance_fn(
                                    value=callback,
                                    config_file_path=config_file_path,
                                )
                            )
                        # these are litellm callbacks - "langfuse", "sentry", "wandb"
                        else:
                            litellm.logging_callback_manager.add_litellm_success_callback(callback)
                            if "prometheus" in callback:
                                from litellm.integrations.prometheus import (
                                    PrometheusLogger,
                                )

                                if PrometheusLogger is not None:
                                    verbose_proxy_logger.debug("mounting metrics endpoint")
                                    PrometheusLogger._mount_metrics_endpoint()
                    print(  # noqa: T201
                        f"{blue_color_code} Initialized Success Callbacks - {litellm.success_callback} {reset_color_code}"
                    )
                elif key == "failure_callback":
                    litellm.failure_callback = []

                    # initialize success callbacks
                    for callback in value:
                        # user passed custom_callbacks.async_on_succes_logger. They need us to import a function
                        if "." in callback:
                            litellm.logging_callback_manager.add_litellm_failure_callback(
                                get_instance_fn(
                                    value=callback,
                                    config_file_path=config_file_path,
                                )
                            )
                        # these are litellm callbacks - "langfuse", "sentry", "wandb"
                        else:
                            litellm.logging_callback_manager.add_litellm_failure_callback(callback)
                    print(  # noqa: T201
                        f"{blue_color_code} Initialized Failure Callbacks - {litellm.failure_callback} {reset_color_code}"
                    )
                elif key == "audit_log_callbacks":
                    from litellm.proxy.management_helpers.audit_logs import (
                        reset_audit_log_callback_cache,
                    )

                    reset_audit_log_callback_cache()
                    litellm.audit_log_callbacks = []

                    for callback in value:
                        if "." in callback:
                            litellm.audit_log_callbacks.append(
                                get_instance_fn(
                                    value=callback,
                                    config_file_path=config_file_path,
                                )
                            )
                        else:
                            litellm.audit_log_callbacks.append(callback)

                    _store_audit_logs = litellm_settings.get("store_audit_logs", litellm.store_audit_logs)
                    if _store_audit_logs:
                        print(  # noqa: T201
                            f"{blue_color_code} Initialized Audit Log Callbacks - {litellm.audit_log_callbacks} {reset_color_code}"
                        )
                    else:
                        verbose_proxy_logger.warning(
                            "'audit_log_callbacks' is configured but 'store_audit_logs' is not enabled. "
                            "Audit log callbacks will not fire until 'store_audit_logs: true' is added to litellm_settings."
                        )
                elif key == "cache_params":
                    # this is set in the cache branch
                    # see usage here: https://docs.litellm.ai/docs/proxy/caching
                    pass
                elif key == "responses":
                    # Initialize global polling via cache settings
                    global polling_via_cache_enabled, native_background_mode, polling_cache_ttl
                    background_mode = value.get("background_mode", {})
                    polling_via_cache_enabled = background_mode.get("polling_via_cache", False)
                    native_background_mode = background_mode.get("native_background_mode", [])
                    polling_cache_ttl = background_mode.get("ttl", 3600)
                    verbose_proxy_logger.debug(
                        f"{blue_color_code} Initialized polling via cache: enabled={polling_via_cache_enabled}, native_background_mode={native_background_mode}, ttl={polling_cache_ttl}{reset_color_code}"
                    )
                elif key == "max_ui_session_budget":
                    litellm.max_ui_session_budget = float(value) if value is not None else None
                    verbose_proxy_logger.debug(
                        f"{blue_color_code} setting litellm.max_ui_session_budget={litellm.max_ui_session_budget}{reset_color_code}"
                    )
                elif key == "default_team_settings":
                    for idx, team_setting in enumerate(value):  # run through pydantic validation
                        try:
                            TeamDefaultSettings(**team_setting)
                        except Exception:
                            if isinstance(team_setting, dict):
                                raise Exception(
                                    f"team_id missing from default_team_settings at index={idx}\npassed in value={team_setting.keys()}"
                                )
                            raise Exception(
                                f"team_id missing from default_team_settings at index={idx}\npassed in value={type(team_setting)}"
                            )
                    verbose_proxy_logger.debug(
                        f"{blue_color_code} setting litellm.{key}={_redact_general_setting_value(key, value, is_full_admin=False)}{reset_color_code}"
                    )
                    setattr(litellm, key, value)
                elif key == "upperbound_key_generate_params":
                    if value is not None and isinstance(value, dict):
                        for _k, _v in value.items():
                            if isinstance(_v, str) and _v.startswith("os.environ/"):
                                value[_k] = get_secret(_v)
                        litellm.upperbound_key_generate_params = LiteLLM_UpperboundKeyGenerateParams(**value)
                    else:
                        raise Exception(f"Invalid value set for upperbound_key_generate_params - value={value}")
                elif key == "json_logs" and value is True:
                    litellm.json_logs = True
                    litellm._turn_on_json()
                    verbose_proxy_logger.debug(f"{blue_color_code} Enabled JSON logging via config{reset_color_code}")
                elif key == "budget_reset_time":
                    from litellm.proxy.common_utils.timezone_utils import (
                        parse_budget_reset_time,
                    )

                    parse_budget_reset_time(value)
                    setattr(litellm, key, value)
                else:
                    verbose_proxy_logger.debug(
                        f"{blue_color_code} setting litellm.{key}={_redact_general_setting_value(key, value, is_full_admin=False)}{reset_color_code}"
                    )
                    setattr(litellm, key, value)
                    if key == "request_timeout":
                        litellm.request_timeout_explicitly_set = True
                    if key in {"s3_audit_callback_params", "s3_callback_params"}:
                        from litellm.integrations.s3_v2 import S3Logger as S3V2Logger
                        from litellm.litellm_core_utils.litellm_logging import (
                            _in_memory_loggers,
                        )
                        from litellm.proxy.management_helpers.audit_logs import (
                            reset_audit_log_callback_cache,
                        )

                        reset_audit_log_callback_cache()
                        _in_memory_loggers[:] = [cb for cb in _in_memory_loggers if not isinstance(cb, S3V2Logger)]

        ## GENERAL SERVER SETTINGS (e.g. master key,..) # do this after initializing litellm, to ensure sentry logging works for proxylogging
        general_settings = config.get("general_settings", {})
        if general_settings is None:
            general_settings = {}
        _enable_hc_routing = False
        _hc_staleness = None
        _hc_ignore_transient = False
        if general_settings:
            ### LOAD KEY MANAGEMENT SETTINGS FIRST (needed for custom secret manager) ###
            key_management_settings = general_settings.get("key_management_settings", None)
            if key_management_settings is not None:
                litellm._key_management_settings = KeyManagementSettings(**key_management_settings)

            ### LOAD SECRET MANAGER ###
            key_management_system = general_settings.get("key_management_system", None)
            self.initialize_secret_manager(
                key_management_system=key_management_system,
                config_file_path=config_file_path,
            )
            ### [DEPRECATED] LOAD FROM GOOGLE KMS ### old way of loading from google kms
            use_google_kms = general_settings.get("use_google_kms", False)
            load_google_kms(use_google_kms=use_google_kms)
            ### [DEPRECATED] LOAD FROM AZURE KEY VAULT ### old way of loading from azure secret manager
            use_azure_key_vault = general_settings.get("use_azure_key_vault", False)
            load_from_azure_key_vault(use_azure_key_vault=use_azure_key_vault)
            ### ALERTING ###
            self._load_alerting_settings(general_settings=general_settings)
            ### PLUGINS ###
            register_plugins_from_config(general_settings)
            ### CONNECT TO DATABASE ###
            database_url = general_settings.get("database_url", None)
            if database_url and database_url.startswith("os.environ/"):
                verbose_proxy_logger.debug("Resolving database_url via secret manager")
                database_url = get_secret(database_url)
                verbose_proxy_logger.debug("Resolved database_url from secret manager")
            ### MASTER KEY ###
            master_key = general_settings.get("master_key", get_secret("LITELLM_MASTER_KEY", None))

            if master_key and master_key.startswith("os.environ/"):
                master_key = get_secret(master_key)  # type: ignore

            if master_key is not None and isinstance(master_key, str):
                litellm_master_key_hash = hash_token(master_key)
            else:
                verbose_proxy_logger.critical(
                    "LITELLM_MASTER_KEY is not set! All requests will be treated as INTERNAL_USER with no admin access. Set LITELLM_MASTER_KEY for production use."
                )
            ### USER API KEY CACHE TTL (in-memory + Redis when Redis auth sharing is enabled) ###
            user_api_key_cache_ttl = general_settings.get("user_api_key_cache_ttl", None)
            if user_api_key_cache_ttl is not None:
                ttl = float(user_api_key_cache_ttl)
                # Mirror TTL on Redis as well when ``litellm_settings.enable_redis_auth_cache``
                # attaches Redis to ``user_api_key_cache``; otherwise DualCache misses in
                # memory fall back to a key that outlasts ``user_api_key_cache_ttl``.
                user_api_key_cache.update_cache_ttl(
                    default_in_memory_ttl=ttl,
                    default_redis_ttl=ttl,
                )

            ### PKCE MULTI-INSTANCE PREREQUISITE CHECK ###
            # PKCE verifiers are stored in redis_usage_cache when available so they can
            # be read back by any instance (not just the one that started the auth flow).
            use_pkce = os.getenv("GENERIC_CLIENT_USE_PKCE", "false").lower() == "true"
            if use_pkce and redis_usage_cache is None:
                global _pkce_no_redis_warning_emitted
                if not _pkce_no_redis_warning_emitted:
                    _pkce_no_redis_warning_emitted = True
                    verbose_proxy_logger.warning(
                        "GENERIC_CLIENT_USE_PKCE=true but Redis is not configured for LiteLLM caching. "
                        "PKCE verifiers will not be shared across instances — callbacks may land on a "
                        "different pod than the login request and fail silently. "
                        "Configure Redis via the 'cache' section in your proxy config, "
                        "or enable sticky sessions for single-instance deployments. "
                        "Set PKCE_STRICT_CACHE_MISS=true to fail fast with a 401 on cache misses "
                        "instead of continuing without a code_verifier."
                    )

            ### CONTROL PLANE CODE-EXCHANGE PREREQUISITE CHECK ###
            cp_url = general_settings.get("control_plane_url")
            if cp_url and redis_usage_cache is None:
                global _cp_no_redis_warning_emitted
                if not _cp_no_redis_warning_emitted:
                    _cp_no_redis_warning_emitted = True
                    verbose_proxy_logger.warning(
                        "control_plane_url is configured but Redis is not configured for LiteLLM caching. "
                        "Login codes (SSO and /v3/login) will not be shared across instances — "
                        "the /v3/login/exchange call may land on a different pod and fail with 401. "
                        "Configure Redis via the 'cache' section in your proxy config, "
                        "or ensure sticky sessions for single-instance deployments."
                    )

            ### STORE MODEL IN DB ### feature flag for `/model/new`
            store_model_in_db = general_settings.get("store_model_in_db", False)
            if store_model_in_db is None:
                store_model_in_db = False
            general_settings["store_model_in_db"] = store_model_in_db
            ### CUSTOM API KEY AUTH ###
            ## pass filepath
            custom_auth = general_settings.get("custom_auth", None)
            if custom_auth is not None:
                user_custom_auth = get_instance_fn(value=custom_auth, config_file_path=config_file_path)
            warn_once_if_custom_auth_skips_common_checks(
                custom_auth_configured=custom_auth is not None,
                run_common_checks=bool(general_settings.get("custom_auth_run_common_checks", False)),
            )

            custom_key_generate = general_settings.get("custom_key_generate", None)
            if custom_key_generate is not None:
                user_custom_key_generate = get_instance_fn(value=custom_key_generate, config_file_path=config_file_path)

            custom_key_update = general_settings.get("custom_key_update", None)
            if custom_key_update is not None:
                user_custom_key_update = get_instance_fn(value=custom_key_update, config_file_path=config_file_path)

            custom_sso = general_settings.get("custom_sso", None)
            if custom_sso is not None:
                user_custom_sso = get_instance_fn(value=custom_sso, config_file_path=config_file_path)

            custom_ui_sso_sign_in_handler = general_settings.get("custom_ui_sso_sign_in_handler", None)
            if custom_ui_sso_sign_in_handler is not None:
                user_custom_ui_sso_sign_in_handler = get_instance_fn(
                    value=custom_ui_sso_sign_in_handler,
                    config_file_path=config_file_path,
                )

            if enterprise_proxy_config is not None:
                await enterprise_proxy_config.load_enterprise_config(general_settings)

            ## pass through endpoints
            if general_settings.get("pass_through_endpoints", None) is not None:
                config_passthrough_endpoints = general_settings["pass_through_endpoints"]
                await initialize_pass_through_endpoints(
                    pass_through_endpoints=general_settings["pass_through_endpoints"],
                    config_file_path=config_file_path,
                )

            ## ADMIN UI ACCESS ##
            ui_access_mode = general_settings.get("ui_access_mode", "all")  # can be either ["admin_only" or "all"]
            ### ALLOWED IP ###
            allowed_ips = general_settings.get("allowed_ips", None)
            if allowed_ips is not None and premium_user is False:
                raise ValueError(
                    "allowed_ips is an Enterprise Feature. Please add a valid LITELLM_LICENSE to your envionment."
                )
            ## BUDGET RESCHEDULER ##
            proxy_budget_rescheduler_min_time = general_settings.get(
                "proxy_budget_rescheduler_min_time", proxy_budget_rescheduler_min_time
            )
            proxy_budget_rescheduler_max_time = general_settings.get(
                "proxy_budget_rescheduler_max_time", proxy_budget_rescheduler_max_time
            )
            ## BATCH POLLING INTERVAL ##
            proxy_batch_polling_interval = general_settings.get(
                "proxy_batch_polling_interval", proxy_batch_polling_interval
            )
            ## BATCH WRITER ##
            proxy_batch_write_at = general_settings.get("proxy_batch_write_at", proxy_batch_write_at)
            ## DB CONFIG RELOAD INTERVAL ##
            proxy_config_reload_interval_seconds = general_settings.get(
                "proxy_config_reload_interval_seconds", proxy_config_reload_interval_seconds
            )
            ## DISABLE SPEND LOGS ## - gives a perf improvement
            disable_spend_logs = general_settings.get("disable_spend_logs", disable_spend_logs)
            ### BACKGROUND HEALTH CHECKS ###
            # Enable background health checks
            use_background_health_checks = general_settings.get("background_health_checks", False)
            # Enable shared health check state across pods (requires Redis)
            use_shared_health_check = general_settings.get("use_shared_health_check", False)
            health_check_interval = general_settings.get("health_check_interval", DEFAULT_HEALTH_CHECK_INTERVAL)
            health_check_concurrency = general_settings.get("health_check_concurrency", None)
            health_check_details = general_settings.get("health_check_details", True)
            ### INTERACTIONS API SCHEMA ###
            _use_legacy_interactions_schema = general_settings.get("use_legacy_interactions_schema")
            if _use_legacy_interactions_schema is not None:
                if isinstance(_use_legacy_interactions_schema, str):
                    litellm.use_legacy_interactions_schema = _use_legacy_interactions_schema.lower() == "true"
                else:
                    litellm.use_legacy_interactions_schema = bool(_use_legacy_interactions_schema)
            # Health-check-driven routing (opt-in, passes through to Router later)
            _enable_hc_routing = general_settings.get("enable_health_check_routing", False)
            _hc_staleness = general_settings.get("health_check_staleness_threshold", None)
            _hc_ignore_transient = general_settings.get("health_check_ignore_transient_errors", False)
            verbose_proxy_logger.info(
                "background_health_check_config enabled=%s shared=%s interval_seconds=%s max_concurrency=%s details=%s health_check_routing=%s",
                use_background_health_checks,
                use_shared_health_check,
                health_check_interval,
                health_check_concurrency,
                health_check_details,
                _enable_hc_routing,
            )

            ### RBAC ###
            rbac_role_permissions = general_settings.get("role_permissions", None)
            if rbac_role_permissions is not None:
                general_settings["role_permissions"] = [  # validate role permissions
                    RoleBasedPermissions(**role_permission) for role_permission in rbac_role_permissions
                ]

            ### SSRF URL VALIDATION SETTINGS ###
            _apply_ssrf_general_settings(general_settings)

            ## check if user has set a premium feature in general_settings
            if general_settings.get("enforced_params") is not None and premium_user is not True:
                raise ValueError("Trying to use `enforced_params`" + CommonProxyErrors.not_premium_user.value)

            # check if litellm_license in general_settings
            if "litellm_license" in general_settings:
                _license_check.license_str = general_settings["litellm_license"]
                premium_user = _license_check.is_premium()

        router_params: dict = {
            "cache_responses": litellm.cache is not None,  # cache if user passed in cache values
        }
        # Health-check-driven routing params (from general_settings)
        if _enable_hc_routing:
            router_params["enable_health_check_routing"] = True
        if _hc_staleness is not None:
            router_params["health_check_staleness_threshold"] = _hc_staleness
        if _hc_ignore_transient:
            router_params["health_check_ignore_transient_errors"] = True
        ## MODEL LIST
        model_list = config.get("model_list", None)
        if model_list:
            router_params["model_list"] = model_list
            print(  # noqa: T201
                "\033[32mLiteLLM: Proxy initialized with Config, Set models:\033[0m"
            )
            for model in model_list:
                ### LOAD FROM os.environ/ ###
                for k, v in model["litellm_params"].items():
                    if isinstance(v, str) and v.startswith("os.environ/"):
                        model["litellm_params"][k] = get_secret(v)
                complexity_router_config = model["litellm_params"].get("complexity_router_config")
                if isinstance(complexity_router_config, dict):
                    resolve_complexity_router_plugins(
                        model_name=model.get("model_name", ""),
                        complexity_router_config=complexity_router_config,
                        config_file_path=config_file_path,
                    )
                print(f"\033[32m    {model.get('model_name', '')}\033[0m")  # noqa: T201
                litellm_model_name = model["litellm_params"]["model"]
                litellm_model_api_base = model["litellm_params"].get("api_base", None)
                if "ollama" in litellm_model_name and litellm_model_api_base is None:
                    run_ollama_serve()

        ## ASSISTANT SETTINGS
        assistants_config: Optional[AssistantsTypedDict] = None
        assistant_settings = config.get("assistant_settings", None)
        if assistant_settings:
            for k, v in assistant_settings["litellm_params"].items():
                if isinstance(v, str) and v.startswith("os.environ/"):
                    _v = v.replace("os.environ/", "")
                    v = os.getenv(_v)
                    assistant_settings["litellm_params"][k] = v
            assistants_config = AssistantsTypedDict(**assistant_settings)  # type: ignore

        ## SEARCH TOOLS SETTINGS
        search_tools: Optional[List[SearchToolTypedDict]] = self.parse_search_tools(config)

        ## SANDBOX TOOLS SETTINGS
        from litellm.sandbox.sandbox_tools import register_sandbox_tools

        register_sandbox_tools(config.get("sandbox_tools") or [])

        ## /fine_tuning/jobs endpoints config
        finetuning_config = config.get("finetune_settings", None)
        set_fine_tuning_config(config=finetuning_config)

        ## /files endpoint config
        files_config = config.get("files_settings", None)
        set_files_config(config=files_config)

        ## default config for vertex ai routes
        default_vertex_config = config.get("default_vertex_config", None)
        passthrough_endpoint_router.set_default_vertex_config(config=default_vertex_config)

        ## ROUTER SETTINGS (e.g. routing_strategy, ...)
        router_settings = config.get("router_settings", None)

        if router_settings and isinstance(router_settings, dict):
            # model list and search_tools already set
            exclude_args = {
                "model_list",
                "search_tools",
            }

            available_args = [x for x in litellm.Router.get_valid_args() if x not in exclude_args]

            for k, v in router_settings.items():
                if k in available_args:
                    if k == "plugins" and isinstance(v, list):
                        v = resolve_routing_plugins(
                            plugin_paths=v,
                            config_file_path=config_file_path,
                            source_label="router_settings.plugins",
                        )
                    router_params[k] = v
                elif k in {"health_check_interval", "health_check_concurrency"}:
                    raise ValueError(
                        f"'{k}' is NOT a valid router_settings parameter. Please move it to 'general_settings'."
                    )
                else:
                    verbose_proxy_logger.warning(
                        f"Key '{k}' is not a valid argument for Router.__init__(). Ignoring this key."
                    )
        router = litellm.Router(
            **router_params,
            assistants_config=assistants_config,
            search_tools=search_tools,
            router_general_settings=RouterGeneralSettings(
                async_only_mode=True  # only init async clients
            ),
            ignore_invalid_deployments=True,  # don't raise an error if a deployment is invalid
        )  # type: ignore

        if redis_usage_cache is not None and router.cache.redis_cache is None:
            router._update_redis_cache(cache=redis_usage_cache)

        # Guardrail settings

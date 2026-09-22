### Hide pydantic namespace conflict warnings globally ###
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", message=".*conflict with protected namespace.*")
# Suppress Pydantic 2.11+ deprecation warning about accessing model_fields on instances
# This warning can accumulate during streaming and cause memory leaks
warnings.filterwarnings("ignore", message=".*Accessing the.*attribute on the instance is deprecated.*")
### INIT VARIABLES #########################
import threading
import os

# Load .env before any other litellm imports so env vars (e.g. LITELLM_UI_SESSION_DURATION) are available
import dotenv as _dotenv


def _dev_env_hot_reload_enabled() -> bool:
    """The proxy exports this flag when started with ``--reload``. A reloaded
    worker is a fresh process that inherits the reloader's environment, so an
    edited ``.env`` value stays masked by the stale inherited one unless we
    let the file win; overriding makes the edit take effect on reload."""
    return os.getenv("LITELLM_DEV_ENV_HOT_RELOAD") == "True"


if os.getenv("LITELLM_MODE", "DEV") == "DEV":
    _dotenv.load_dotenv(override=_dev_env_hot_reload_enabled())

from typing import (
    Callable,
    List,
    Optional,
    Dict,
    Union,
    Any,
    Literal,
    get_args,
    TYPE_CHECKING,
    Tuple,
    overload,
    Type,
)
from litellm.types.integrations.datadog import DatadogInitParams
from litellm.types.integrations.newrelic import NewRelicInitParams
from litellm._logging import (
    set_verbose,
    _turn_on_debug,
    verbose_logger,
    json_logs,
    _turn_on_json,
    log_level,
)
import re
from litellm.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_FLUSH_INTERVAL_SECONDS,
    ROUTER_MAX_FALLBACKS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REPLICATE_POLLING_RETRIES,
    DEFAULT_REPLICATE_POLLING_DELAY_SECONDS,
    LITELLM_CHAT_PROVIDERS,
    HUMANLOOP_PROMPT_CACHE_TTL_SECONDS,
    OPENAI_CHAT_COMPLETION_PARAMS,
    OPENAI_CHAT_COMPLETION_PARAMS as _openai_completion_params,  # backwards compatibility
    OPENAI_FINISH_REASONS,
    OPENAI_FINISH_REASONS as _openai_finish_reasons,  # backwards compatibility
    openai_compatible_endpoints,
    openai_compatible_providers,
    openai_text_completion_compatible_providers,
    _openai_like_providers,
    replicate_models,
    clarifai_models,
    huggingface_models,
    modelscope_models,
    empower_models,
    together_ai_models,
    baseten_models,
    WANDB_MODELS,
    REPEATED_STREAMING_CHUNK_LIMIT,
    request_timeout,
    request_timeout_explicitly_set as request_timeout_explicitly_set,
    open_ai_embedding_models,
    cohere_embedding_models,
    bedrock_embedding_models,
    known_tokenizer_config,
    BEDROCK_INVOKE_PROVIDERS_LITERAL,
    BEDROCK_EMBEDDING_PROVIDERS_LITERAL,
    BEDROCK_CONVERSE_MODELS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_SOFT_BUDGET,
    DEFAULT_ALLOWED_FAILS,
)
import httpx

# register_async_client_cleanup is lazy-loaded and called on first access

litellm_mode = os.getenv("LITELLM_MODE", "DEV")  # "PRODUCTION", "DEV"


####################################################
if set_verbose:
    _turn_on_debug()
####################################################
### Callbacks /Logging / Success / Failure Handlers #####
CALLBACK_TYPES = Union[str, Callable, "CustomLogger"]  # CustomLogger is lazy-loaded
input_callback: List[CALLBACK_TYPES] = []
success_callback: List[CALLBACK_TYPES] = []
failure_callback: List[CALLBACK_TYPES] = []
service_callback: List[CALLBACK_TYPES] = []
audit_log_callbacks: List[CALLBACK_TYPES] = []
# logging_callback_manager is lazy-loaded via __getattr__
_custom_logger_compatible_callbacks_literal = Literal[
    "lago",
    "openmeter",
    "logfire",
    "literalai",
    "litellm_agent",
    "dynamic_rate_limiter",
    "dynamic_rate_limiter_v3",
    "langsmith",
    "prometheus",
    "otel",
    "datadog",
    "datadog_metrics",
    "datadog_llm_observability",
    "galileo",
    "braintrust",
    "arize",
    "arize_phoenix",
    "langtrace",
    "gcs_bucket",
    "azure_storage",
    "opik",
    "argilla",
    "mlflow",
    "langfuse",
    "langfuse_otel",
    "weave_otel",
    "pagerduty",
    "humanloop",
    "azure_sentinel",
    "gcs_pubsub",
    "agentops",
    "anthropic_cache_control_hook",
    "generic_api",
    "resend_email",
    "sendgrid_email",
    "smtp_email",
    "deepeval",
    "s3_v2",
    "aws_sqs",
    "vector_store_pre_call_hook",
    "dotprompt",
    "bitbucket",
    "gitlab",
    "cloudzero",
    "focus",
    "mavvrik",
    "vantage",
    "posthog",
    "levo",
    "compression_interception",
    "newrelic",
]
cold_storage_custom_logger: Optional[_custom_logger_compatible_callbacks_literal] = None
logged_real_time_event_types: Optional[Union[List[str], Literal["*"]]] = None
_known_custom_logger_compatible_callbacks: List = list(get_args(_custom_logger_compatible_callbacks_literal))
callbacks: List[
    Union[Callable, _custom_logger_compatible_callbacks_literal, "CustomLogger"]  # CustomLogger is lazy-loaded
] = []
callback_settings: Dict[str, Dict[str, Any]] = {}
initialized_langfuse_clients: int = 0
langfuse_default_tags: Optional[List[str]] = None
langsmith_batch_size: Optional[int] = None
prometheus_initialize_budget_metrics: Optional[bool] = False
prometheus_latency_buckets: Optional[List[float]] = None
require_auth_for_metrics_endpoint: Optional[bool] = True
argilla_batch_size: Optional[int] = None
datadog_use_v1: Optional[bool] = False  # if you want to use v1 datadog logged payload.
gcs_pub_sub_use_v1: Optional[bool] = False  # if you want to use v1 gcs pubsub logged payload
generic_api_use_v1: Optional[bool] = False  # if you want to use v1 generic api logged payload
argilla_transformation_object: Optional[Dict[str, Any]] = None
_async_input_callback: List[Union[str, Callable, "CustomLogger"]] = (  # CustomLogger is lazy-loaded
    []
)  # internal variable - async custom callbacks are routed here.
_async_success_callback: List[Union[str, Callable, "CustomLogger"]] = (  # CustomLogger is lazy-loaded
    []
)  # internal variable - async custom callbacks are routed here.
_async_failure_callback: List[Union[str, Callable, "CustomLogger"]] = (  # CustomLogger is lazy-loaded
    []
)  # internal variable - async custom callbacks are routed here.
pre_call_rules: List[Callable] = []
post_call_rules: List[Callable] = []
turn_off_message_logging: Optional[bool] = False
standard_logging_payload_excluded_fields: Optional[List[str]] = (
    None  # Fields to exclude from StandardLoggingPayload before callbacks receive it
)
log_raw_request_response: bool = False
redact_messages_in_exceptions: Optional[bool] = False
redact_user_api_key_info: Optional[bool] = False
# When True (default — preserves historical behavior), the Router appends
# internal config names (model_group, fallback model groups, deployment
# timeouts, fallback failure details) onto exception messages and surfaces
# them to clients via ProxyException.message. Set to False if you do NOT
# want the proxy's internal model_name / fallback wiring visible to clients.
# Deprecation: planned to flip to False (redact by default) in a future
# major release; opt in early with `litellm.expose_router_debug_in_errors
# = False`.
expose_router_debug_in_errors: bool = True
filter_invalid_headers: Optional[bool] = False
add_user_information_to_llm_headers: Optional[bool] = (
    None  # adds user_id, team_id, token hash (params from StandardLoggingMetadata) to request headers
)
overwrite_user_with_key_hash: bool = (
    False  # force the outgoing `user` param to the hashed api key, so providers see a stable, tamper-proof id
)
store_audit_logs = False  # Enterprise feature, allow users to see audit logs
skip_system_message_in_guardrail: bool = False
skip_tool_message_in_guardrail: bool = False
### end of callbacks #############

email: Optional[str] = (
    None  # Not used anymore, will be removed in next MAJOR release - https://github.com/BerriAI/litellm/discussions/648
)
token: Optional[str] = (
    None  # Not used anymore, will be removed in next MAJOR release - https://github.com/BerriAI/litellm/discussions/648
)
telemetry = True
max_tokens: int = DEFAULT_MAX_TOKENS  # OpenAI Defaults
drop_params = bool(os.getenv("LITELLM_DROP_PARAMS", False))
modify_params = bool(os.getenv("LITELLM_MODIFY_PARAMS", False))
use_chat_completions_url_for_anthropic_messages: bool = bool(
    os.getenv("LITELLM_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES", False)
)  # When True, routes OpenAI /v1/messages requests to chat/completions instead of the Responses API
# When True, strip the OpenAI-flavored `usage.total_tokens` field that
# LiteLLM injects into non-streaming /v1/messages responses, bringing the
# wire response into line with the Anthropic spec (matches the streaming
# SSE path, which already omits total_tokens). Default False to preserve
# backward compatibility for clients that read the LiteLLM-shaped
# `usage.total_tokens` today. Planned to flip to True in a future major
# release; opt in early via Python:
#   `litellm.strip_anthropic_total_tokens = True`
# Or via `litellm_settings.strip_anthropic_total_tokens: true` in
# config.yaml.
strip_anthropic_total_tokens: bool = False
route_all_chat_openai_to_responses: bool = (
    os.getenv("LITELLM_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES", "false").lower() == "true"
)  # When True, routes all OpenAI /chat/completions requests through the Responses API bridge
# When True, Gemini/Vertex Live setup is deferred until client `session.update`.
# Default False preserves historical behavior (auto-send setup on connect).
gemini_live_defer_setup: bool = os.getenv("LITELLM_GEMINI_LIVE_DEFER_SETUP", "false").lower() == "true"
use_legacy_interactions_schema: bool = (
    os.getenv("LITELLM_USE_LEGACY_INTERACTIONS_SCHEMA", "false").lower() == "true"
)  # When True, sends Api-Revision: 2026-05-07 to Google so responses use the legacy `outputs`
# schema instead of the new `steps` schema. Remove this flag after June 8, 2026.
retry = True
### AUTH ###
api_key: Optional[str] = None
openai_key: Optional[str] = None
groq_key: Optional[str] = None
gigachat_key: Optional[str] = None
xai_key: Optional[str] = None
databricks_key: Optional[str] = None
openai_like_key: Optional[str] = None
azure_key: Optional[str] = None
anthropic_key: Optional[str] = None
replicate_key: Optional[str] = None
bytez_key: Optional[str] = None
gdc_key: Optional[str] = None
gdc_api_base: Optional[str] = None
cohere_key: Optional[str] = None
infinity_key: Optional[str] = None
clarifai_key: Optional[str] = None
maritalk_key: Optional[str] = None
ai21_key: Optional[str] = None
ollama_key: Optional[str] = None
openrouter_key: Optional[str] = None
datarobot_key: Optional[str] = None
predibase_key: Optional[str] = None
huggingface_key: Optional[str] = None
vertex_project: Optional[str] = None
vertex_location: Optional[str] = None
predibase_tenant_id: Optional[str] = None
togetherai_api_key: Optional[str] = None
cloudflare_api_key: Optional[str] = None
vercel_ai_gateway_key: Optional[str] = None
baseten_key: Optional[str] = None
llama_api_key: Optional[str] = None
aleph_alpha_key: Optional[str] = None
nlp_cloud_key: Optional[str] = None
novita_api_key: Optional[str] = None
snowflake_key: Optional[str] = None
gradient_ai_api_key: Optional[str] = None
nebius_key: Optional[str] = None
wandb_key: Optional[str] = None
heroku_key: Optional[str] = None
cometapi_key: Optional[str] = None
ovhcloud_key: Optional[str] = None
lemonade_key: Optional[str] = None
sap_service_key: Optional[str] = None
amazon_nova_api_key: Optional[str] = None
inception_key: Optional[str] = None
common_cloud_provider_auth_params: dict = {
    "params": ["project", "region_name", "token"],
    "providers": ["vertex_ai", "bedrock", "watsonx", "azure", "vertex_ai_beta"],
}
use_litellm_proxy: bool = False  # when True, requests will be sent to the specified litellm proxy endpoint
use_client: bool = False
ssl_verify: Union[str, bool] = True
ssl_security_level: Optional[str] = None
ssl_certificate: Optional[str] = None
user_url_validation: bool = True
user_url_allowed_hosts: List[str] = []
provider_url_destination_allowed_hosts: List[str] = []
ssl_ecdh_curve: Optional[str] = None  # Set to 'X25519' to disable PQC and improve performance
disable_streaming_logging: bool = False
disable_token_counter: bool = False
disable_add_transform_inline_image_block: bool = False
disable_add_user_agent_to_request_tags: bool = False
disable_anthropic_gemini_context_caching_transform: bool = False
enable_anthropic_prompt_caching: bool = os.getenv("LITELLM_ENABLE_ANTHROPIC_PROMPT_CACHING", "false").lower() == "true"
_anthropic_prompt_caching_ttl_env: Optional[str] = os.getenv("LITELLM_ANTHROPIC_PROMPT_CACHING_TTL")
anthropic_prompt_caching_ttl: Optional[Literal["5m", "1h"]] = (
    "1h" if _anthropic_prompt_caching_ttl_env == "1h" else "5m" if _anthropic_prompt_caching_ttl_env == "5m" else None
)
disable_vertex_batch_output_transformation: bool = False
extra_spend_tag_headers: Optional[List[str]] = None
in_memory_llm_clients_cache: "LLMClientCache"
safe_memory_mode: bool = False
enable_azure_ad_token_refresh: Optional[bool] = False
# Proxy Authentication - auto-obtain/refresh OAuth2/JWT tokens for LiteLLM Proxy
proxy_auth: Optional[Any] = None
### DEFAULT AZURE API VERSION ###
AZURE_DEFAULT_API_VERSION = "2025-02-01-preview"  # this is updated to the latest
### DEFAULT WATSONX API VERSION ###
WATSONX_DEFAULT_API_VERSION = "2024-03-13"
### COHERE EMBEDDINGS DEFAULT TYPE ###
COHERE_DEFAULT_EMBEDDING_INPUT_TYPE: "COHERE_EMBEDDING_INPUT_TYPES" = "search_document"
### CREDENTIALS ###
credential_list: List["CredentialItem"] = []
### GUARDRAILS ###
llamaguard_model_name: Optional[str] = None
openai_moderations_model_name: Optional[str] = None
presidio_ad_hoc_recognizers: Optional[str] = None
google_moderation_confidence_threshold: Optional[float] = None
llamaguard_unsafe_content_categories: Optional[str] = None
blocked_user_list: Optional[Union[str, List]] = None
banned_keywords_list: Optional[Union[str, List]] = None
llm_guard_mode: Literal["all", "key-specific", "request-specific"] = "all"
guardrail_name_config_map: Dict[str, GuardrailItem] = {}
include_cost_in_streaming_usage: bool = False
reasoning_auto_summary: bool = False
### PROMPTS ####
from litellm.types.prompts.init_prompts import PromptSpec

prompt_name_config_map: Dict[str, PromptSpec] = {}

##################
### PREVIEW FEATURES ###
enable_preview_features: bool = False
return_response_headers: bool = False  # get response headers from LLM Api providers - example x-remaining-requests,
enable_json_schema_validation: bool = False
enable_model_config_credential_overrides: bool = False
enable_key_alias_format_validation: bool = (
    False  # opt-in validation of key_alias format on /key/generate and /key/update
)
enable_gemini_default_thinking_level_low: bool = (
    False  # opt-in: force thinkingLevel low/minimal for Gemini 3 thinking param mapping
)
####################
logging: bool = True
enable_loadbalancing_on_batch_endpoints: Optional[bool] = None
require_managed_files: bool = False  # proxy only - require target_model_names on POST /v1/files
enable_caching_on_provider_specific_optional_params: bool = (
    False  # feature-flag for caching on optional params - e.g. 'top_k'
)
caching: bool = False  # Not used anymore, will be removed in next MAJOR release - https://github.com/BerriAI/litellm/discussions/648
caching_with_models: bool = False  # # Not used anymore, will be removed in next MAJOR release - https://github.com/BerriAI/litellm/discussions/648
cache: Optional["Cache"] = None  # cache object <- use this - https://docs.litellm.ai/docs/caching
default_in_memory_ttl: Optional[float] = None
default_redis_ttl: Optional[float] = None
default_redis_batch_cache_expiry: Optional[float] = None
model_alias_map: Dict[str, str] = {}
model_group_settings: Optional["ModelGroupSettings"] = None
max_budget: float = 0.0  # set the max budget across all providers
budget_duration: Optional[str] = (
    None  # proxy only - resets budget after fixed duration. You can set duration as seconds ("30s"), minutes ("30m"), hours ("30h"), days ("30d").
)
default_soft_budget: float = DEFAULT_SOFT_BUDGET  # by default all litellm proxy keys have a soft budget of 50.0
budget_exceeded_throttle_percentage: Optional[float] = None
forward_traceparent_to_llm_provider: bool = False


_current_cost = 0.0  # private variable, used if max budget is set
error_logs: Dict = {}
add_function_to_prompt: bool = (
    False  # if function calling not supported by api, append function call details to system prompt
)
client_session: Optional[httpx.Client] = None
aclient_session: Optional[httpx.AsyncClient] = None
model_fallbacks: Optional[List] = None  # Deprecated for 'litellm.fallbacks'
model_cost_map_url: str = os.getenv(
    "LITELLM_MODEL_COST_MAP_URL",
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
)
blog_posts_url: str = os.getenv(
    "LITELLM_BLOG_POSTS_URL",
    "https://docs.litellm.ai/blog/rss.xml",
)
anthropic_beta_headers_url: str = os.getenv(
    "LITELLM_ANTHROPIC_BETA_HEADERS_URL",
    "https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/anthropic_beta_headers_config.json",
)
suppress_debug_info: bool = False
dynamodb_table_name: Optional[str] = None
s3_callback_params: Optional[Dict] = None
s3_audit_callback_params: Optional[Dict] = None
datadog_llm_observability_params: Optional[Union[DatadogLLMObsInitParams, Dict]] = None
datadog_params: Optional[Union[DatadogInitParams, Dict]] = None
newrelic_params: Optional[Union[NewRelicInitParams, Dict]] = None
aws_sqs_callback_params: Optional[Dict] = None
generic_logger_headers: Optional[Dict] = None
default_key_generate_params: Optional[Dict] = None
default_key_max_budget_alert_emails: Optional[Dict[str, list]] = None
upperbound_key_generate_params: Optional[LiteLLM_UpperboundKeyGenerateParams] = None
key_generation_settings: Optional["StandardKeyGenerationConfig"] = None
default_internal_user_params: Optional[Dict] = None
default_team_params: Optional[Union[DefaultTeamSSOParams, Dict]] = None
default_team_settings: Optional[List] = None
max_user_budget: Optional[float] = None
default_max_internal_user_budget: Optional[float] = None
max_internal_user_budget: Optional[float] = None
max_ui_session_budget: Optional[float] = (
    1.0  # USD budget for each dashboard login session (playground, test connection)
)
internal_user_budget_duration: Optional[str] = None
tag_budget_config: Optional[Dict[str, "BudgetConfig"]] = None
max_end_user_budget: Optional[float] = None
max_end_user_budget_id: Optional[str] = None
# When True, end-user IDs extracted from requests are validated against
# LiteLLM_EndUserTable / LiteLLM_UserTable. Values that do not resolve to a
# known row are dropped before reaching spend logs. Defaults to False for
# backwards compatibility — arbitrary client-supplied identifiers still
# pass through unchanged.
validate_end_user_id_in_db: bool = False
disable_end_user_cost_tracking: Optional[bool] = None
disable_end_user_cost_tracking_prometheus_only: Optional[bool] = None
enable_end_user_cost_tracking_prometheus_only: Optional[bool] = None
custom_prometheus_metadata_labels: List[str] = []
custom_prometheus_tags: List[str] = []
prometheus_metrics_config: Optional[List] = None
prometheus_emit_stream_label: bool = False
# Opt-in: emit `rate_limit_category` and `rate_limit_type` labels on
# `litellm_proxy_failed_requests_metric`. Off by default to preserve the
# pre-unification label set so existing dashboards / recording rules keyed on
# that metric keep matching after upgrade. Enable when downstream consumers
# are ready to split 429s by source (vendor vs. litellm) and dimension
# (RPM/TPM/concurrent/budget).
prometheus_emit_rate_limit_labels: bool = False
prometheus_user_budget_label_include_email_alias: bool = False
prometheus_end_user_metrics_max_series_per_metric: Optional[int] = 10000
prometheus_end_user_metrics_ttl_seconds: Optional[float] = 3600.0
prometheus_end_user_metrics_cleanup_interval_seconds: Optional[float] = 60.0
disable_add_prefix_to_prompt: bool = False  # used by anthropic, to disable adding prefix to prompt
disable_copilot_system_to_assistant: bool = False  # If false (default), converts all 'system' role messages to 'assistant' for GitHub Copilot compatibility. Set to true to disable this behavior.
public_mcp_servers: Optional[List[str]] = None
public_mcp_hub_strict_whitelist: bool = True
public_model_groups: Optional[List[str]] = None
public_agent_groups: Optional[List[str]] = None
# Supports both old format (Dict[str, str]) and new format (Dict[str, Dict[str, Any]])
# New format: { "displayName": { "url": "...", "index": 0 } }
# Old format: { "displayName": "url" } (for backward compatibility)
public_model_groups_links: Dict[str, Union[str, Dict[str, Any]]] = {}
#### REQUEST PRIORITIZATION #######
priority_reservation: Optional[Dict[str, Union[float, "PriorityReservationDict"]]] = None
# priority_reservation_settings is lazy-loaded via __getattr__
# Only declare for type checking - at runtime __getattr__ handles it
if TYPE_CHECKING:
    priority_reservation_settings: Optional["PriorityReservationSettings"] = None


######## Networking Settings ########
use_aiohttp_transport: bool = True  # Older variable, aiohttp is now the default. use disable_aiohttp_transport instead.
aiohttp_trust_env: bool = False  # set to true to use HTTP_ Proxy settings
disable_aiohttp_transport: bool = False  # Set this to true to use httpx instead
disable_aiohttp_trust_env: bool = False  # When False, aiohttp will respect HTTP(S)_PROXY env vars
force_ipv4: bool = False  # when True, litellm will force ipv4 for all LLM requests. Some users have seen httpx ConnectionError when using ipv6.
network_mock: bool = False  # When True, use mock transport — no real network calls

####### STOP SEQUENCE LIMIT #######
disable_stop_sequence_limit: bool = False  # when True, stop sequence limit is disabled

#### RETRIES ####
num_retries: Optional[int] = None  # per model endpoint
max_fallbacks: Optional[int] = None
default_fallbacks: Optional[List] = None
fallbacks: Optional[List] = None
context_window_fallbacks: Optional[List] = None
content_policy_fallbacks: Optional[List] = None
allowed_fails: int = 3
allow_dynamic_callback_disabling: bool = True
num_retries_per_request: Optional[int] = None  # for the request overall (incl. fallbacks + model retries)
####### SECRET MANAGERS #####################
secret_manager_client: Optional[Any] = (
    None  # list of instantiated key management clients - e.g. azure kv, infisical, etc.
)
_google_kms_resource_name: Optional[str] = None
_key_management_system: Optional["KeyManagementSystem"] = None
# Note: KeyManagementSettings must be eagerly imported because _key_management_settings
# is accessed during import time in secret_managers/main.py
# We'll import it after the lazy import system is set up
# We can't define it here because KeyManagementSettings is lazy-loaded
#### PII MASKING ####
output_parse_pii: bool = False
#############################################
from litellm.litellm_core_utils.get_model_cost_map import get_model_cost_map

model_cost = get_model_cost_map(url=model_cost_map_url)
cost_discount_config: Dict[str, float] = {}  # Provider-specific cost discounts {"vertex_ai": 0.05} = 5% discount
cost_margin_config: Dict[
    str, Union[float, Dict[str, float]]
] = {}  # Provider-specific or global cost margins. Examples:
# Percentage: {"openai": 0.10} = 10% margin
# Fixed: {"openai": {"fixed_amount": 0.001}} = $0.001 per request
# Global: {"global": 0.05} = 5% global margin on all providers
# Combined: {"vertex_ai": {"percentage": 0.08, "fixed_amount": 0.0005}}
custom_prompt_dict: Dict[str, dict] = {}
check_provider_endpoint = False


####### THREAD-SPECIFIC DATA ####################
class MyLocal(threading.local):
    def __init__(self):
        self.user = "Hello World"


_thread_context = MyLocal()


def identify(event_details):
    # Store user in thread local data
    if "user" in event_details:
        _thread_context.user = event_details["user"]


####### ADDITIONAL PARAMS ################### configurable params if you use proxy models like Helicone, map spend to org id, etc.
api_base: Optional[str] = None
headers = None
api_version: Optional[str] = None
organization = None
project = None
config_path = None
vertex_ai_safety_settings: Optional[dict] = None

####### COMPLETION MODELS ###################
from typing import Set

open_ai_chat_completion_models: Set = set()
open_ai_text_completion_models: Set = set()
cohere_models: Set = set()
cohere_chat_models: Set = set()
mistral_chat_models: Set = set()
text_completion_codestral_models: Set = set()
text_completion_inception_models: Set = set()
anthropic_models: Set = set()
openrouter_models: Set = set()
datarobot_models: Set = set()
vertex_language_models: Set = set()
vertex_vision_models: Set = set()
vertex_chat_models: Set = set()
vertex_code_chat_models: Set = set()
vertex_ai_image_models: Set = set()
vertex_ai_video_models: Set = set()
vertex_text_models: Set = set()
vertex_code_text_models: Set = set()
vertex_embedding_models: Set = set()
vertex_anthropic_models: Set = set()
vertex_llama3_models: Set = set()
vertex_deepseek_models: Set = set()
vertex_ai_ai21_models: Set = set()
vertex_mistral_models: Set = set()
vertex_openai_models: Set = set()
vertex_minimax_models: Set = set()
vertex_moonshot_models: Set = set()
vertex_zai_models: Set = set()
ai21_models: Set = set()
ai21_chat_models: Set = set()
nlp_cloud_models: Set = set()
aleph_alpha_models: Set = set()
bedrock_models: Set = set()
bedrock_converse_models: Set = set(BEDROCK_CONVERSE_MODELS)
fal_ai_models: Set = set()
fireworks_ai_models: Set = set()
fireworks_ai_embedding_models: Set = set()
deepinfra_models: Set = set()
perplexity_models: Set = set()
watsonx_models: Set = set()
gemini_models: Set = set()
xai_models: Set = set()
zai_models: Set = set()
deepseek_models: Set = set()
tencent_models: Set = set()
runwayml_models: Set = set()
azure_ai_models: Set = set()
jina_ai_models: Set = set()
voyage_models: Set = set()
infinity_models: Set = set()
heroku_models: Set = set()
databricks_models: Set = set()
cloudflare_models: Set = set()
codestral_models: Set = set()
friendliai_models: Set = set()
featherless_ai_models: Set = set()
palm_models: Set = set()
groq_models: Set = set()
azure_models: Set = set()
azure_anthropic_models: Set = set()
azure_text_models: Set = set()
anyscale_models: Set = set()
cerebras_models: Set = set()
galadriel_models: Set = set()
nvidia_nim_models: Set = set()
nvidia_riva_models: Set = set()
soniox_models: Set = set()
sambanova_models: Set = set()
sambanova_embedding_models: Set = set()
novita_models: Set = set()
assemblyai_models: Set = set()
snowflake_models: Set = set()
gradient_ai_models: Set = set()
llama_models: Set = set()
nscale_models: Set = set()
nebius_models: Set = set()
nebius_embedding_models: Set = set()
aiml_models: Set = set()
deepgram_models: Set = set()
elevenlabs_models: Set = set()
dashscope_models: Set = set()
moonshot_models: Set = set()
publicai_models: Set = set()
darkbloom_models: Set = set()
v0_models: Set = set()
morph_models: Set = set()
lambda_ai_models: Set = set()
inception_models: Set = set()
hyperbolic_models: Set = set()
black_forest_labs_models: Set = set()
recraft_models: Set = set()
cometapi_models: Set = set()
oci_models: Set = set()
vercel_ai_gateway_models: Set = set()
volcengine_models: Set = set()
wandb_models: Set = set(WANDB_MODELS)
ovhcloud_models: Set = set()
ovhcloud_embedding_models: Set = set()
lemonade_models: Set = set()
docker_model_runner_models: Set = set()
amazon_nova_models: Set = set()
stability_models: Set = set()
github_copilot_models: Set = set()
chatgpt_models: Set = set()
minimax_models: Set = set()
aws_polly_models: Set = set()
gigachat_models: Set = set()
llamagate_models: Set = set()
reducto_models: Set = set()
bedrock_mantle_models: Set = set()


def is_bedrock_pricing_only_model(key: str) -> bool:
    """
    Excludes keys with the pattern 'bedrock/<region>/<model>'. These are in the model_prices_and_context_window.json file for pricing purposes only.

    Args:
        key (str): A key to filter.

    Returns:
        bool: True if the key matches the Bedrock pattern, False otherwise.
    """
    # Regex to match 'bedrock/<region>/<model>'
    bedrock_pattern = re.compile(r"^bedrock/[a-zA-Z0-9_-]+/.+$")

    if "month-commitment" in key:
        return True

    is_match = bedrock_pattern.match(key)
    return is_match is not None


def is_openai_finetune_model(key: str) -> bool:
    """
    Excludes model cost keys with the pattern 'ft:<model>'. These are in the model_prices_and_context_window.json file for pricing purposes only.

    Args:
        key (str): A key to filter.

    Returns:
        bool: True if the key matches the OpenAI finetune pattern, False otherwise.
    """
    return key.startswith("ft:") and not key.count(":") > 1


def add_known_models(model_cost_map: Optional[Dict] = None):
    _map = model_cost_map if model_cost_map is not None else model_cost
    for key, value in _map.items():
        if value.get("litellm_provider") == "openai" and not is_openai_finetune_model(key):
            open_ai_chat_completion_models.add(key)
        elif value.get("litellm_provider") == "text-completion-openai":
            open_ai_text_completion_models.add(key)
        elif value.get("litellm_provider") == "azure_text":
            azure_text_models.add(key)
        elif value.get("litellm_provider") == "cohere":
            cohere_models.add(key)
        elif value.get("litellm_provider") == "cohere_chat":
            cohere_chat_models.add(key)
        elif value.get("litellm_provider") == "mistral":
            mistral_chat_models.add(key)
        elif value.get("litellm_provider") == "anthropic":
            anthropic_models.add(key)
        elif value.get("litellm_provider") == "empower":
            empower_models.add(key)
        elif value.get("litellm_provider") == "openrouter":
            openrouter_models.add(key)
        elif value.get("litellm_provider") == "vercel_ai_gateway":
            vercel_ai_gateway_models.add(key)
        elif value.get("litellm_provider") == "datarobot":
            datarobot_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-text-models":
            vertex_text_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-code-text-models":
            vertex_code_text_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-language-models":
            vertex_language_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-vision-models":
            vertex_vision_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-chat-models":
            vertex_chat_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-code-chat-models":
            vertex_code_chat_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-embedding-models":
            vertex_embedding_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-anthropic_models":
            key = key.replace("vertex_ai/", "")
            vertex_anthropic_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-llama_models":
            key = key.replace("vertex_ai/", "")
            vertex_llama3_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-deepseek_models":
            key = key.replace("vertex_ai/", "")
            vertex_deepseek_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-mistral_models":
            key = key.replace("vertex_ai/", "")
            vertex_mistral_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-ai21_models":
            key = key.replace("vertex_ai/", "")
            vertex_ai_ai21_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-image-models":
            key = key.replace("vertex_ai/", "")
            vertex_ai_image_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-video-models":
            key = key.replace("vertex_ai/", "")
            vertex_ai_video_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-openai_models":
            key = key.replace("vertex_ai/", "")
            vertex_openai_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-minimax_models":
            key = key.replace("vertex_ai/", "")
            vertex_minimax_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-moonshot_models":
            key = key.replace("vertex_ai/", "")
            vertex_moonshot_models.add(key)
        elif value.get("litellm_provider") == "vertex_ai-zai_models":
            key = key.replace("vertex_ai/", "")
            vertex_zai_models.add(key)
        elif value.get("litellm_provider") == "ai21":
            if value.get("mode") == "chat":
                ai21_chat_models.add(key)
            else:
                ai21_models.add(key)
        elif value.get("litellm_provider") == "nlp_cloud":
            nlp_cloud_models.add(key)
        elif value.get("litellm_provider") == "aleph_alpha":
            aleph_alpha_models.add(key)
        elif value.get("litellm_provider") == "bedrock" and not is_bedrock_pricing_only_model(key):
            bedrock_models.add(key)
        elif value.get("litellm_provider") == "bedrock_converse":
            bedrock_converse_models.add(key)
        elif value.get("litellm_provider") == "deepinfra":
            deepinfra_models.add(key)
        elif value.get("litellm_provider") == "perplexity":
            perplexity_models.add(key)
        elif value.get("litellm_provider") == "watsonx":
            watsonx_models.add(key)
        elif value.get("litellm_provider") == "gemini":
            gemini_models.add(key)
        elif value.get("litellm_provider") == "fireworks_ai":
            # ignore the 'up-to', '-to-' model names -> not real models. just for cost tracking based on model params.
            if "-to-" not in key and "fireworks-ai-default" not in key:
                fireworks_ai_models.add(key)
        elif value.get("litellm_provider") == "fireworks_ai-embedding-models":
            # ignore the 'up-to', '-to-' model names -> not real models. just for cost tracking based on model params.
            if "-to-" not in key:
                fireworks_ai_embedding_models.add(key)
        elif value.get("litellm_provider") == "text-completion-codestral":
            text_completion_codestral_models.add(key)
        elif value.get("litellm_provider") == "text-completion-inception":
            text_completion_inception_models.add(key)
        elif value.get("litellm_provider") == "xai":
            xai_models.add(key)
        elif value.get("litellm_provider") == "zai":
            zai_models.add(key)
        elif value.get("litellm_provider") == "fal_ai":
            fal_ai_models.add(key)
        elif value.get("litellm_provider") == "deepseek":
            deepseek_models.add(key)
        elif value.get("litellm_provider") == "tencent":
            tencent_models.add(key)
        elif value.get("litellm_provider") == "runwayml":
            runwayml_models.add(key)
        elif value.get("litellm_provider") == "meta_llama":
            llama_models.add(key)
        elif value.get("litellm_provider") == "nscale":
            nscale_models.add(key)
        elif value.get("litellm_provider") == "azure_ai":
            azure_ai_models.add(key)
        elif value.get("litellm_provider") == "voyage":
            voyage_models.add(key)
        elif value.get("litellm_provider") == "infinity":
            infinity_models.add(key)
        elif value.get("litellm_provider") == "databricks":
            databricks_models.add(key)
        elif value.get("litellm_provider") == "cloudflare":
            cloudflare_models.add(key)
        elif value.get("litellm_provider") == "codestral":
            codestral_models.add(key)
        elif value.get("litellm_provider") == "friendliai":
            friendliai_models.add(key)
        elif value.get("litellm_provider") == "palm":
            palm_models.add(key)
        elif value.get("litellm_provider") == "groq":
            groq_models.add(key)
        elif value.get("litellm_provider") == "azure":
            azure_models.add(key)
        elif value.get("litellm_provider") == "azure_anthropic":
            azure_anthropic_models.add(key)
        elif value.get("litellm_provider") == "anyscale":
            anyscale_models.add(key)
        elif value.get("litellm_provider") == "cerebras":
            cerebras_models.add(key)
        elif value.get("litellm_provider") == "galadriel":
            galadriel_models.add(key)
        elif value.get("litellm_provider") == "nvidia_nim":
            nvidia_nim_models.add(key)
        elif value.get("litellm_provider") == "nvidia_riva":
            nvidia_riva_models.add(key)
        elif value.get("litellm_provider") == "soniox":
            soniox_models.add(key)
        elif value.get("litellm_provider") == "sambanova":
            sambanova_models.add(key)
        elif value.get("litellm_provider") == "sambanova-embedding-models":
            sambanova_embedding_models.add(key)
        elif value.get("litellm_provider") == "novita":
            novita_models.add(key)
        elif value.get("litellm_provider") == "nebius-chat-models":
            nebius_models.add(key)
        elif value.get("litellm_provider") == "nebius-embedding-models":
            nebius_embedding_models.add(key)
        elif value.get("litellm_provider") == "aiml":
            aiml_models.add(key)
        elif value.get("litellm_provider") == "assemblyai":
            assemblyai_models.add(key)
        elif value.get("litellm_provider") == "jina_ai":
            jina_ai_models.add(key)
        elif value.get("litellm_provider") == "snowflake":
            snowflake_models.add(key)
        elif value.get("litellm_provider") == "gradient_ai":
            gradient_ai_models.add(key)
        elif value.get("litellm_provider") == "featherless_ai":
            featherless_ai_models.add(key)
        elif value.get("litellm_provider") == "deepgram":
            deepgram_models.add(key)
        elif value.get("litellm_provider") == "elevenlabs":
            elevenlabs_models.add(key)
        elif value.get("litellm_provider") == "heroku":
            heroku_models.add(key)
        elif value.get("litellm_provider") == "dashscope":
            dashscope_models.add(key)
        elif value.get("litellm_provider") == "modelscope":
            modelscope_models.add(key)
        elif value.get("litellm_provider") == "moonshot":
            moonshot_models.add(key)
        elif value.get("litellm_provider") == "publicai":
            publicai_models.add(key)
        elif value.get("litellm_provider") == "darkbloom":
            darkbloom_models.add(key)
        elif value.get("litellm_provider") == "v0":
            v0_models.add(key)
        elif value.get("litellm_provider") == "morph":
            morph_models.add(key)
        elif value.get("litellm_provider") == "lambda_ai":
            lambda_ai_models.add(key)
        elif value.get("litellm_provider") == "inception":
            inception_models.add(key)
        elif value.get("litellm_provider") == "hyperbolic":
            hyperbolic_models.add(key)
        elif value.get("litellm_provider") == "black_forest_labs":
            black_forest_labs_models.add(key)
        elif value.get("litellm_provider") == "recraft":
            recraft_models.add(key)
        elif value.get("litellm_provider") == "cometapi":
            cometapi_models.add(key)
        elif value.get("litellm_provider") == "oci":
            oci_models.add(key)
        elif value.get("litellm_provider") == "volcengine":
            volcengine_models.add(key)
        elif value.get("litellm_provider") == "wandb":
            wandb_models.add(key)
        elif value.get("litellm_provider") == "ovhcloud":
            ovhcloud_models.add(key)
        elif value.get("litellm_provider") == "ovhcloud-embedding-models":
            ovhcloud_embedding_models.add(key)
        elif value.get("litellm_provider") == "lemonade":
            lemonade_models.add(key)
        elif value.get("litellm_provider") == "docker_model_runner":
            docker_model_runner_models.add(key)
        elif value.get("litellm_provider") == "amazon_nova":
            amazon_nova_models.add(key)
        elif value.get("litellm_provider") == "stability":
            stability_models.add(key)
        elif value.get("litellm_provider") == "github_copilot":
            github_copilot_models.add(key)
        elif value.get("litellm_provider") == "chatgpt":
            chatgpt_models.add(key)
        elif value.get("litellm_provider") == "minimax":
            minimax_models.add(key)
        elif value.get("litellm_provider") == "aws_polly":
            aws_polly_models.add(key)
        elif value.get("litellm_provider") == "gigachat":
            gigachat_models.add(key)
        elif value.get("litellm_provider") == "llamagate":
            llamagate_models.add(key)
        elif value.get("litellm_provider") == "reducto":
            reducto_models.add(key)
        elif value.get("litellm_provider") == "bedrock_mantle":
            bedrock_mantle_models.add(key)


add_known_models()
# known openai compatible endpoints - we'll eventually move this list to the model_prices_and_context_window.json dictionary

# this is maintained for Exception Mapping


# used for Cost Tracking & Token counting
# https://azure.microsoft.com/en-in/pricing/details/cognitive-services/openai-service/
# Azure returns gpt-35-turbo in their responses, we need to map this to azure/gpt-3.5-turbo for token counting
azure_llms = {
    "gpt-35-turbo": "azure/gpt-35-turbo",
    "gpt-35-turbo-16k": "azure/gpt-35-turbo-16k",
    "gpt-35-turbo-instruct": "azure/gpt-35-turbo-instruct",
    "azure/gpt-41": "gpt-4.1",
    "azure/gpt-41-mini": "gpt-4.1-mini",
    "azure/gpt-41-nano": "gpt-4.1-nano",
}

azure_embedding_models = {
    "ada": "azure/ada",
}

petals_models = [
    "petals-team/StableBeluga2",
]

ollama_models = ["llama2"]

maritalk_models = ["maritalk"]

model_list = list(
    open_ai_chat_completion_models
    | open_ai_text_completion_models
    | cohere_models
    | cohere_chat_models
    | anthropic_models
    | set(replicate_models)
    | openrouter_models
    | datarobot_models
    | set(huggingface_models)
    | vertex_chat_models
    | vertex_text_models
    | ai21_models
    | ai21_chat_models
    | set(together_ai_models)
    | set(baseten_models)
    | aleph_alpha_models
    | nlp_cloud_models
    | set(ollama_models)
    | bedrock_models
    | deepinfra_models
    | perplexity_models
    | set(maritalk_models)
    | runwayml_models
    | vertex_language_models
    | watsonx_models
    | gemini_models
    | text_completion_codestral_models
    | text_completion_inception_models
    | xai_models
    | zai_models
    | fal_ai_models
    | deepseek_models
    | modelscope_models
    | azure_ai_models
    | voyage_models
    | infinity_models
    | databricks_models
    | cloudflare_models
    | codestral_models
    | friendliai_models
    | palm_models
    | groq_models
    | azure_models
    | azure_anthropic_models
    | anyscale_models
    | cerebras_models
    | galadriel_models
    | nvidia_nim_models
    | nvidia_riva_models
    | soniox_models
    | sambanova_models
    | azure_text_models
    | novita_models
    | assemblyai_models
    | jina_ai_models
    | snowflake_models
    | gradient_ai_models
    | llama_models
    | featherless_ai_models
    | nscale_models
    | deepgram_models
    | elevenlabs_models
    | dashscope_models
    | moonshot_models
    | publicai_models
    | darkbloom_models
    | v0_models
    | morph_models
    | lambda_ai_models
    | inception_models
    | black_forest_labs_models
    | recraft_models
    | cometapi_models
    | oci_models
    | heroku_models
    | vercel_ai_gateway_models
    | volcengine_models
    | wandb_models
    | ovhcloud_models
    | lemonade_models
    | docker_model_runner_models
    | reducto_models
    | bedrock_mantle_models
    | set(clarifai_models)
)

model_list_set = set(model_list)

# provider_list is lazy-loaded via __getattr__ to avoid importing LlmProviders at import time


models_by_provider: dict = {
    "openai": open_ai_chat_completion_models | open_ai_text_completion_models,
    "text-completion-openai": open_ai_text_completion_models,
    "cohere": cohere_models | cohere_chat_models,
    "cohere_chat": cohere_chat_models,
    "anthropic": anthropic_models,
    "replicate": replicate_models,
    "huggingface": huggingface_models,
    "together_ai": together_ai_models,
    "baseten": baseten_models,
    "openrouter": openrouter_models,
    "vercel_ai_gateway": vercel_ai_gateway_models,
    "datarobot": datarobot_models,
    "vertex_ai": vertex_chat_models
    | vertex_text_models
    | vertex_anthropic_models
    | vertex_vision_models
    | vertex_language_models
    | vertex_deepseek_models
    | vertex_minimax_models
    | vertex_moonshot_models
    | vertex_zai_models,
    "ai21": ai21_models,
    "bedrock": bedrock_models | bedrock_converse_models,
    "petals": petals_models,
    "ollama": ollama_models,
    "ollama_chat": ollama_models,
    "deepinfra": deepinfra_models,
    "perplexity": perplexity_models,
    "maritalk": maritalk_models,
    "watsonx": watsonx_models,
    "gemini": gemini_models,
    "fireworks_ai": fireworks_ai_models | fireworks_ai_embedding_models,
    "aleph_alpha": aleph_alpha_models,
    "text-completion-codestral": text_completion_codestral_models,
    "text-completion-inception": text_completion_inception_models,
    "xai": xai_models,
    "zai": zai_models,
    "fal_ai": fal_ai_models,
    "deepseek": deepseek_models,
    "tencent": tencent_models,
    "runwayml": runwayml_models,
    "mistral": mistral_chat_models,
    "azure_ai": azure_ai_models,
    "voyage": voyage_models,
    "infinity": infinity_models,
    "databricks": databricks_models,
    "cloudflare": cloudflare_models,
    "codestral": codestral_models,
    "nlp_cloud": nlp_cloud_models,
    "friendliai": friendliai_models,
    "palm": palm_models,
    "groq": groq_models,
    "azure": azure_models | azure_text_models,
    "azure_anthropic": azure_anthropic_models,
    "azure_text": azure_text_models,
    "anyscale": anyscale_models,
    "cerebras": cerebras_models,
    "galadriel": galadriel_models,
    "nvidia_nim": nvidia_nim_models,
    "nvidia_riva": nvidia_riva_models,
    "soniox": soniox_models,
    "sambanova": sambanova_models | sambanova_embedding_models,
    "novita": novita_models,
    "nebius": nebius_models | nebius_embedding_models,
    "aiml": aiml_models,
    "assemblyai": assemblyai_models,
    "jina_ai": jina_ai_models,
    "snowflake": snowflake_models,
    "gradient_ai": gradient_ai_models,
    "meta_llama": llama_models,
    "nscale": nscale_models,
    "featherless_ai": featherless_ai_models,
    "deepgram": deepgram_models,
    "elevenlabs": elevenlabs_models,
    "heroku": heroku_models,
    "dashscope": dashscope_models,
    "modelscope": modelscope_models,
    "moonshot": moonshot_models,
    "publicai": publicai_models,
    "darkbloom": darkbloom_models,
    "v0": v0_models,
    "morph": morph_models,
    "lambda_ai": lambda_ai_models,
    "inception": inception_models,
    "hyperbolic": hyperbolic_models,
    "black_forest_labs": black_forest_labs_models,
    "recraft": recraft_models,
    "cometapi": cometapi_models,
    "oci": oci_models,
    "volcengine": volcengine_models,
    "wandb": wandb_models,
    "ovhcloud": ovhcloud_models | ovhcloud_embedding_models,
    "lemonade": lemonade_models,
    "clarifai": clarifai_models,
    "amazon_nova": amazon_nova_models,
    "stability": stability_models,
    "github_copilot": github_copilot_models,
    "chatgpt": chatgpt_models,
    "minimax": minimax_models,
    "aws_polly": aws_polly_models,
    "gigachat": gigachat_models,
    "llamagate": llamagate_models,
    "reducto": reducto_models,
    "bedrock_mantle": bedrock_mantle_models,
}

# mapping for those models which have larger equivalents
longer_context_model_fallback_dict: dict = {
    # openai chat completion models
    "gpt-3.5-turbo": "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-0301": "gpt-3.5-turbo-16k-0301",
    "gpt-3.5-turbo-0613": "gpt-3.5-turbo-16k-0613",
    "gpt-4": "gpt-4-32k",
    "gpt-4-0314": "gpt-4-32k-0314",
    "gpt-4-0613": "gpt-4-32k-0613",
    # anthropic
    "claude-instant-1": "claude-2",
    "claude-instant-1.2": "claude-2",
    # vertexai
    "chat-bison": "chat-bison-32k",
    "chat-bison@001": "chat-bison-32k",
    "codechat-bison": "codechat-bison-32k",
    "codechat-bison@001": "codechat-bison-32k",
    # openrouter
    "openrouter/openai/gpt-3.5-turbo": "openrouter/openai/gpt-3.5-turbo-16k",
    "openrouter/anthropic/claude-instant-v1": "openrouter/anthropic/claude-2",
}

####### EMBEDDING MODELS ###################

all_embedding_models = (
    open_ai_embedding_models
    | set(cohere_embedding_models)
    | set(bedrock_embedding_models)
    | vertex_embedding_models
    | fireworks_ai_embedding_models
    | nebius_embedding_models
    | sambanova_embedding_models
    | ovhcloud_embedding_models
)

####### IMAGE GENERATION MODELS ###################
openai_image_generation_models = ["dall-e-2", "dall-e-3"]

####### VIDEO GENERATION MODELS ###################
openai_video_generation_models = ["sora-2"]

# timeout is lazy-loaded via __getattr__
# get_llm_provider is lazy-loaded via __getattr__
# remove_index_from_tool_calls is lazy-loaded via __getattr__

# Import KeyManagementSettings here (before utils import) because _key_management_settings
# is accessed during import time in secret_managers/main.py (via dd_tracing -> datadog -> _service_logger -> utils)
from litellm.types.secret_managers.main import KeyManagementSettings

_key_management_settings: KeyManagementSettings = KeyManagementSettings()

# client must be imported immediately as it's used as a decorator at function definition time
from .utils import client
from litellm.secret_managers.main import get_secret, get_secret_str

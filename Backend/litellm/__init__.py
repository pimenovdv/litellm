### Hide pydantic namespace conflict warnings globally ###
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", message=".*conflict with protected namespace.*")
# Suppress Pydantic 2.11+ deprecation warning about accessing model_fields on instances
# This warning can accumulate during streaming and cause memory leaks
warnings.filterwarnings("ignore", message=".*Accessing the.*attribute on the instance is deprecated.*")
### INIT VARIABLES #########################
import os
import threading

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

import re
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
    get_args,
    overload,
)

import httpx

from litellm._logging import (
    _turn_on_debug,
    _turn_on_json,
    json_logs,
    log_level,
    set_verbose,
    verbose_logger,
)
from litellm.constants import (
    BEDROCK_CONVERSE_MODELS,
    BEDROCK_EMBEDDING_PROVIDERS_LITERAL,
    BEDROCK_INVOKE_PROVIDERS_LITERAL,
    DEFAULT_ALLOWED_FAILS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_FLUSH_INTERVAL_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_REPLICATE_POLLING_DELAY_SECONDS,
    DEFAULT_REPLICATE_POLLING_RETRIES,
    DEFAULT_SOFT_BUDGET,
    HUMANLOOP_PROMPT_CACHE_TTL_SECONDS,
    LITELLM_CHAT_PROVIDERS,
    OPENAI_CHAT_COMPLETION_PARAMS,
    OPENAI_FINISH_REASONS,
    REPEATED_STREAMING_CHUNK_LIMIT,
    ROUTER_MAX_FALLBACKS,
    WANDB_MODELS,
    _openai_like_providers,
    baseten_models,
    bedrock_embedding_models,
    clarifai_models,
    cohere_embedding_models,
    empower_models,
    huggingface_models,
    known_tokenizer_config,
    modelscope_models,
    open_ai_embedding_models,
    openai_compatible_endpoints,
    openai_compatible_providers,
    openai_text_completion_compatible_providers,
    replicate_models,
    request_timeout,
    together_ai_models,
)
from litellm.constants import (
    OPENAI_CHAT_COMPLETION_PARAMS as _openai_completion_params,  # backwards compatibility
)
from litellm.constants import (
    OPENAI_FINISH_REASONS as _openai_finish_reasons,  # backwards compatibility
)
from litellm.constants import (
    request_timeout_explicitly_set as request_timeout_explicitly_set,
)
from litellm.types.integrations.newrelic import NewRelicInitParams

# register_async_client_cleanup is lazy-loaded and called on first access

litellm_mode = os.getenv("LITELLM_MODE", "DEV")  # "PRODUCTION", "DEV"


####################################################
if set_verbose:
    _turn_on_debug()
####################################################
### Callbacks /Logging / Success / Failure Handlers #####
CALLBACK_TYPES = Union[str, Callable, "CustomLogger"]  # CustomLogger is lazy-loaded
input_callback: list[CALLBACK_TYPES] = []
success_callback: list[CALLBACK_TYPES] = []
failure_callback: list[CALLBACK_TYPES] = []
service_callback: list[CALLBACK_TYPES] = []
audit_log_callbacks: list[CALLBACK_TYPES] = []
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
cold_storage_custom_logger: _custom_logger_compatible_callbacks_literal | None = None
logged_real_time_event_types: list[str] | Literal["*"] | None = None
_known_custom_logger_compatible_callbacks: list = list(get_args(_custom_logger_compatible_callbacks_literal))
callbacks: list[
    Callable | _custom_logger_compatible_callbacks_literal | CustomLogger  # CustomLogger is lazy-loaded
] = []
callback_settings: dict[str, dict[str, Any]] = {}
initialized_langfuse_clients: int = 0
langfuse_default_tags: list[str] | None = None
langsmith_batch_size: int | None = None
prometheus_initialize_budget_metrics: bool | None = False
prometheus_latency_buckets: list[float] | None = None
require_auth_for_metrics_endpoint: bool | None = True
argilla_batch_size: int | None = None
datadog_use_v1: bool | None = False  # if you want to use v1 datadog logged payload.
gcs_pub_sub_use_v1: bool | None = False  # if you want to use v1 gcs pubsub logged payload
generic_api_use_v1: bool | None = False  # if you want to use v1 generic api logged payload
argilla_transformation_object: dict[str, Any] | None = None
_async_input_callback: list[str | Callable | CustomLogger] = (  # CustomLogger is lazy-loaded
    []
)  # internal variable - async custom callbacks are routed here.
_async_success_callback: list[str | Callable | CustomLogger] = (  # CustomLogger is lazy-loaded
    []
)  # internal variable - async custom callbacks are routed here.
_async_failure_callback: list[str | Callable | CustomLogger] = (  # CustomLogger is lazy-loaded
    []
)  # internal variable - async custom callbacks are routed here.
pre_call_rules: list[Callable] = []
post_call_rules: list[Callable] = []
turn_off_message_logging: bool | None = False
standard_logging_payload_excluded_fields: list[str] | None = (
    None  # Fields to exclude from StandardLoggingPayload before callbacks receive it
)
log_raw_request_response: bool = False
redact_messages_in_exceptions: bool | None = False
redact_user_api_key_info: bool | None = False
# When True (default — preserves historical behavior), the Router appends
# internal config names (model_group, fallback model groups, deployment
# timeouts, fallback failure details) onto exception messages and surfaces
# them to clients via ProxyException.message. Set to False if you do NOT
# want the proxy's internal model_name / fallback wiring visible to clients.
# Deprecation: planned to flip to False (redact by default) in a future
# major release; opt in early with `litellm.expose_router_debug_in_errors
# = False`.
expose_router_debug_in_errors: bool = True
filter_invalid_headers: bool | None = False
add_user_information_to_llm_headers: bool | None = (
    None  # adds user_id, team_id, token hash (params from StandardLoggingMetadata) to request headers
)
overwrite_user_with_key_hash: bool = (
    False  # force the outgoing `user` param to the hashed api key, so providers see a stable, tamper-proof id
)
store_audit_logs = False  # Enterprise feature, allow users to see audit logs
skip_system_message_in_guardrail: bool = False
skip_tool_message_in_guardrail: bool = False
### end of callbacks #############

email: str | None = (
    None  # Not used anymore, will be removed in next MAJOR release - https://github.com/BerriAI/litellm/discussions/648
)
token: str | None = (
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
api_key: str | None = None
openai_key: str | None = None
groq_key: str | None = None
gigachat_key: str | None = None
xai_key: str | None = None
databricks_key: str | None = None
openai_like_key: str | None = None
azure_key: str | None = None
anthropic_key: str | None = None
replicate_key: str | None = None
bytez_key: str | None = None
gdc_key: str | None = None
gdc_api_base: str | None = None
cohere_key: str | None = None
infinity_key: str | None = None
clarifai_key: str | None = None
maritalk_key: str | None = None
ai21_key: str | None = None
ollama_key: str | None = None
openrouter_key: str | None = None
datarobot_key: str | None = None
predibase_key: str | None = None
huggingface_key: str | None = None
vertex_project: str | None = None
vertex_location: str | None = None
predibase_tenant_id: str | None = None
togetherai_api_key: str | None = None
cloudflare_api_key: str | None = None
vercel_ai_gateway_key: str | None = None
baseten_key: str | None = None
llama_api_key: str | None = None
aleph_alpha_key: str | None = None
nlp_cloud_key: str | None = None
novita_api_key: str | None = None
snowflake_key: str | None = None
gradient_ai_api_key: str | None = None
nebius_key: str | None = None
wandb_key: str | None = None
heroku_key: str | None = None
cometapi_key: str | None = None
ovhcloud_key: str | None = None
lemonade_key: str | None = None
sap_service_key: str | None = None
amazon_nova_api_key: str | None = None
inception_key: str | None = None
common_cloud_provider_auth_params: dict = {
    "params": ["project", "region_name", "token"],
    "providers": ["vertex_ai", "bedrock", "watsonx", "azure", "vertex_ai_beta"],
}
use_litellm_proxy: bool = False  # when True, requests will be sent to the specified litellm proxy endpoint
use_client: bool = False
ssl_verify: str | bool = True
ssl_security_level: str | None = None
ssl_certificate: str | None = None
user_url_validation: bool = True
user_url_allowed_hosts: list[str] = []
provider_url_destination_allowed_hosts: list[str] = []
ssl_ecdh_curve: str | None = None  # Set to 'X25519' to disable PQC and improve performance
disable_streaming_logging: bool = False
disable_token_counter: bool = False
disable_add_transform_inline_image_block: bool = False
disable_add_user_agent_to_request_tags: bool = False
disable_anthropic_gemini_context_caching_transform: bool = False
enable_anthropic_prompt_caching: bool = os.getenv("LITELLM_ENABLE_ANTHROPIC_PROMPT_CACHING", "false").lower() == "true"
_anthropic_prompt_caching_ttl_env: str | None = os.getenv("LITELLM_ANTHROPIC_PROMPT_CACHING_TTL")
anthropic_prompt_caching_ttl: Literal["5m", "1h"] | None = (
    "1h" if _anthropic_prompt_caching_ttl_env == "1h" else "5m" if _anthropic_prompt_caching_ttl_env == "5m" else None
)
disable_vertex_batch_output_transformation: bool = False
extra_spend_tag_headers: list[str] | None = None
in_memory_llm_clients_cache: LLMClientCache
safe_memory_mode: bool = False
enable_azure_ad_token_refresh: bool | None = False
# Proxy Authentication - auto-obtain/refresh OAuth2/JWT tokens for LiteLLM Proxy
proxy_auth: Any | None = None
### DEFAULT AZURE API VERSION ###
AZURE_DEFAULT_API_VERSION = "2025-02-01-preview"  # this is updated to the latest
### DEFAULT WATSONX API VERSION ###
WATSONX_DEFAULT_API_VERSION = "2024-03-13"
### COHERE EMBEDDINGS DEFAULT TYPE ###
COHERE_DEFAULT_EMBEDDING_INPUT_TYPE: COHERE_EMBEDDING_INPUT_TYPES = "search_document"
### CREDENTIALS ###
credential_list: list[CredentialItem] = []
### GUARDRAILS ###
llamaguard_model_name: str | None = None
openai_moderations_model_name: str | None = None
presidio_ad_hoc_recognizers: str | None = None
google_moderation_confidence_threshold: float | None = None
llamaguard_unsafe_content_categories: str | None = None
blocked_user_list: str | list | None = None
banned_keywords_list: str | list | None = None
llm_guard_mode: Literal["all", "key-specific", "request-specific"] = "all"
guardrail_name_config_map: dict[str, GuardrailItem] = {}
include_cost_in_streaming_usage: bool = False
reasoning_auto_summary: bool = False
### PROMPTS ####
from litellm.types.prompts.init_prompts import PromptSpec

prompt_name_config_map: dict[str, PromptSpec] = {}

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
enable_loadbalancing_on_batch_endpoints: bool | None = None
require_managed_files: bool = False  # proxy only - require target_model_names on POST /v1/files
enable_caching_on_provider_specific_optional_params: bool = (
    False  # feature-flag for caching on optional params - e.g. 'top_k'
)
caching: bool = False  # Not used anymore, will be removed in next MAJOR release - https://github.com/BerriAI/litellm/discussions/648
caching_with_models: bool = False  # # Not used anymore, will be removed in next MAJOR release - https://github.com/BerriAI/litellm/discussions/648
cache: Cache | None = None  # cache object <- use this - https://docs.litellm.ai/docs/caching
default_in_memory_ttl: float | None = None
default_redis_ttl: float | None = None
default_redis_batch_cache_expiry: float | None = None
model_alias_map: dict[str, str] = {}
model_group_settings: ModelGroupSettings | None = None
max_budget: float = 0.0  # set the max budget across all providers
budget_duration: str | None = (
    None  # proxy only - resets budget after fixed duration. You can set duration as seconds ("30s"), minutes ("30m"), hours ("30h"), days ("30d").
)
default_soft_budget: float = DEFAULT_SOFT_BUDGET  # by default all litellm proxy keys have a soft budget of 50.0
budget_exceeded_throttle_percentage: float | None = None
forward_traceparent_to_llm_provider: bool = False


_current_cost = 0.0  # private variable, used if max budget is set
error_logs: dict = {}
add_function_to_prompt: bool = (
    False  # if function calling not supported by api, append function call details to system prompt
)
client_session: httpx.Client | None = None
aclient_session: httpx.AsyncClient | None = None
model_fallbacks: list | None = None  # Deprecated for 'litellm.fallbacks'
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
dynamodb_table_name: str | None = None
s3_callback_params: dict | None = None
s3_audit_callback_params: dict | None = None
datadog_llm_observability_params: DatadogLLMObsInitParams | dict | None = None
datadog_params: DatadogInitParams | dict | None = None
newrelic_params: NewRelicInitParams | dict | None = None
aws_sqs_callback_params: dict | None = None
generic_logger_headers: dict | None = None
default_key_generate_params: dict | None = None
default_key_max_budget_alert_emails: dict[str, list] | None = None
upperbound_key_generate_params: LiteLLM_UpperboundKeyGenerateParams | None = None
key_generation_settings: StandardKeyGenerationConfig | None = None
default_internal_user_params: dict | None = None
default_team_params: DefaultTeamSSOParams | dict | None = None
default_team_settings: list | None = None
max_user_budget: float | None = None
default_max_internal_user_budget: float | None = None
max_internal_user_budget: float | None = None
max_ui_session_budget: float | None = (
    1.0  # USD budget for each dashboard login session (playground, test connection)
)
internal_user_budget_duration: str | None = None
tag_budget_config: dict[str, BudgetConfig] | None = None
max_end_user_budget: float | None = None
max_end_user_budget_id: str | None = None
# When True, end-user IDs extracted from requests are validated against
# LiteLLM_EndUserTable / LiteLLM_UserTable. Values that do not resolve to a
# known row are dropped before reaching spend logs. Defaults to False for
# backwards compatibility — arbitrary client-supplied identifiers still
# pass through unchanged.
validate_end_user_id_in_db: bool = False
disable_end_user_cost_tracking: bool | None = None
disable_end_user_cost_tracking_prometheus_only: bool | None = None
enable_end_user_cost_tracking_prometheus_only: bool | None = None
custom_prometheus_metadata_labels: list[str] = []
custom_prometheus_tags: list[str] = []
prometheus_metrics_config: list | None = None
prometheus_emit_stream_label: bool = False
# Opt-in: emit `rate_limit_category` and `rate_limit_type` labels on
# `litellm_proxy_failed_requests_metric`. Off by default to preserve the
# pre-unification label set so existing dashboards / recording rules keyed on
# that metric keep matching after upgrade. Enable when downstream consumers
# are ready to split 429s by source (vendor vs. litellm) and dimension
# (RPM/TPM/concurrent/budget).
prometheus_emit_rate_limit_labels: bool = False
prometheus_user_budget_label_include_email_alias: bool = False
prometheus_end_user_metrics_max_series_per_metric: int | None = 10000
prometheus_end_user_metrics_ttl_seconds: float | None = 3600.0
prometheus_end_user_metrics_cleanup_interval_seconds: float | None = 60.0
disable_add_prefix_to_prompt: bool = False  # used by anthropic, to disable adding prefix to prompt
disable_copilot_system_to_assistant: bool = False  # If false (default), converts all 'system' role messages to 'assistant' for GitHub Copilot compatibility. Set to true to disable this behavior.
public_mcp_servers: list[str] | None = None
public_mcp_hub_strict_whitelist: bool = True
public_model_groups: list[str] | None = None
public_agent_groups: list[str] | None = None
# Supports both old format (Dict[str, str]) and new format (Dict[str, Dict[str, Any]])
# New format: { "displayName": { "url": "...", "index": 0 } }
# Old format: { "displayName": "url" } (for backward compatibility)
public_model_groups_links: dict[str, str | dict[str, Any]] = {}
#### REQUEST PRIORITIZATION #######
priority_reservation: dict[str, float | PriorityReservationDict] | None = None
# priority_reservation_settings is lazy-loaded via __getattr__
# Only declare for type checking - at runtime __getattr__ handles it
if TYPE_CHECKING:
    priority_reservation_settings: PriorityReservationSettings | None = None


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
num_retries: int | None = None  # per model endpoint
max_fallbacks: int | None = None
default_fallbacks: list | None = None
fallbacks: list | None = None
context_window_fallbacks: list | None = None
content_policy_fallbacks: list | None = None
allowed_fails: int = 3
allow_dynamic_callback_disabling: bool = True
num_retries_per_request: int | None = None  # for the request overall (incl. fallbacks + model retries)
####### SECRET MANAGERS #####################
secret_manager_client: Any | None = (
    None  # list of instantiated key management clients - e.g. azure kv, infisical, etc.
)
_google_kms_resource_name: str | None = None
_key_management_system: KeyManagementSystem | None = None
# Note: KeyManagementSettings must be eagerly imported because _key_management_settings
# is accessed during import time in secret_managers/main.py
# We'll import it after the lazy import system is set up
# We can't define it here because KeyManagementSettings is lazy-loaded
#### PII MASKING ####
output_parse_pii: bool = False
#############################################
from litellm.litellm_core_utils.get_model_cost_map import get_model_cost_map

model_cost = get_model_cost_map(url=model_cost_map_url)
cost_discount_config: dict[str, float] = {}  # Provider-specific cost discounts {"vertex_ai": 0.05} = 5% discount
cost_margin_config: dict[
    str, float | dict[str, float]
] = {}  # Provider-specific or global cost margins. Examples:
# Percentage: {"openai": 0.10} = 10% margin
# Fixed: {"openai": {"fixed_amount": 0.001}} = $0.001 per request
# Global: {"global": 0.05} = 5% global margin on all providers
# Combined: {"vertex_ai": {"percentage": 0.08, "fixed_amount": 0.0005}}
custom_prompt_dict: dict[str, dict] = {}
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
api_base: str | None = None
headers = None
api_version: str | None = None
organization = None
project = None
config_path = None
vertex_ai_safety_settings: dict | None = None

####### COMPLETION MODELS ###################
from typing import Set

open_ai_chat_completion_models: set = set()
open_ai_text_completion_models: set = set()
cohere_models: set = set()
cohere_chat_models: set = set()
mistral_chat_models: set = set()
text_completion_codestral_models: set = set()
text_completion_inception_models: set = set()
anthropic_models: set = set()
openrouter_models: set = set()
datarobot_models: set = set()
vertex_language_models: set = set()
vertex_vision_models: set = set()
vertex_chat_models: set = set()
vertex_code_chat_models: set = set()
vertex_ai_image_models: set = set()
vertex_ai_video_models: set = set()
vertex_text_models: set = set()
vertex_code_text_models: set = set()
vertex_embedding_models: set = set()
vertex_anthropic_models: set = set()
vertex_llama3_models: set = set()
vertex_deepseek_models: set = set()
vertex_ai_ai21_models: set = set()
vertex_mistral_models: set = set()
vertex_openai_models: set = set()
vertex_minimax_models: set = set()
vertex_moonshot_models: set = set()
vertex_zai_models: set = set()
ai21_models: set = set()
ai21_chat_models: set = set()
nlp_cloud_models: set = set()
aleph_alpha_models: set = set()
bedrock_models: set = set()
bedrock_converse_models: set = set(BEDROCK_CONVERSE_MODELS)
fal_ai_models: set = set()
fireworks_ai_models: set = set()
fireworks_ai_embedding_models: set = set()
deepinfra_models: set = set()
perplexity_models: set = set()
watsonx_models: set = set()
gemini_models: set = set()
xai_models: set = set()
zai_models: set = set()
deepseek_models: set = set()
tencent_models: set = set()
runwayml_models: set = set()
azure_ai_models: set = set()
jina_ai_models: set = set()
voyage_models: set = set()
infinity_models: set = set()
heroku_models: set = set()
databricks_models: set = set()
cloudflare_models: set = set()
codestral_models: set = set()
friendliai_models: set = set()
featherless_ai_models: set = set()
palm_models: set = set()
groq_models: set = set()
azure_models: set = set()
azure_anthropic_models: set = set()
azure_text_models: set = set()
anyscale_models: set = set()
cerebras_models: set = set()
galadriel_models: set = set()
nvidia_nim_models: set = set()
nvidia_riva_models: set = set()
soniox_models: set = set()
sambanova_models: set = set()
sambanova_embedding_models: set = set()
novita_models: set = set()
assemblyai_models: set = set()
snowflake_models: set = set()
gradient_ai_models: set = set()
llama_models: set = set()
nscale_models: set = set()
nebius_models: set = set()
nebius_embedding_models: set = set()
aiml_models: set = set()
deepgram_models: set = set()
elevenlabs_models: set = set()
dashscope_models: set = set()
moonshot_models: set = set()
publicai_models: set = set()
darkbloom_models: set = set()
v0_models: set = set()
morph_models: set = set()
lambda_ai_models: set = set()
inception_models: set = set()
hyperbolic_models: set = set()
black_forest_labs_models: set = set()
recraft_models: set = set()
cometapi_models: set = set()
oci_models: set = set()
vercel_ai_gateway_models: set = set()
volcengine_models: set = set()
wandb_models: set = set(WANDB_MODELS)
ovhcloud_models: set = set()
ovhcloud_embedding_models: set = set()
lemonade_models: set = set()
docker_model_runner_models: set = set()
amazon_nova_models: set = set()
stability_models: set = set()
github_copilot_models: set = set()
chatgpt_models: set = set()
minimax_models: set = set()
aws_polly_models: set = set()
gigachat_models: set = set()
llamagate_models: set = set()
reducto_models: set = set()
bedrock_mantle_models: set = set()


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


def add_known_models(model_cost_map: dict | None = None):
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
from litellm.secret_managers.main import get_secret, get_secret_str

from .utils import client

# Cleaned up RAG routes and endpoints

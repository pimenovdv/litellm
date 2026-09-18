import contextvars
import hashlib
import os
import secrets
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    Type,
    Union,
    get_args,
)

from litellm._logging import verbose_logger
from litellm.litellm_core_utils.core_helpers import (
    get_metadata_variable_name_from_kwargs,
    get_or_create_metadata_bucket,
    redact_nested_match_and_regex_keys,
)
from litellm.caching import DualCache
from litellm.integrations.custom_logger import CustomLogger
from litellm.secret_managers.main import str_to_bool
from litellm.types.guardrails import (
    DynamicGuardrailParams,
    GuardrailEventHooks,
    LitellmParams,
    Mode,
)
from litellm.types.llms.openai import AllMessageValues
from litellm.types.proxy.guardrails.guardrail_hooks.base import GuardrailConfigModel
from litellm.types.utils import (
    CallTypes,
    GenericGuardrailAPIInputs,
    GuardrailStatus,
    GuardrailTracingDetail,
    LLMResponseTypes,
    StandardLoggingGuardrailInformation,
)

try:
    from fastapi.exceptions import HTTPException
except ImportError:
    HTTPException = None  # type: ignore

if TYPE_CHECKING:
    from litellm.litellm_core_utils.litellm_logging import Logging as LiteLLMLoggingObj
dc = DualCache()


from litellm.constants import (
    GUARDRAIL_SCANNED_MESSAGES_CACHE_TTL_SECONDS,
    PRE_CALL_EXECUTED_GUARDRAILS_KEY,
)
from litellm.exceptions import (
    BlockedPiiEntityError,
    GuardrailRaisedException,
    ModifyResponseException,
    SensitiveDataRouteException,
)

# Per-process secret tagging each recorded marker. The deployment hook only
# honors markers carrying this token, so a caller cannot forge the metadata
# field to suppress a guardrail on the direct-SDK path that never reaches the
# proxy's metadata sanitizer.
_PRE_CALL_EXECUTED_TOKEN = secrets.token_hex(16)

_guardrail_self_recorded: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "litellm_guardrail_self_recorded", default=False
)


def _strict_guardrail_modes_enabled() -> bool:
    """Whether guardrail-mode validation raises (default) or logs a warning.

    Set `LITELLM_STRICT_GUARDRAIL_MODES=false` to keep the pre-LIT-4226 behavior
    for guardrails whose supported_event_hooks list newly includes their
    configured mode: log the mismatch and continue instead of raising at boot.
    """
    raw = os.environ.get("LITELLM_STRICT_GUARDRAIL_MODES")
    if raw is None:
        return True
    parsed = str_to_bool(raw)
    return True if parsed is None else parsed


def get_session_id_from_request_data(request_data: Dict[str, Any]) -> Optional[str]:
    """Extract session_id from request data (litellm_session_id or metadata)."""
    session_id = request_data.get("litellm_session_id")
    if session_id:
        return str(session_id)

    metadata = request_data.get("metadata") or {}
    session_id = metadata.get("session_id")
    if session_id:
        return str(session_id)

    litellm_metadata = request_data.get("litellm_metadata") or {}
    session_id = litellm_metadata.get("session_id")
    if session_id:
        return str(session_id)

    return None



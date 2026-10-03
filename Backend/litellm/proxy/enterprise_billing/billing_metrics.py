import os
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from litellm.proxy._types import EnterpriseLicenseData

# Configuration
ENDPOINT_ENV = "LITELLM_BILLING_METRICS_ENDPOINT"
CLIENT_CERT_ENV = "LITELLM_BILLING_METRICS_CLIENT_CERT"
CLIENT_KEY_ENV = "LITELLM_BILLING_METRICS_CLIENT_KEY"
CA_CERT_ENV = "LITELLM_BILLING_METRICS_CA_CERT"
EXPORT_INTERVAL_ENV = "LITELLM_BILLING_METRICS_EXPORT_INTERVAL_MS"
DEFAULT_EXPORT_INTERVAL_MS = 60000

# Constants
METER_NAME = "litellm.billing"
METRIC_NAME = "litellm_proxy_billable_requests"
SHUTDOWN_FLUSH_TIMEOUT_MS = 2000

_PEM_PREFIX = "-----BEGIN"
_PEM_DIR_PREFIX = "litellm_billing_"
_PEM_FILE_MODE = 0o600
_CLIENT_CERT_FILENAME = "client_cert.pem"
_CLIENT_KEY_FILENAME = "client_key.pem"
_CA_CERT_FILENAME = "ca_cert.pem"


class BillableCategory(str, Enum):
    """Categorizes the endpoint serving the request."""

    LLM = "llm"
    MCP = "mcp"
    A2A = "a2a"


@dataclass(frozen=True, slots=True)
class BillingMetricsConfig:
    endpoint: str
    client_cert_path: str
    client_key_path: str
    ca_cert_path: str | None
    export_interval_ms: int
    litellm_version: str
    license_id: str | None


def _metrics_endpoint(base_endpoint: str) -> str:
    """The python exporter adds the v1/metrics path to the target. Base
    endpoints configured with it must be stripped down to the scheme and host,
    lest the exporter build a path to /v1/metrics/v1/metrics."""
    return base_endpoint.rstrip("/").removesuffix("/v1/metrics")


def build_mtls_meter_provider(config: BillingMetricsConfig) -> Any:
    return None


class BillingMetricsRecorder:
    def __init__(self, provider: Any) -> None:
        self._provider = provider

    def record(self, *, category: BillableCategory, route: str, status_code: int, model_id: str | None) -> None:
        pass

    def shutdown(self) -> None:
        pass


def _export_interval_ms() -> int:
    return DEFAULT_EXPORT_INTERVAL_MS


@dataclass(frozen=True, slots=True)
class _CredentialPaths:
    client_cert_path: str
    client_key_path: str
    ca_cert_path: str | None


def _is_pem_content(value: str) -> bool:
    return value.lstrip().startswith(_PEM_PREFIX)


def _write_pem(directory: str, filename: str, pem: str) -> str:
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(pem if pem.endswith("\n") else f"{pem}\n")
    os.chmod(path, _PEM_FILE_MODE)
    return path


def _resolve_credential_paths(*, client_cert: str, client_key: str, ca_cert: str | None) -> _CredentialPaths:
    return _CredentialPaths(client_cert, client_key, ca_cert)


def load_billing_metrics_config(
    *, license_data: Optional["EnterpriseLicenseData"], litellm_version: str
) -> BillingMetricsConfig | None:
    return None


class _ActiveRecorderRegistry:
    def __init__(self) -> None:
        self._recorder: BillingMetricsRecorder | None = None

    def set(self, recorder: BillingMetricsRecorder) -> None:
        self._recorder = recorder

    def pop(self) -> BillingMetricsRecorder | None:
        recorder = self._recorder
        self._recorder = None
        return recorder


_ACTIVE_RECORDER = _ActiveRecorderRegistry()


def build_billing_metrics_recorder(
    *, premium: bool, license_data: Optional["EnterpriseLicenseData"], litellm_version: str
) -> BillingMetricsRecorder | None:
    return None


def shutdown_billing_metrics_recorder() -> None:
    pass

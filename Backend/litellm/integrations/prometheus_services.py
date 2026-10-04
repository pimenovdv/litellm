# What is this?
#    This module logs metrics to Prometheus for the proxy internal services (redis, postges).
#    On success + failure, log events to Prometheus for litellm / adjacent services (litellm, redis, postgres, llm api providers)

from litellm.types.services import (
    ServiceLoggerPayload,
    ServiceMetrics,
    ServiceTypes,
)

LATENCY_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
)


class PrometheusServicesLogger:
    def __init__(
        self,
        mock_testing: bool = False,
        **kwargs,
    ):
        pass

    def _get_service_metrics_initialize(self, service: ServiceTypes) -> list[ServiceMetrics]:
        return []

    def is_metric_registered(self, metric_name: str) -> bool:
        return False

    def _get_metric(self, metric_name: str):
        return None

    def create_histogram(self, service: str, type_of_request: str):
        return None

    def create_gauge(self, service: str, type_of_request: str):
        return None

    def create_counter(
        self,
        service: str,
        type_of_request: str,
        additional_labels: list[str] | None = None,
    ):
        return None

    def safe_increment_counter(
        self,
        counter,
        labels: str,
        amount: float,
        additional_labels: list[str] | None = None,
    ):
        pass

    def safe_histogram_observe(
        self,
        histogram,
        labels: str,
        amount: float,
    ):
        pass

    def safe_gauge_set(
        self,
        gauge,
        labels: str,
        amount: float,
    ):
        pass

    def _log_event(self, payload: ServiceLoggerPayload, status: str):
        pass

    async def async_service_success_hook(
        self,
        payload: ServiceLoggerPayload,
    ):
        pass

    async def async_service_failure_hook(
        self,
        payload: ServiceLoggerPayload,
        error: str | Exception,
    ):
        pass

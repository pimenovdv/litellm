from litellm.types.services import (
    ServiceLoggerPayload,
    ServiceMetrics,
    ServiceTypes,
)


class PrometheusServicesLogger:
    litellm_service_latency = None

    def __init__(self, mock_testing: bool = False, **kwargs):
        self.payload_to_prometheus_map: dict = {}
        self.prometheus_to_amount_map: dict = {}
        self.mock_testing = mock_testing
        self.mock_testing_success_calls = 0
        self.mock_testing_failure_calls = 0

    def _get_service_metrics_initialize(self, service: ServiceTypes) -> list[ServiceMetrics]:
        return []

    def is_metric_registered(self, metric_name) -> bool:
        return False

    def _get_metric(self, metric_name):
        return None

    def create_histogram(self, service: str, type_of_request: str):
        return None

    def create_gauge(self, service: str, type_of_request: str):
        return None

    def create_counter(self, service: str, type_of_request: str, additional_labels: list[str] | None = None):
        return None

    def observe_histogram(self, histogram, labels: str, amount: float):
        pass

    def update_gauge(self, gauge, labels: str, amount: float):
        pass

    def increment_counter(self, counter, labels: str, amount: float, additional_labels: list[str] | None = None):
        pass

    def service_success_hook(self, payload: ServiceLoggerPayload):
        if self.mock_testing:
            self.mock_testing_success_calls += 1

    def service_failure_hook(self, payload: ServiceLoggerPayload):
        if self.mock_testing:
            self.mock_testing_failure_calls += 1

    async def async_service_success_hook(self, payload: ServiceLoggerPayload):
        if self.mock_testing:
            self.mock_testing_success_calls += 1

    async def async_service_failure_hook(self, payload: ServiceLoggerPayload, error: str | Exception):
        if self.mock_testing:
            self.mock_testing_failure_calls += 1

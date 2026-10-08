"""
Registry mapping the callback class string to the class type.

This is used to get the class type from the callback class string.

Example:
    "datadog" -> DataDogLogger
    "prometheus" -> PrometheusLogger
"""

from typing import Union

from litellm import _custom_logger_compatible_callbacks_literal
try:
    from litellm.integrations.agentops import AgentOps
except ImportError:
    pass
try:
    from litellm.integrations.anthropic_cache_control_hook import AnthropicCacheControlHook
except ImportError:
    pass
try:
    from litellm.integrations.argilla import ArgillaLogger
except ImportError:
    pass
try:
    from litellm.integrations.azure_sentinel.azure_sentinel import AzureSentinelLogger
except ImportError:
    pass
try:
    from litellm.integrations.azure_storage.azure_storage import AzureBlobStorageLogger
except ImportError:
    pass
try:
    from litellm.integrations.bitbucket import BitBucketPromptManager
except ImportError:
    pass
try:
    from litellm.integrations.braintrust_logging import BraintrustLogger
except ImportError:
    pass
try:
    from litellm.integrations.cloudzero.cloudzero import CloudZeroLogger
except ImportError:
    pass
try:
    from litellm.integrations.datadog.datadog import DataDogLogger
except ImportError:
    pass
try:
    from litellm.integrations.datadog.datadog_llm_obs import DataDogLLMObsLogger
except ImportError:
    pass
try:
    from litellm.integrations.datadog.datadog_metrics import DatadogMetricsLogger
except ImportError:
    pass
try:
    from litellm.integrations.deepeval import DeepEvalLogger
except ImportError:
    pass
try:
    from litellm.integrations.dotprompt import DotpromptManager
except ImportError:
    pass
try:
    from litellm.integrations.focus.focus_logger import FocusLogger
except ImportError:
    pass
try:
    from litellm.integrations.mavvrik_focus.mavvrik_focus_logger import MavvrikFocusLogger
except ImportError:
    pass
try:
    from litellm.integrations.vantage.vantage_logger import VantageLogger
except ImportError:
    pass
try:
    from litellm.integrations.galileo import GalileoObserve
except ImportError:
    pass
try:
    from litellm.integrations.gcs_bucket.gcs_bucket import GCSBucketLogger
except ImportError:
    pass
try:
    from litellm.integrations.gcs_pubsub.pub_sub import GcsPubSubLogger
except ImportError:
    pass
try:
    from litellm.integrations.gitlab import GitLabPromptManager
except ImportError:
    pass
try:
    from litellm.integrations.humanloop import HumanloopLogger
except ImportError:
    pass
try:
    from litellm.integrations.lago import LagoLogger
except ImportError:
    pass
try:
    from litellm.integrations.langfuse.langfuse_prompt_management import (
    LangfusePromptManagement,
)
except ImportError:
    pass
try:
    from litellm.integrations.langsmith import LangsmithLogger
except ImportError:
    pass
try:
    from litellm.integrations.litellm_agent import LiteLLMAgentModelResolver
except ImportError:
    pass
try:
    from litellm.integrations.literal_ai import LiteralAILogger
except ImportError:
    pass
try:
    from litellm.integrations.mlflow import MlflowLogger
except ImportError:
    pass
try:
    from litellm.integrations.newrelic import NewRelicLogger
except ImportError:
    pass
try:
    from litellm.integrations.openmeter import OpenMeterLogger
except ImportError:
    pass
try:
    from litellm.integrations.opik.opik import OpikLogger
except ImportError:
    pass
try:
    from litellm.integrations.posthog import PostHogLogger
except ImportError:
    pass
try:
    from litellm.integrations.prometheus import PrometheusLogger
except ImportError:
    pass
try:
    from litellm.integrations.s3_v2 import S3Logger
except ImportError:
    pass
try:
    from litellm.integrations.sqs import SQSLogger
except ImportError:
    pass
try:
    from litellm.integrations.vector_store_integrations.vector_store_pre_call_hook import (
    VectorStorePreCallHook,
)
except ImportError:
    pass
from litellm.proxy.hooks.dynamic_rate_limiter import _PROXY_DynamicRateLimitHandler
from litellm.proxy.hooks.dynamic_rate_limiter_v3 import _PROXY_DynamicRateLimitHandlerV3


class DummyLogger: pass
try: LagoLogger
except NameError: LagoLogger = DummyLogger
try: OpenMeterLogger
except NameError: OpenMeterLogger = DummyLogger
try: BraintrustLogger
except NameError: BraintrustLogger = DummyLogger
try: OpenWebUILogger
except NameError: OpenWebUILogger = DummyLogger
try: Supabase
except NameError: Supabase = DummyLogger
try: LangsmithLogger
except NameError: LangsmithLogger = DummyLogger
try: ArizeLogger
except NameError: ArizeLogger = DummyLogger
try: CometLogger
except NameError: CometLogger = DummyLogger
try: PrometheusLogger
except NameError: PrometheusLogger = DummyLogger
try: QdrantLogger
except NameError: QdrantLogger = DummyLogger
try: LangFuseLogger
except NameError: LangFuseLogger = DummyLogger
try: LiteDebugger
except NameError: LiteDebugger = DummyLogger
try: DataDogLogger
except NameError: DataDogLogger = DummyLogger
try: DataDogLLMObs
except NameError: DataDogLLMObs = DummyLogger
try: PagerDutyLogger
except NameError: PagerDutyLogger = DummyLogger
try: AthinaLogger
except NameError: AthinaLogger = DummyLogger
try: LunaryLogger
except NameError: LunaryLogger = DummyLogger
try: SlackAlerting
except NameError: SlackAlerting = DummyLogger
try: TraceloopLogger
except NameError: TraceloopLogger = DummyLogger
try: MlflowLogger
except NameError: MlflowLogger = DummyLogger
try: HeliconeLogger
except NameError: HeliconeLogger = DummyLogger
try: OpenTelemetry
except NameError: OpenTelemetry = DummyLogger
try: AgentOps
except NameError: AgentOps = DummyLogger
try: Log10Logger
except NameError: Log10Logger = DummyLogger
try: S3Logger
except NameError: S3Logger = DummyLogger
try: GCSBucketLogger
except NameError: GCSBucketLogger = DummyLogger
try: DynamoDBLogger
except NameError: DynamoDBLogger = DummyLogger
try: DatasetLogger
except NameError: DatasetLogger = DummyLogger
try: BasetenLogger
except NameError: BasetenLogger = DummyLogger
try: UpstashLogger
except NameError: UpstashLogger = DummyLogger
try: SignozLogger
except NameError: SignozLogger = DummyLogger
try: DifyLogger
except NameError: DifyLogger = DummyLogger
try: GenericAPILogger
except NameError: GenericAPILogger = DummyLogger
try: SQSLogger
except NameError: SQSLogger = DummyLogger
try: ArgillaLogger
except NameError: ArgillaLogger = DummyLogger
try: AiseraLogger
except NameError: AiseraLogger = DummyLogger
try: GreenscaleLogger
except NameError: GreenscaleLogger = DummyLogger
try: DataDogMetricsManager
except NameError: DataDogMetricsManager = DummyLogger
try: VectorStorePreCallHook
except NameError: VectorStorePreCallHook = DummyLogger
try: _PROXY_DynamicRateLimitHandler
except NameError: _PROXY_DynamicRateLimitHandler = DummyLogger
try: _PROXY_DynamicRateLimitHandlerV3
except NameError: _PROXY_DynamicRateLimitHandlerV3 = DummyLogger
try: GalileoObserve
except NameError: GalileoObserve = DummyLogger
try: LiteralAILogger
except NameError: LiteralAILogger = DummyLogger
try: CustomLogger
except NameError: CustomLogger = DummyLogger
try: HoneycombLogger
except NameError: HoneycombLogger = DummyLogger
try: DataDogLLMObsLogger
except NameError: DataDogLLMObsLogger = DummyLogger
try: DatadogMetricsLogger
except NameError: DatadogMetricsLogger = DummyLogger
try: AzureSentinelLogger
except NameError: AzureSentinelLogger = DummyLogger
try: AzureBlobStorageLogger
except NameError: AzureBlobStorageLogger = DummyLogger
try: HumanloopLogger
except NameError: HumanloopLogger = DummyLogger
try: LangfusePromptManagement
except NameError: LangfusePromptManagement = DummyLogger
try: GcsPubSubLogger
except NameError: GcsPubSubLogger = DummyLogger
try: AnthropicCacheControlHook
except NameError: AnthropicCacheControlHook = DummyLogger
try: DeepEvalLogger
except NameError: DeepEvalLogger = DummyLogger
try: DotpromptManager
except NameError: DotpromptManager = DummyLogger
try: BitBucketPromptManager
except NameError: BitBucketPromptManager = DummyLogger
try: RedisQueueLogger
except NameError: RedisQueueLogger = DummyLogger
try: OpikLogger
except NameError: OpikLogger = DummyLogger
try: WandbLogger
except NameError: WandbLogger = DummyLogger
try: LoguruLogger
except NameError: LoguruLogger = DummyLogger
try: GitLabPromptManager
except NameError: GitLabPromptManager = DummyLogger
try: CloudZeroLogger
except NameError: CloudZeroLogger = DummyLogger
try: FocusLogger
except NameError: FocusLogger = DummyLogger
try: MavvrikFocusLogger
except NameError: MavvrikFocusLogger = DummyLogger
try: VantageLogger
except NameError: VantageLogger = DummyLogger
try: PostHogLogger
except NameError: PostHogLogger = DummyLogger
try: NewRelicLogger
except NameError: NewRelicLogger = DummyLogger
class CustomLoggerRegistry:
    """
    Registry mapping the callback class string to the class type.
    """

    CALLBACK_CLASS_STR_TO_CLASS_TYPE = {
        "lago": LagoLogger,
        "openmeter": OpenMeterLogger,
        "braintrust": BraintrustLogger,
        "galileo": GalileoObserve,
        "langsmith": LangsmithLogger,
        "literalai": LiteralAILogger,
        "litellm_agent": LiteLLMAgentModelResolver,
        "prometheus": PrometheusLogger,
        "datadog": DataDogLogger,
        "datadog_llm_observability": DataDogLLMObsLogger,
        "datadog_metrics": DatadogMetricsLogger,
        "gcs_bucket": GCSBucketLogger,
        "opik": OpikLogger,
        "argilla": ArgillaLogger,
        "azure_sentinel": AzureSentinelLogger,
        "azure_storage": AzureBlobStorageLogger,
        "humanloop": HumanloopLogger,
        # OTEL compatible loggers
        "logfire": OpenTelemetry,
        "arize": OpenTelemetry,
        "langfuse_otel": OpenTelemetry,
        "arize_phoenix": OpenTelemetry,
        "langtrace": OpenTelemetry,
        "weave_otel": OpenTelemetry,
        "levo": OpenTelemetry,
        "mlflow": MlflowLogger,
        "langfuse": LangfusePromptManagement,
        "otel": OpenTelemetry,
        "gcs_pubsub": GcsPubSubLogger,
        "anthropic_cache_control_hook": AnthropicCacheControlHook,
        "agentops": AgentOps,
        "deepeval": DeepEvalLogger,
        "s3_v2": S3Logger,
        "aws_sqs": SQSLogger,
        "dynamic_rate_limiter": _PROXY_DynamicRateLimitHandler,
        "dynamic_rate_limiter_v3": _PROXY_DynamicRateLimitHandlerV3,
        "vector_store_pre_call_hook": VectorStorePreCallHook,
        "dotprompt": DotpromptManager,
        "bitbucket": BitBucketPromptManager,
        "gitlab": GitLabPromptManager,
        "cloudzero": CloudZeroLogger,
        "focus": FocusLogger,
        "mavvrik": MavvrikFocusLogger,
        "vantage": VantageLogger,
        "posthog": PostHogLogger,
        "newrelic": NewRelicLogger,
    }

    try:
        from litellm_enterprise.enterprise_callbacks.pagerduty.pagerduty import (
            PagerDutyAlerting,
        )
        from litellm_enterprise.enterprise_callbacks.send_emails.resend_email import (
            ResendEmailLogger,
        )
        from litellm_enterprise.enterprise_callbacks.send_emails.sendgrid_email import (
            SendGridEmailLogger,
        )
        from litellm_enterprise.enterprise_callbacks.send_emails.smtp_email import (
            SMTPEmailLogger,
        )

        from litellm.integrations.generic_api.generic_api_callback import (
            GenericAPILogger,
        )

        enterprise_loggers = {
            "pagerduty": PagerDutyAlerting,
            "generic_api": GenericAPILogger,
            "resend_email": ResendEmailLogger,
            "sendgrid_email": SendGridEmailLogger,
            "smtp_email": SMTPEmailLogger,
        }
        CALLBACK_CLASS_STR_TO_CLASS_TYPE.update(enterprise_loggers)
    except ImportError:
        pass  # enterprise not installed

    @classmethod
    def get_callback_str_from_class_type(cls, class_type: type) -> Union[str, None]:
        """
        Get the callback string from the class type.

        Args:
            class_type: The class type to find the string for

        Returns:
            str: The callback string, or None if not found
        """
        for (
            callback_str,
            callback_class,
        ) in cls.CALLBACK_CLASS_STR_TO_CLASS_TYPE.items():
            if callback_class == class_type:
                return callback_str
        return None

    @classmethod
    def get_all_callback_strs_from_class_type(cls, class_type: type) -> list[str]:
        """
        Get all callback strings that map to the same class type.
        Some class types (like OpenTelemetry) have multiple string mappings.

        Args:
            class_type: The class type to find all strings for

        Returns:
            list: List of callback strings that map to the class type
        """
        callback_strs: list[str] = []
        for (
            callback_str,
            callback_class,
        ) in cls.CALLBACK_CLASS_STR_TO_CLASS_TYPE.items():
            if callback_class == class_type:
                callback_strs.append(callback_str)
        return callback_strs

    @classmethod
    def get_class_type_for_custom_logger_name(
        cls,
        custom_logger_name: _custom_logger_compatible_callbacks_literal,
    ) -> type:
        """
        Get the class type for a given custom logger name
        """
        return cls.CALLBACK_CLASS_STR_TO_CLASS_TYPE[custom_logger_name]

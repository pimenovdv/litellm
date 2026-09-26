"""
Registry mapping the callback class string to the class type.

This is used to get the class type from the callback class string.

Example:
    "datadog" -> DataDogLogger
    "prometheus" -> PrometheusLogger
"""

from typing import Union

from litellm import _custom_logger_compatible_callbacks_literal
from litellm.proxy.hooks.dynamic_rate_limiter import _PROXY_DynamicRateLimitHandler
from litellm.proxy.hooks.dynamic_rate_limiter_v3 import _PROXY_DynamicRateLimitHandlerV3


class CustomLoggerRegistry:
    """
    Registry mapping the callback class string to the class type.
    """

    CALLBACK_CLASS_STR_TO_CLASS_TYPE = {
        "lago":  type(None),
        "openmeter":  type(None),
        "braintrust":  type(None),
        "galileo":  type(None),
        "langsmith":  type(None),
        "literalai":  type(None),
        "litellm_agent":  type(None),
        "prometheus":  type(None),
        "datadog":  type(None),
        "datadog_llm_observability":  type(None),
        "datadog_metrics":  type(None),
        "gcs_bucket":  type(None),
        "opik":  type(None),
        "argilla":  type(None),
        "azure_sentinel":  type(None),
        "azure_storage":  type(None),
        "humanloop":  type(None),
        # OTEL compatible loggers
        "logfire":  type(None),
        "arize":  type(None),
        "langfuse_otel":  type(None),
        "arize_phoenix":  type(None),
        "langtrace":  type(None),
        "weave_otel":  type(None),
        "levo":  type(None),
        "mlflow":  type(None),
        "langfuse":  type(None),
        "otel":  type(None),
        "gcs_pubsub":  type(None),
        "anthropic_cache_control_hook":  type(None),
        "agentops":  type(None),
        "deepeval":  type(None),
        "s3_v2":  type(None),
        "aws_sqs":  type(None),
        "dynamic_rate_limiter":  type(None),
        "dynamic_rate_limiter_v3":  type(None),
        "vector_store_pre_call_hook":  type(None),
        "dotprompt":  type(None),
        "bitbucket":  type(None),
        "gitlab":  type(None),
        "cloudzero":  type(None),
        "focus":  type(None),
        "mavvrik":  type(None),
        "vantage":  type(None),
        "posthog":  type(None),
        "newrelic":  type(None),
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


        enterprise_loggers = {
            "pagerduty":  type(None),
            "generic_api":  type(None),
            "resend_email":  type(None),
            "sendgrid_email":  type(None),
            "smtp_email":  type(None),
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

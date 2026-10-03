
from litellm.proxy._types import UserAPIKeyAuth


class DDSpanTagger:
    @staticmethod
    def tag_call_id(litellm_call_id: str | None) -> None:
        pass

    @staticmethod
    def tag_request(
        user_api_key_dict: UserAPIKeyAuth,
        requested_model: str | None,
    ) -> None:
        pass

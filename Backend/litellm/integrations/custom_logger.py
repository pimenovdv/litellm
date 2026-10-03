from typing import Optional, List

class Span: pass

class CustomLogger:
    def __init__(self, *a, **k): pass

    @classmethod
    def get_callback_env_vars(cls, callback_name: Optional[str]) -> List[str]:
        if callback_name == "langfuse":
            return ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]
        return []

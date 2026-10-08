"""
Handles Tracing on DataDog Traces.
"""

from contextlib import contextmanager
from typing import Any


class NullSpan:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def finish(self):
        pass


@contextmanager
def null_tracer(name, **kwargs):
    yield NullSpan()


class NullTracer:
    def trace(self, name, **kwargs):
        return NullSpan()

    def wrap(self, name=None, **kwargs):
        if callable(name):
            return name

        def decorator(f):
            return f

        return decorator


tracer = NullTracer()


def get_active_span() -> Any | None:
    return None


def set_active_span_tag(tag_key: str, tag_value: str) -> bool:
    return False

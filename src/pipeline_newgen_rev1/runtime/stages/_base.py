"""Base contract for pipeline stages.

A Stage is a factory station: it receives the RuntimeContext (the conveyor),
mutates the fields it is responsible for, and returns nothing. Stages do not
know about each other. Ordering lives in `STAGE_PIPELINE_ORDER` inside
`runtime/stages/__init__.py`.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..context import RuntimeContext


@runtime_checkable
class Stage(Protocol):
    feature_key: str

    def run(self, ctx: RuntimeContext) -> None: ...


def stage_is_enabled(ctx: RuntimeContext, feature_key: str) -> bool:
    return feature_key in ctx.enabled_features

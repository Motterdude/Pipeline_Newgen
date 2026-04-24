"""Stage: run the preflight inventory/confirmation when requested.

Gating note: this stage respects `ctx.use_preflight` (the explicit runtime
kwarg) rather than the default feature flag. That preserves the legacy
behavior where the CLI/GUI decides whether the preflight shows up; the
feature-flag default is merely advisory until the stage is fully re-wired.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...ui.runtime_preflight import choose_runtime_preflight
from ..context import RuntimeContext


@dataclass(frozen=True)
class ShowRuntimePreflightStage:
    feature_key: str = "show_runtime_preflight"

    def run(self, ctx: RuntimeContext) -> None:
        if not ctx.use_preflight:
            return
        assert ctx.input_dir is not None and ctx.selection is not None
        ctx.selection = choose_runtime_preflight(
            process_dir=ctx.input_dir,
            initial_selection=ctx.selection,
        )

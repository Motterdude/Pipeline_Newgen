"""Stage: load the text/excel configuration bundle onto the context."""
from __future__ import annotations

from dataclasses import dataclass

from ...config import load_pipeline29_config_bundle
from ..context import RuntimeContext


@dataclass(frozen=True)
class LoadTextConfigStage:
    feature_key: str = "load_text_config"

    def run(self, ctx: RuntimeContext) -> None:
        ctx.bundle = load_pipeline29_config_bundle(
            project_root=ctx.project_root,
            config_source=ctx.config_source,
            text_config_dir=ctx.text_config_dir,
            excel_path=ctx.excel_path,
        )

"""Stage: audit layer de incerteza sobre `ctx.final_table`.

Roda **depois** de `build_final_table` (bridge) e **antes** de `export_excel`
para que o xlsx saia já com as colunas auditáveis.

Não depende do galpão antigo — só lê `ctx.final_table` e `ctx.bundle.instruments`.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..context import RuntimeContext
from ..uncertainty_audit import enrich_final_table_with_audit


@dataclass(frozen=True)
class EnrichFinalTableAuditStage:
    feature_key: str = "enrich_final_table_audit"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.final_table is None:
            print("[INFO] enrich_final_table_audit | final_table is None; skipping.")
            return
        if ctx.bundle is None:
            print("[INFO] enrich_final_table_audit | bundle is None; skipping.")
            return

        before_cols = len(ctx.final_table.columns)
        ctx.final_table = enrich_final_table_with_audit(
            ctx.final_table,
            instruments=ctx.bundle.instruments,
        )
        after_cols = len(ctx.final_table.columns)
        added = after_cols - before_cols
        print(f"[OK] enrich_final_table_audit | added {added} audit column(s) to final_table ({before_cols} -> {after_cols}).")

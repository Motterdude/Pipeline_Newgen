"""Stage: scan_campaign_structure — detect experimental structure from inputs."""
from __future__ import annotations

from dataclasses import dataclass

from ..campaign_scan import scan_campaign_structure, summarize_campaign_catalog
from ..context import RuntimeContext


@dataclass(frozen=True)
class ScanCampaignStructureStage:
    feature_key: str = "scan_campaign_structure"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.discovery is None:
            print("[INFO] scan_campaign_structure | no discovery data; skipping.")
            return

        catalog = scan_campaign_structure(ctx.discovery)
        ctx.campaign_catalog = catalog

        summary = summarize_campaign_catalog(catalog)
        print(
            f"[OK] scan_campaign_structure | mode={catalog.iteration_mode} "
            f"fuels={len(catalog.fuel_labels)} loads={len(catalog.load_points)} "
            f"dirs={len(catalog.directions)} campaigns={len(catalog.campaigns)} "
            f"files={catalog.total_files}"
        )

"""Runtime preflight helpers for the migrated load/sweep workflow.

Heavy submodules (.scan, .service) are lazy-loaded via __getattr__ to avoid
a circular import: adapters.input_discovery → this package's constants →
__init__ → .service → .scan → adapters.input_discovery.
"""

from .models import (
    OpenConversionStatus,
    RuntimeInputInventory,
    RuntimePreflightSnapshot,
    RuntimeSelection,
)

_LAZY_SERVICE = frozenset({
    "PreflightCancelledError",
    "build_runtime_preflight_snapshot",
    "choose_runtime_preflight",
    "summarize_runtime_preflight_snapshot",
})

_LAZY_SCAN = frozenset({
    "available_sweep_keys_from_paths",
    "parse_filename_sweep",
    "planned_pipeline_csv_path",
    "scan_open_conversion_status",
    "scan_runtime_input_inventory",
})

__all__ = [
    "OpenConversionStatus",
    "PreflightCancelledError",
    "RuntimeInputInventory",
    "RuntimePreflightSnapshot",
    "RuntimeSelection",
    "available_sweep_keys_from_paths",
    "build_runtime_preflight_snapshot",
    "choose_runtime_preflight",
    "parse_filename_sweep",
    "planned_pipeline_csv_path",
    "scan_open_conversion_status",
    "scan_runtime_input_inventory",
    "summarize_runtime_preflight_snapshot",
]


def __getattr__(name: str):
    if name in _LAZY_SERVICE:
        from . import service as _svc
        return getattr(_svc, name)
    if name in _LAZY_SCAN:
        from . import scan as _scan
        return getattr(_scan, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


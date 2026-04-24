"""Frozen copies of the legacy monoliths the new pipeline is migrating.

This package is transitional. The files here are verbatim copies of
`nanum-pipeline-28-main/nanum_pipeline_29.py`, `nanum_pipeline_30.py`,
`kibox_open_to_csv.py`, and `pipeline29_config_backend.py`. Bridges in
`pipeline_newgen_rev1.bridges.legacy_runtime` import them lazily to
terceirize stations that have not been ported yet.

Two properties are load-bearing:

1. **sys.path injection**: the legacy files use bare imports between
   siblings (e.g. `from pipeline29_config_backend import ...`). When any
   bridge first imports one of them, we prepend this directory to
   `sys.path` so those imports resolve here rather than at the original
   legacy repo. This keeps the newgen package self-contained.

2. **Transience**: when the last station that uses these files is ported,
   the whole package is deleted along with `bridges/legacy_runtime.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path


_HERE = Path(__file__).resolve().parent


def ensure_on_path() -> None:
    path_str = str(_HERE)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


# Eager: any import of the package wires sys.path. Bridges can then
# `from .. import legacy_monoliths; import nanum_pipeline_29` without
# further bookkeeping.
ensure_on_path()

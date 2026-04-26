from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..ui.runtime_preflight.constants import DEFAULT_SWEEP_KEY, SWEEP_FILENAME_PATTERNS
from ..ui.runtime_preflight.normalize import normalize_sweep_key, sweep_axis_label


@dataclass(frozen=True)
class InputFileMeta:
    path: Path
    basename: str
    source_type: str
    load_kw: Optional[float]
    dies_pct: Optional[float]
    biod_pct: Optional[float]
    etoh_pct: Optional[float]
    h2o_pct: Optional[float]
    sweep_key: Optional[str] = None
    sweep_value: Optional[float] = None
    sweep_label: str = ""
    load_parse: str = ""
    composition_parse: str = ""
    sweep_parse: str = ""


@dataclass(frozen=True)
class DiscoveredRuntimeInputs:
    process_dir: Path
    files: List[InputFileMeta]


def _to_pct_or_none(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(str(value).replace(",", "."))
    except Exception:
        return None
    if not isfinite(parsed):
        return None
    return parsed


def parse_filename_sweep(stem: str) -> Tuple[Optional[str], Optional[float], str]:
    text = str(stem or "").strip()
    if not text:
        return None, None, "missing_filename"
    for sweep_key, pattern in SWEEP_FILENAME_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is None:
            continue
        sweep_value = _to_pct_or_none(match.group(1))
        if sweep_value is None:
            continue
        canonical = normalize_sweep_key(sweep_key)
        return canonical, sweep_value, f"filename_{canonical}"
    return None, None, "missing_filename"


def parse_filename_composition(stem: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], str]:
    text = str(stem or "").strip()
    if not text:
        return None, None, None, None, "missing_filename"

    ethanol_hydrated = re.search(r"E(\d+)\s*H(\d+)", text, flags=re.IGNORECASE)
    if ethanol_hydrated:
        return None, None, _to_pct_or_none(ethanol_hydrated.group(1)), _to_pct_or_none(ethanol_hydrated.group(2)), "filename_ethanol"

    dies_pct = None
    biod_pct = None
    etoh_pct = None

    diesel_biodiesel = re.search(r"(?:^|[^A-Za-z0-9])D(\d+(?:[.,]\d+)?)\s*B(\d+(?:[.,]\d+)?)(?:$|[^A-Za-z0-9])", text, flags=re.IGNORECASE)
    if diesel_biodiesel:
        dies_pct = _to_pct_or_none(diesel_biodiesel.group(1))
        biod_pct = _to_pct_or_none(diesel_biodiesel.group(2))
        return dies_pct, biod_pct, None, None, "filename_diesel"

    biodiesel_diesel = re.search(r"(?:^|[^A-Za-z0-9])B(\d+(?:[.,]\d+)?)\s*D(\d+(?:[.,]\d+)?)(?:$|[^A-Za-z0-9])", text, flags=re.IGNORECASE)
    if biodiesel_diesel:
        biod_pct = _to_pct_or_none(biodiesel_diesel.group(1))
        dies_pct = _to_pct_or_none(biodiesel_diesel.group(2))
        return dies_pct, biod_pct, None, None, "filename_diesel_reversed"

    biodiesel_ethanol = re.search(r"(?:^|[^A-Za-z0-9])B(\d+(?:[.,]\d+)?)\s*E(\d+(?:[.,]\d+)?)(?:$|[^A-Za-z0-9])", text, flags=re.IGNORECASE)
    if biodiesel_ethanol:
        biod_pct = _to_pct_or_none(biodiesel_ethanol.group(1))
        etoh_pct = _to_pct_or_none(biodiesel_ethanol.group(2))
        return 0.0, biod_pct, etoh_pct, 0.0, "filename_biodiesel_ethanol"

    ethanol_biodiesel = re.search(r"(?:^|[^A-Za-z0-9])E(\d+(?:[.,]\d+)?)\s*B(\d+(?:[.,]\d+)?)(?:$|[^A-Za-z0-9])", text, flags=re.IGNORECASE)
    if ethanol_biodiesel:
        etoh_pct = _to_pct_or_none(ethanol_biodiesel.group(1))
        biod_pct = _to_pct_or_none(ethanol_biodiesel.group(2))
        return 0.0, biod_pct, etoh_pct, 0.0, "filename_ethanol_biodiesel"

    diesel_ethanol = re.search(r"(?:^|[^A-Za-z0-9])D(\d+(?:[.,]\d+)?)\s*E(\d+(?:[.,]\d+)?)(?:$|[^A-Za-z0-9])", text, flags=re.IGNORECASE)
    if diesel_ethanol:
        dies_pct = _to_pct_or_none(diesel_ethanol.group(1))
        etoh_pct = _to_pct_or_none(diesel_ethanol.group(2))
        return dies_pct, 0.0, etoh_pct, 0.0, "filename_diesel_ethanol"

    ethanol_diesel = re.search(r"(?:^|[^A-Za-z0-9])E(\d+(?:[.,]\d+)?)\s*D(\d+(?:[.,]\d+)?)(?:$|[^A-Za-z0-9])", text, flags=re.IGNORECASE)
    if ethanol_diesel:
        etoh_pct = _to_pct_or_none(ethanol_diesel.group(1))
        dies_pct = _to_pct_or_none(ethanol_diesel.group(2))
        return dies_pct, 0.0, etoh_pct, 0.0, "filename_ethanol_diesel"

    pure_biodiesel = re.match(r"^B(\d+(?:[.,]\d+)?)(?:$|[^A-Za-z0-9])", text, flags=re.IGNORECASE)
    if pure_biodiesel:
        biod_pct = _to_pct_or_none(pure_biodiesel.group(1))
        if biod_pct is not None:
            return 0.0, biod_pct, 0.0, 0.0, "filename_biodiesel"

    pure_diesel = re.match(r"^D(\d+(?:[.,]\d+)?)(?:$|[^A-Za-z0-9])", text, flags=re.IGNORECASE)
    if pure_diesel:
        dies_pct = _to_pct_or_none(pure_diesel.group(1))
        if dies_pct is not None:
            return dies_pct, 0.0, 0.0, 0.0, "filename_diesel_only"

    diesel_hint = re.search(r"(?:dies_pct|diesel|dies)\s*[-_ ]*(\d+(?:[.,]\d+)?)", text, flags=re.IGNORECASE)
    if diesel_hint:
        dies_pct = _to_pct_or_none(diesel_hint.group(1))

    biod_hint = re.search(r"(?:biod_pct|biodiesel|biod)\s*[-_ ]*(\d+(?:[.,]\d+)?)", text, flags=re.IGNORECASE)
    if biod_hint:
        biod_pct = _to_pct_or_none(biod_hint.group(1))

    if dies_pct is None and biod_pct is not None and 0.0 <= biod_pct <= 100.0:
        dies_pct = 100.0 - biod_pct
        return dies_pct, biod_pct, None, None, "filename_diesel_inferred"

    if biod_pct is None and dies_pct is not None and 0.0 <= dies_pct <= 100.0:
        biod_pct = 100.0 - dies_pct
        return dies_pct, biod_pct, None, None, "filename_diesel_inferred"

    return None, None, None, None, "missing_filename"


def classify_source_type(path: Path) -> str:
    stem_lower = path.stem.lower()
    if stem_lower.endswith("_i"):
        return "KIBOX"
    if stem_lower.endswith("_m"):
        return "MOTEC"
    return "LABVIEW"


def parse_filename_load(stem: str) -> Tuple[Optional[float], str]:
    text = str(stem or "").strip()
    if not text:
        return None, "missing_filename"

    load_tokens = re.findall(r"(\d+(?:[.,]\d+)?)\s*[-_ ]?\s*kw", text, flags=re.IGNORECASE)
    if not load_tokens:
        bare_num = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*", text)
        if bare_num:
            load_tokens = [bare_num.group(1)]

    load_candidates: List[float] = []
    for token in load_tokens:
        value = float(str(token).replace(",", "."))
        if value not in load_candidates:
            load_candidates.append(value)

    if len(load_candidates) == 1:
        return load_candidates[0], "filename"
    if len(load_candidates) > 1:
        return None, "ambiguous_filename"
    return None, "missing_filename"


def _default_basename(path: Path) -> str:
    return "__".join((path.parent.name, path.stem))


def build_input_basename(path: Path, *, roots: Sequence[Path] = ()) -> str:
    for root in roots:
        try:
            rel = path.relative_to(root)
            return "__".join(rel.with_suffix("").parts)
        except Exception:
            continue
    return _default_basename(path)


def discover_input_file(path: Path, *, roots: Sequence[Path] = ()) -> InputFileMeta:
    source_path = Path(path).expanduser().resolve()
    load_kw, load_parse = parse_filename_load(source_path.stem)
    dies_pct, biod_pct, etoh_pct, h2o_pct, composition_parse = parse_filename_composition(source_path.stem)
    sweep_key, sweep_value, sweep_parse = parse_filename_sweep(source_path.stem)
    return InputFileMeta(
        path=source_path,
        basename=build_input_basename(source_path, roots=roots),
        source_type=classify_source_type(source_path),
        load_kw=load_kw,
        dies_pct=dies_pct,
        biod_pct=biod_pct,
        etoh_pct=etoh_pct,
        h2o_pct=h2o_pct,
        sweep_key=sweep_key,
        sweep_value=sweep_value,
        sweep_label=sweep_axis_label(sweep_key) if sweep_key else "",
        load_parse=load_parse,
        composition_parse=composition_parse,
        sweep_parse=sweep_parse,
    )


_DISCOVERY_EXTENSIONS = frozenset({".xlsx", ".csv", ".open"})


def discover_runtime_inputs(process_dir: Path) -> DiscoveredRuntimeInputs:
    root = Path(process_dir).expanduser().resolve()
    paths = [
        p for p in root.rglob("*")
        if p.suffix.lower() in _DISCOVERY_EXTENSIONS
        and p.is_file()
        and not p.name.startswith("~$")
    ]
    files = [discover_input_file(p, roots=(root,)) for p in paths]
    files.sort(key=lambda item: (str(item.path.parent).lower(), item.path.name.lower()))
    return DiscoveredRuntimeInputs(process_dir=root, files=files)


def summarize_discovered_inputs(discovery: DiscoveredRuntimeInputs) -> Dict[str, object]:
    by_source = {"LABVIEW": 0, "KIBOX": 0, "MOTEC": 0}
    sweep_keys: List[str] = []
    files_with_load = 0
    files_with_composition = 0
    for item in discovery.files:
        by_source[item.source_type] = by_source.get(item.source_type, 0) + 1
        if item.load_kw is not None:
            files_with_load += 1
        if any(value is not None for value in (item.dies_pct, item.biod_pct, item.etoh_pct, item.h2o_pct)):
            files_with_composition += 1
        if item.sweep_key and item.sweep_key not in sweep_keys:
            sweep_keys.append(item.sweep_key)
    if not sweep_keys:
        sweep_keys.append(DEFAULT_SWEEP_KEY)
    return {
        "process_dir": str(discovery.process_dir),
        "total_files": len(discovery.files),
        "by_source": by_source,
        "files_with_load": files_with_load,
        "files_with_composition": files_with_composition,
        "available_sweep_keys": sweep_keys,
        "files": [
            {
                "path": str(item.path),
                "basename": item.basename,
                "source_type": item.source_type,
                "load_kw": item.load_kw,
                "dies_pct": item.dies_pct,
                "biod_pct": item.biod_pct,
                "etoh_pct": item.etoh_pct,
                "h2o_pct": item.h2o_pct,
                "sweep_key": item.sweep_key,
                "sweep_value": item.sweep_value,
                "sweep_label": item.sweep_label,
                "load_parse": item.load_parse,
                "composition_parse": item.composition_parse,
                "sweep_parse": item.sweep_parse,
            }
            for item in discovery.files
        ],
    }

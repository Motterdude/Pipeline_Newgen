"""Run a parity cycle: legacy pipeline_29 end-to-end vs newgen run-load-sweep.

Both pipelines process the same raw folder (legacy repo's raw/subindo_aditivado_1/),
each writing into its own tempdir. Afterwards the two output trees are diffed
for lv_kpis_clean.xlsx (via pandas DataFrame equality) and PNGs under plots/
(via file byte hash + size).

Runs unattended: monkey-patches the legacy interactive plot-point prompts,
isolates the legacy's LOCALAPPDATA-based runtime-paths JSON, and skips the
config-GUI prompt. Never touches operational dirs.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


LEGACY_REPO = Path(r"C:\Temp\np28_git_main_20260422\nanum-pipeline-28-main")
NEWGEN_REPO = Path(r"C:\Temp\np28_git_main_20260422\Pipeline_newgen_rev1")
RAW_SOURCE_DEFAULT = LEGACY_REPO / "raw" / "subindo_aditivado_1"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _list_pngs(root: Path) -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    plots = root / "plots"
    if not plots.exists():
        return out
    for p in sorted(plots.rglob("*.png")):
        rel = str(p.relative_to(plots)).replace("\\", "/")
        out[rel] = (p.stat().st_size, _sha256(p))
    return out


def _prepare_config_copy(src: Path, dest: Path, raw_dir: Path, out_dir: Path) -> None:
    shutil.copytree(src, dest)
    defaults = dest / "defaults.toml"
    text = defaults.read_text(encoding="utf-8")
    new_lines = []
    for line in text.splitlines():
        if line.startswith('"RAW_INPUT_DIR"'):
            new_lines.append(f'"RAW_INPUT_DIR" = "{str(raw_dir).replace(os.sep, os.sep * 2)}"')
        elif line.startswith('"OUT_DIR"'):
            new_lines.append(f'"OUT_DIR" = "{str(out_dir).replace(os.sep, os.sep * 2)}"')
        else:
            new_lines.append(line)
    defaults.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _run_legacy(config_dir: Path, raw_dir: Path, out_dir: Path, appdata: Path, log_path: Path) -> int:
    driver = out_dir.parent / "legacy_driver.py"
    driver_src = textwrap.dedent(f"""
        import sys, os, json
        from pathlib import Path

        sys.path.insert(0, r"{LEGACY_REPO}")
        os.environ["PIPELINE29_USE_DEFAULT_RUNTIME_DIRS"] = "1"
        os.environ["PIPELINE29_SKIP_CONFIG_GUI_PROMPT"] = "1"

        # Seed the runtime-paths JSON so legacy uses these dirs without any popup.
        appdata = Path(r"{appdata}") / "nanum_pipeline_29"
        appdata.mkdir(parents=True, exist_ok=True)
        (appdata / "pipeline29_runtime_paths.json").write_text(
            json.dumps({{
                "raw_input_dir": r"{raw_dir}",
                "out_dir": r"{out_dir}",
            }}),
            encoding="utf-8",
        )

        import nanum_pipeline_29 as legacy

        # Disable interactive plot-point prompts — "None" means "no filter".
        legacy.prompt_plot_point_filter_from_metas = lambda metas: None
        legacy.prompt_plot_point_filter = lambda df: None

        sys.argv = [
            "nanum_pipeline_29.py",
            "--config-source", "text",
            "--config-dir", r"{config_dir}",
            "--skip-config-gui-prompt",
            "--plot-scope", "all",
        ]
        legacy.main()
    """)
    driver.write_text(driver_src, encoding="utf-8")

    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(appdata)
    env["PIPELINE29_USE_DEFAULT_RUNTIME_DIRS"] = "1"
    env["PIPELINE29_SKIP_CONFIG_GUI_PROMPT"] = "1"

    res = subprocess.run(
        [sys.executable, str(driver)],
        env=env,
        cwd=str(LEGACY_REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log_path.write_text(
        f"=== legacy stdout ===\n{res.stdout}\n=== legacy stderr ===\n{res.stderr}\n",
        encoding="utf-8",
    )
    return res.returncode


def _run_newgen(config_dir: Path, raw_dir: Path, out_dir: Path, log_path: Path) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(NEWGEN_REPO / "src")
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "pipeline_newgen_rev1.cli",
            "run-load-sweep",
            "--config-dir",
            str(config_dir),
            "--process-dir",
            str(raw_dir),
            "--out-dir",
            str(out_dir),
            "--json",
        ],
        env=env,
        cwd=str(NEWGEN_REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log_path.write_text(
        f"=== newgen stdout ===\n{res.stdout}\n=== newgen stderr ===\n{res.stderr}\n",
        encoding="utf-8",
    )
    return res.returncode


def _compare_kpis(legacy_out: Path, newgen_out: Path) -> dict:
    legacy_xlsx = legacy_out / "lv_kpis_clean.xlsx"
    newgen_xlsx = newgen_out / "lv_kpis_clean.xlsx"
    report: dict = {
        "legacy_exists": legacy_xlsx.exists(),
        "newgen_exists": newgen_xlsx.exists(),
    }
    if not (legacy_xlsx.exists() and newgen_xlsx.exists()):
        return report
    report["legacy_size"] = legacy_xlsx.stat().st_size
    report["newgen_size"] = newgen_xlsx.stat().st_size
    report["byte_identical"] = _sha256(legacy_xlsx) == _sha256(newgen_xlsx)
    try:
        import pandas as pd
        ldf = pd.read_excel(legacy_xlsx)
        ndf = pd.read_excel(newgen_xlsx)
        report["legacy_shape"] = list(ldf.shape)
        report["newgen_shape"] = list(ndf.shape)
        report["dataframe_equals"] = bool(ldf.equals(ndf))
        if not report["dataframe_equals"] and list(ldf.shape) == list(ndf.shape):
            mism = (ldf != ndf) & ~(ldf.isna() & ndf.isna())
            if mism.values.any():
                col_diffs = mism.sum(axis=0).to_dict()
                report["columns_with_diffs"] = {k: int(v) for k, v in col_diffs.items() if v > 0}
    except Exception as exc:
        report["pandas_error"] = f"{type(exc).__name__}: {exc}"
    return report


def _compare_metricas_incertezas(legacy_out: Path, newgen_out: Path) -> dict:
    subdir = Path("plots") / "compare_iteracoes_bl_vs_adtv"
    legacy_xlsx = legacy_out / subdir / "compare_iteracoes_metricas_incertezas.xlsx"
    newgen_xlsx = newgen_out / subdir / "compare_iteracoes_metricas_incertezas.xlsx"
    report: dict = {
        "legacy_exists": legacy_xlsx.exists(),
        "newgen_exists": newgen_xlsx.exists(),
    }
    if not (legacy_xlsx.exists() and newgen_xlsx.exists()):
        return report
    report["legacy_size"] = legacy_xlsx.stat().st_size
    report["newgen_size"] = newgen_xlsx.stat().st_size
    report["byte_identical"] = _sha256(legacy_xlsx) == _sha256(newgen_xlsx)
    try:
        import pandas as pd
        ldf = pd.read_excel(legacy_xlsx)
        ndf = pd.read_excel(newgen_xlsx)
        report["legacy_shape"] = list(ldf.shape)
        report["newgen_shape"] = list(ndf.shape)
        report["dataframe_equals"] = bool(ldf.equals(ndf))
        if not report["dataframe_equals"] and list(ldf.shape) == list(ndf.shape):
            mism = (ldf != ndf) & ~(ldf.isna() & ndf.isna())
            if mism.values.any():
                col_diffs = mism.sum(axis=0).to_dict()
                report["columns_with_diffs"] = {k: int(v) for k, v in col_diffs.items() if v > 0}
    except Exception as exc:
        report["pandas_error"] = f"{type(exc).__name__}: {exc}"
    return report


def _compare_plots(legacy_out: Path, newgen_out: Path) -> dict:
    l_pngs = _list_pngs(legacy_out)
    n_pngs = _list_pngs(newgen_out)
    missing_in_newgen = sorted(set(l_pngs) - set(n_pngs))
    extra_in_newgen = sorted(set(n_pngs) - set(l_pngs))
    common = sorted(set(l_pngs) & set(n_pngs))
    byte_identical = [name for name in common if l_pngs[name][1] == n_pngs[name][1]]
    byte_different = [
        {
            "name": name,
            "legacy_size": l_pngs[name][0],
            "newgen_size": n_pngs[name][0],
        }
        for name in common
        if l_pngs[name][1] != n_pngs[name][1]
    ]
    return {
        "legacy_count": len(l_pngs),
        "newgen_count": len(n_pngs),
        "byte_identical_count": len(byte_identical),
        "byte_different_count": len(byte_different),
        "missing_in_newgen": missing_in_newgen,
        "extra_in_newgen": extra_in_newgen,
        "byte_different": byte_different,
    }


def main() -> int:
    raw_source = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_SOURCE_DEFAULT

    tmp_root = Path(tempfile.mkdtemp(prefix="compare_cycle_"))
    raw_dir = tmp_root / "raw"
    config_dir = tmp_root / "config"
    appdata = tmp_root / "appdata"
    legacy_out = tmp_root / "legacy_out"
    newgen_out = tmp_root / "newgen_out"

    legacy_out.mkdir(parents=True, exist_ok=True)
    newgen_out.mkdir(parents=True, exist_ok=True)
    appdata.mkdir(parents=True, exist_ok=True)

    print(f"[compare] tempdir: {tmp_root}")
    print(f"[compare] raw source: {raw_source}")
    shutil.copytree(raw_source, raw_dir)
    _prepare_config_copy(NEWGEN_REPO / "config" / "pipeline29_text", config_dir, raw_dir, legacy_out)

    legacy_log = tmp_root / "legacy.log"
    newgen_log = tmp_root / "newgen.log"

    print("[compare] running legacy pipeline_29 end-to-end ...")
    rc_legacy = _run_legacy(config_dir, raw_dir, legacy_out, appdata, legacy_log)
    print(f"[compare] legacy rc = {rc_legacy} | log = {legacy_log}")

    print("[compare] running newgen run-load-sweep ...")
    rc_newgen = _run_newgen(config_dir, raw_dir, newgen_out, newgen_log)
    print(f"[compare] newgen rc = {rc_newgen} | log = {newgen_log}")

    report = {
        "tempdir": str(tmp_root),
        "rc_legacy": rc_legacy,
        "rc_newgen": rc_newgen,
        "kpis": _compare_kpis(legacy_out, newgen_out),
        "plots": _compare_plots(legacy_out, newgen_out),
        "metricas_incertezas": _compare_metricas_incertezas(legacy_out, newgen_out),
    }
    report_path = tmp_root / "compare_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== COMPARE REPORT ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[compare] report: {report_path}")
    print(f"[compare] legacy log: {legacy_log}")
    print(f"[compare] newgen log: {newgen_log}")
    print(f"[compare] tempdir preserved at: {tmp_root}")

    return 0 if (rc_legacy == 0 and rc_newgen == 0) else 1


if __name__ == "__main__":
    sys.exit(main())

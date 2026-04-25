from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List, Optional

from .config import (
    default_runtime_state_path,
    load_pipeline29_config_bundle,
    load_runtime_state,
    summarize_config_bundle,
    summarize_runtime_state,
)
from .runtime import run_load_sweep
from .adapters import (
    aggregate_kibox_mean,
    discover_runtime_inputs,
    export_open_inputs,
    read_kibox_csv,
    read_labview_xlsx,
    read_motec_csv,
    summarize_kibox_aggregate,
    summarize_kibox_read,
    summarize_discovered_inputs,
    summarize_export_results,
    summarize_labview_read,
    summarize_motec_read,
)
from .ui.runtime_preflight import build_runtime_preflight_snapshot, summarize_runtime_preflight_snapshot
from .workflows.load_sweep.orchestrator import build_load_sweep_plan, plan_as_markdown, summarize_plan
from .workflows.load_sweep.state import default_feature_state_path, load_feature_state


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pipeline-newgen")
    sub = parser.add_subparsers(dest="command", required=True)

    show_plan = sub.add_parser("show-plan", help="Show the load/sweep feature plan.")
    show_plan.add_argument("--mode", choices=["load", "sweep"], default="load")
    show_plan.add_argument("--state-path", default="", help="Optional path to a JSON file with feature selections.")
    show_plan.add_argument("--json", action="store_true", help="Print the plan summary as JSON.")

    scan_preflight = sub.add_parser("scan-preflight", help="Scan the runtime input folder using the migrated preflight modules.")
    scan_preflight.add_argument("--process-dir", required=True, help="Directory to scan for xlsx/csv/open inputs.")
    scan_preflight.add_argument("--json", action="store_true", help="Print the scan summary as JSON.")

    discover_inputs = sub.add_parser("discover-inputs", help="Classify runtime input files and parse filename metadata in the migrated adapter.")
    discover_inputs.add_argument("--process-dir", required=True, help="Directory to scan for xlsx/csv/open runtime inputs.")
    discover_inputs.add_argument("--json", action="store_true", help="Print the discovery summary as JSON.")

    inspect_labview = sub.add_parser("inspect-labview", help="Read a LabVIEW workbook through the migrated adapter and print a summary.")
    inspect_labview.add_argument("--input", required=True, help="Path to a LabVIEW .xlsx file.")
    inspect_labview.add_argument("--process-root", default="", help="Optional process root used to build the runtime basename.")
    inspect_labview.add_argument("--json", action="store_true", help="Print the summary as JSON.")

    inspect_motec = sub.add_parser("inspect-motec", help="Read a MoTeC CSV through the migrated adapter and print a summary.")
    inspect_motec.add_argument("--input", required=True, help="Path to a MoTeC _m.csv file.")
    inspect_motec.add_argument("--process-root", default="", help="Optional process root used to build the runtime basename.")
    inspect_motec.add_argument("--json", action="store_true", help="Print the summary as JSON.")

    inspect_kibox = sub.add_parser("inspect-kibox", help="Read a KiBox _i.csv through the migrated adapter and print a summary.")
    inspect_kibox.add_argument("--input", required=True, help="Path to a KiBox _i.csv file.")
    inspect_kibox.add_argument("--process-root", default="", help="Optional process root used to build the runtime basename.")
    inspect_kibox.add_argument("--aggregate", action="store_true", help="Return the aggregated KIBOX_* mean row instead of the raw parsed summary.")
    inspect_kibox.add_argument("--json", action="store_true", help="Print the summary as JSON.")

    launch_gui = sub.add_parser("launch-config-gui", help="Open the migrated legacy pipeline29/30 configuration GUI.")
    launch_gui.add_argument("--base-dir", default="", help="Optional project root. Defaults to the current repository root.")
    launch_gui.add_argument("--config-dir", default="", help="Optional text-config directory.")
    launch_gui.add_argument("--excel-path", default="", help="Optional legacy Excel config workbook path.")

    run_load = sub.add_parser("run-load-sweep", help="Run the migrated load/sweep executor using the saved GUI/runtime state or explicit paths.")
    run_load.add_argument("--base-dir", default="", help="Optional project root. Defaults to the current repository root.")
    run_load.add_argument("--config-source", choices=["auto", "text", "excel"], default="auto")
    run_load.add_argument("--config-dir", default="", help="Optional text-config directory.")
    run_load.add_argument("--excel-path", default="", help="Optional legacy Excel workbook.")
    run_load.add_argument("--state-path", default="", help="Optional runtime-state JSON path.")
    run_load.add_argument("--process-dir", default="", help="Optional input directory override.")
    run_load.add_argument("--out-dir", default="", help="Optional output directory override.")
    run_load.add_argument("--use-preflight", action="store_true", help="Run the migrated preflight before execution.")
    run_load.add_argument("--prompt-runtime-dirs", action="store_true", help="Force the runtime folder chooser before execution.")
    run_load.add_argument("--prompt-plot-filter", action="store_true", help="Force the plot point filter in load mode.")
    run_load.add_argument("--plot-scope", choices=["all", "unitary", "compare", "none"], default="",
                          help="Which plot families to generate. Env var: PIPELINE29_PLOT_SCOPE. Default: all.")
    run_load.add_argument("--compare-iter-pairs", default="",
                          help="JSON array of compare_iteracoes pair overrides. Env var: PIPELINE29_COMPARE_ITER_PAIRS.")
    run_load.add_argument("--aggregation-mode", choices=["load", "sweep"], default="",
                          help="Force load or sweep mode without preflight prompt.")
    run_load.add_argument("--sweep-bin-tol", type=float, default=0.0,
                          help="Override sweep bin tolerance (default: 0.015).")
    run_load.add_argument("--json", action="store_true", help="Print the execution summary as JSON.")

    convert_open = sub.add_parser("convert-open", help="Convert KiBox .open files to CSV using the migrated OpenToCSV adapter.")
    convert_open.add_argument("input", help="A single .open file or a directory containing .open files.")
    convert_open.add_argument("--output-dir", default="", help="Optional output root. When omitted, CSVs stay beside the source .open files.")
    convert_open.add_argument("--converter", default="", help="Optional path to OpenToCSV (.exe, .py, .cmd, or .ps1 for tests/tooling).")
    convert_open.add_argument("--type", dest="export_type", choices=["res", "sig", "tim"], default="res")
    convert_open.add_argument("--separator", choices=["tab", ",", ";"], default="tab")
    convert_open.add_argument("--cycles", default="", help="Optional cycle range passed to the converter.")
    convert_open.add_argument("--no-cycle-number", action="store_true", help="Disable the cycle-number column flag passed to OpenToCSV.")
    convert_open.add_argument("--name-mode", choices=["source", "pipeline", "tool"], default="pipeline")
    convert_open.add_argument("--output-name", default="", help="Optional final CSV name for a single-file conversion.")
    convert_open.add_argument("--json", action="store_true", help="Print a JSON summary instead of plain text lines.")

    inspect_config = sub.add_parser("inspect-config", help="Load the migrated config adapter and print a bundle summary.")
    inspect_config.add_argument("--config-source", choices=["auto", "text", "excel"], default="auto")
    inspect_config.add_argument("--text-config-dir", default="", help="Optional directory for the text config bundle.")
    inspect_config.add_argument("--excel-path", default="", help="Optional path to the legacy config Excel workbook.")
    inspect_config.add_argument("--rebuild-text-config", action="store_true", help="Rebuild the text bundle from Excel when available.")
    inspect_config.add_argument("--json", action="store_true", help="Print the config summary as JSON.")

    show_runtime_state = sub.add_parser("show-runtime-state", help="Show the saved runtime state used for input/output dirs and sweep settings.")
    show_runtime_state.add_argument("--state-path", default="", help="Optional path to a runtime-state JSON file.")
    show_runtime_state.add_argument("--json", action="store_true", help="Print the runtime state summary as JSON.")

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    if args.command == "show-plan":
        root = Path(__file__).resolve().parents[2]
        state_path = Path(args.state_path).expanduser().resolve() if args.state_path else default_feature_state_path(root)
        selection = load_feature_state(state_path, args.mode)
        steps = build_load_sweep_plan(args.mode, selection)
        if args.json:
            print(json.dumps(summarize_plan(steps), indent=2, sort_keys=True))
        else:
            print(plan_as_markdown(steps))
        return 0
    if args.command == "scan-preflight":
        snapshot = build_runtime_preflight_snapshot(Path(args.process_dir))
        summary = summarize_runtime_preflight_snapshot(snapshot)
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "discover-inputs":
        discovery = discover_runtime_inputs(Path(args.process_dir))
        summary = summarize_discovered_inputs(discovery)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "inspect-labview":
        process_root = Path(args.process_root).expanduser().resolve() if args.process_root else None
        try:
            result = read_labview_xlsx(Path(args.input), process_root=process_root)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        summary = summarize_labview_read(result)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "inspect-motec":
        process_root = Path(args.process_root).expanduser().resolve() if args.process_root else None
        try:
            result = read_motec_csv(Path(args.input), process_root=process_root)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        summary = summarize_motec_read(result)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "inspect-kibox":
        process_root = Path(args.process_root).expanduser().resolve() if args.process_root else None
        try:
            if args.aggregate:
                result = aggregate_kibox_mean(Path(args.input), process_root=process_root)
                summary = summarize_kibox_aggregate(result)
            else:
                result = read_kibox_csv(Path(args.input), process_root=process_root)
                summary = summarize_kibox_read(result)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "launch-config-gui":
        from .ui.legacy import launch_config_gui
        from .ui.legacy.pipeline29_config_backend import default_gui_state_path, load_gui_state
        from .ui.legacy.pipeline29_config_gui import PIPELINE29_GUI_SAVE_RUN_EXIT_CODE

        root = Path(args.base_dir).expanduser().resolve() if args.base_dir else Path(__file__).resolve().parents[2]
        config_dir = Path(args.config_dir).expanduser().resolve() if args.config_dir else (root / "config" / "pipeline29_text").resolve()
        excel_path = Path(args.excel_path).expanduser().resolve() if args.excel_path else (root / "config" / "config_incertezas_rev3.xlsx").resolve()
        exit_code = launch_config_gui(base_dir=root, config_dir=config_dir, excel_path=excel_path)
        if exit_code == PIPELINE29_GUI_SAVE_RUN_EXIT_CODE:
            gui_state = load_gui_state(default_gui_state_path())
            state_config_dir = str(gui_state.get("config_dir", "")).strip()
            if state_config_dir:
                config_dir = Path(state_config_dir).expanduser().resolve()
            result = run_load_sweep(
                project_root=root,
                config_source="text",
                text_config_dir=config_dir,
                use_preflight=False,
                prompt_runtime_dirs=True,
                prompt_plot_filter=True,
            )
            print(json.dumps(result.summary, indent=2, sort_keys=True))
            return 0
        return exit_code
    if args.command == "run-load-sweep":
        root = Path(args.base_dir).expanduser().resolve() if args.base_dir else Path(__file__).resolve().parents[2]
        plot_scope = (
            args.plot_scope
            or os.environ.get("PIPELINE29_PLOT_SCOPE", "").strip().lower()
            or "all"
        )
        compare_iter_pairs = (
            args.compare_iter_pairs
            or os.environ.get("PIPELINE29_COMPARE_ITER_PAIRS", "").strip()
            or None
        )
        use_default_dirs_env = os.environ.get("PIPELINE29_USE_DEFAULT_RUNTIME_DIRS", "").strip().lower()
        prompt_runtime_dirs = bool(args.prompt_runtime_dirs) and use_default_dirs_env not in ("1", "true", "yes")
        aggregation_mode = args.aggregation_mode or None
        sweep_bin_tol = args.sweep_bin_tol if args.sweep_bin_tol > 0 else None
        result = run_load_sweep(
            project_root=root,
            config_source=args.config_source,
            text_config_dir=Path(args.config_dir).expanduser().resolve() if args.config_dir else None,
            excel_path=Path(args.excel_path).expanduser().resolve() if args.excel_path else None,
            state_path=Path(args.state_path).expanduser().resolve() if args.state_path else None,
            process_dir=Path(args.process_dir).expanduser().resolve() if args.process_dir else None,
            out_dir=Path(args.out_dir).expanduser().resolve() if args.out_dir else None,
            use_preflight=bool(args.use_preflight),
            prompt_runtime_dirs=prompt_runtime_dirs,
            prompt_plot_filter=bool(args.prompt_plot_filter),
            plot_scope=plot_scope,
            compare_iter_pairs=compare_iter_pairs,
            aggregation_mode_override=aggregation_mode,
            sweep_bin_tol_override=sweep_bin_tol,
        )
        print(json.dumps(result.summary, indent=2, sort_keys=True))
        return 0
    if args.command == "convert-open":
        try:
            results = export_open_inputs(
                Path(args.input),
                output_root=Path(args.output_dir).expanduser().resolve() if args.output_dir else None,
                converter_path=Path(args.converter).expanduser().resolve() if args.converter else None,
                export_type=args.export_type,
                separator=args.separator,
                include_cycle_number=not args.no_cycle_number,
                cycles=args.cycles or None,
                name_mode=args.name_mode,
                output_name=args.output_name or None,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        summary = summarize_export_results(results)
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            for result in results:
                print(f"[OK] {result.source_open} -> {result.exported_csv}")
                if result.returncode != 0:
                    print(f"[WARN] OpenToCSV retornou codigo {result.returncode} para {result.source_open.name}.")
        return 0
    if args.command == "inspect-config":
        root = Path(__file__).resolve().parents[2]
        text_config_dir = Path(args.text_config_dir).expanduser().resolve() if args.text_config_dir else None
        excel_path = Path(args.excel_path).expanduser().resolve() if args.excel_path else None
        try:
            bundle = load_pipeline29_config_bundle(
                project_root=root,
                config_source=args.config_source,
                text_config_dir=text_config_dir,
                rebuild_text_config=args.rebuild_text_config,
                excel_path=excel_path,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        summary = summarize_config_bundle(bundle)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "show-runtime-state":
        state_path = Path(args.state_path).expanduser().resolve() if args.state_path else default_runtime_state_path()
        state = load_runtime_state(state_path)
        summary = summarize_runtime_state(state, state_path=state_path)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

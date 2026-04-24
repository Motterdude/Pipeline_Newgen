from __future__ import annotations

from typing import Callable, Tuple

from .constants import RUNTIME_AGGREGATION_LOAD, RUNTIME_AGGREGATION_SWEEP
from .models import RuntimePreflightSnapshot, RuntimeSelection
from .normalize import (
    normalize_runtime_aggregation_mode,
    normalize_runtime_selection,
    normalize_sweep_key,
    sweep_axis_label,
)

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except Exception:
    tk = None
    messagebox = None
    ttk = None


PreflightPromptResult = Tuple[str, RuntimeSelection]
InputFunc = Callable[[str], str]


def prompt_runtime_preflight_via_cli(
    snapshot: RuntimePreflightSnapshot,
    initial_selection: RuntimeSelection,
    *,
    input_func: InputFunc = input,
) -> PreflightPromptResult:
    print(f"[INFO] Pipeline_newgen_rev1 preflight | input: {snapshot.process_dir}")
    print(
        f"[INFO] .open found: {len(snapshot.conversion_status.open_files)} | "
        f"missing conversion: {len(snapshot.conversion_status.missing_csv_opens)}"
    )

    mode_raw = input_func(f"Processing mode [load/sweep] ({initial_selection.aggregation_mode}): ").strip().lower()
    mode = normalize_runtime_aggregation_mode(mode_raw or initial_selection.aggregation_mode)

    sweep_key = normalize_sweep_key(initial_selection.sweep_key)
    if mode == RUNTIME_AGGREGATION_SWEEP:
        options_txt = ", ".join(snapshot.available_sweep_keys)
        sweep_raw = input_func(f"Sweep variable [{options_txt}] ({sweep_key}): ").strip().lower()
        if sweep_raw:
            sweep_key = normalize_sweep_key(sweep_raw)

    if snapshot.conversion_status.missing_csv_opens:
        convert_raw = input_func("Convert missing .open files before processing? [Y/n]: ").strip().lower()
        if convert_raw not in {"", "y", "yes", "s", "sim"}:
            return "continue", normalize_runtime_selection(
                RuntimeSelection(
                    aggregation_mode=mode,
                    sweep_key=sweep_key,
                    sweep_x_col=initial_selection.sweep_x_col,
                    sweep_bin_tol=initial_selection.sweep_bin_tol,
                )
            )
        return "convert", normalize_runtime_selection(
            RuntimeSelection(
                aggregation_mode=mode,
                sweep_key=sweep_key,
                sweep_x_col=initial_selection.sweep_x_col,
                sweep_bin_tol=initial_selection.sweep_bin_tol,
            )
        )

    return "continue", normalize_runtime_selection(
        RuntimeSelection(
            aggregation_mode=mode,
            sweep_key=sweep_key,
            sweep_x_col=initial_selection.sweep_x_col,
            sweep_bin_tol=initial_selection.sweep_bin_tol,
        )
    )


def prompt_runtime_preflight_via_tk(
    snapshot: RuntimePreflightSnapshot,
    initial_selection: RuntimeSelection,
) -> PreflightPromptResult:
    if tk is None or ttk is None or messagebox is None:
        raise RuntimeError("Tkinter is not available for the runtime preflight.")

    root = tk.Tk()
    root.title("Pipeline_newgen_rev1 - runtime preflight")
    root.geometry("860x380")
    root.minsize(760, 320)
    root.columnconfigure(0, weight=1)

    action = {"value": "cancel"}
    mode_var = tk.StringVar(master=root, value=normalize_runtime_aggregation_mode(initial_selection.aggregation_mode))
    initial_sweep = initial_selection.sweep_key or snapshot.available_sweep_keys[0]
    sweep_var = tk.StringVar(master=root, value=normalize_sweep_key(initial_sweep))
    status_var = tk.StringVar(master=root, value="")

    frame = ttk.Frame(root, padding=14)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(1, weight=1)

    summary_lines = [
        f"Input: {snapshot.process_dir}",
        (
            f"LabVIEW: {snapshot.inventory.lv_count} | "
            f"KiBox CSV: {snapshot.inventory.kibox_csv_count} | "
            f"MoTeC CSV: {snapshot.inventory.motec_csv_count}"
        ),
        (
            f".open: {len(snapshot.conversion_status.open_files)} | "
            f"missing conversion: {len(snapshot.conversion_status.missing_csv_opens)}"
        ),
    ]
    ttk.Label(frame, text="\n".join(summary_lines), justify="left", wraplength=800).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 14)
    )

    ttk.Label(frame, text="Processing mode").grid(row=1, column=0, sticky="w", pady=(0, 10))
    mode_combo = ttk.Combobox(
        frame,
        textvariable=mode_var,
        state="readonly",
        values=[RUNTIME_AGGREGATION_LOAD, RUNTIME_AGGREGATION_SWEEP],
    )
    mode_combo.grid(row=1, column=1, sticky="ew", pady=(0, 10))

    ttk.Label(frame, text="Sweep variable").grid(row=2, column=0, sticky="w", pady=(0, 10))
    sweep_display_options = [sweep_axis_label(key) for key in snapshot.available_sweep_keys]
    display_to_key = {sweep_axis_label(key): key for key in snapshot.available_sweep_keys}
    sweep_display_var = tk.StringVar(master=root, value=sweep_axis_label(sweep_var.get()))
    sweep_combo = ttk.Combobox(
        frame,
        textvariable=sweep_display_var,
        state="readonly",
        values=sweep_display_options,
    )
    sweep_combo.grid(row=2, column=1, sticky="ew", pady=(0, 10))

    converter_text = (
        "There are .open files without pipeline CSV output. Convert them now if KiBox data is required."
        if snapshot.conversion_status.missing_csv_opens
        else "There are no .open files pending conversion in this dataset."
    )
    ttk.Label(frame, text=converter_text, justify="left", wraplength=800).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(6, 12)
    )

    ttk.Label(frame, textvariable=status_var, justify="left", wraplength=800).grid(
        row=4, column=0, columnspan=2, sticky="w", pady=(0, 12)
    )

    button_row = ttk.Frame(frame)
    button_row.grid(row=5, column=0, columnspan=2, sticky="ew")
    button_row.columnconfigure(0, weight=1)

    def refresh_status(*_args: object) -> None:
        mode = normalize_runtime_aggregation_mode(mode_var.get())
        sweep_key = display_to_key.get(sweep_display_var.get(), snapshot.available_sweep_keys[0])
        sweep_var.set(sweep_key)
        sweep_state = "readonly" if mode == RUNTIME_AGGREGATION_SWEEP else "disabled"
        sweep_combo.configure(state=sweep_state)
        if mode == RUNTIME_AGGREGATION_SWEEP:
            status_var.set(
                f"Sweep mode: load-based plots may be redirected to {sweep_axis_label(sweep_key)}."
            )
        else:
            status_var.set("Load mode: the classic Load_kW-based flow remains active.")

    mode_combo.bind("<<ComboboxSelected>>", refresh_status)
    sweep_combo.bind("<<ComboboxSelected>>", refresh_status)

    def convert_now() -> None:
        action["value"] = "convert"
        root.quit()

    def continue_now() -> None:
        action["value"] = "continue"
        root.quit()

    def cancel() -> None:
        action["value"] = "cancel"
        root.quit()

    convert_btn = ttk.Button(button_row, text="Convert missing .open", command=convert_now)
    convert_btn.grid(row=0, column=1, padx=(8, 8))
    if not snapshot.conversion_status.missing_csv_opens:
        convert_btn.configure(state="disabled")

    ttk.Button(button_row, text="Continue", command=continue_now).grid(row=0, column=2, padx=(8, 8))
    ttk.Button(button_row, text="Cancel", command=cancel).grid(row=0, column=3, padx=(8, 0))

    root.protocol("WM_DELETE_WINDOW", cancel)
    refresh_status()
    root.after(200, lambda: root.attributes("-topmost", False))
    root.mainloop()
    root.destroy()

    return action["value"], normalize_runtime_selection(
        RuntimeSelection(
            aggregation_mode=mode_var.get(),
            sweep_key=sweep_var.get(),
            sweep_x_col=initial_selection.sweep_x_col,
            sweep_bin_tol=initial_selection.sweep_bin_tol,
        )
    )


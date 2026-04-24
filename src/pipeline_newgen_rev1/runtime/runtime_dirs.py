from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Optional, Tuple

from ..config import RuntimeState

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:
    tk = None
    filedialog = None
    messagebox = None
    ttk = None


PromptRuntimeDirsFunc = Callable[[Path, Path], Tuple[Path, Path]]


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y", "sim", "s"}


def best_existing_dir(*candidates: object, fallback: Optional[Path] = None) -> Path:
    for candidate in candidates:
        raw = str(candidate or "").strip().strip('"').strip("'")
        if not raw:
            continue
        try:
            path = Path(raw).expanduser()
        except Exception:
            continue
        if path.exists() and path.is_dir():
            return path.resolve()
        if path.parent.exists() and path.parent.is_dir():
            return path.parent.resolve()
    if fallback is not None:
        return Path(fallback).expanduser().resolve()
    return Path.cwd().resolve()


def _run_windows_folder_dialog(*, title: str, initial_dir: Path) -> Optional[Path]:
    initial_dir = best_existing_dir(initial_dir)
    escaped_title = title.replace("'", "''")
    escaped_initial = str(initial_dir).replace("'", "''")
    ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '{escaped_title}'
$dialog.ShowNewFolderButton = $true
if (Test-Path -LiteralPath '{escaped_initial}') {{
    $dialog.SelectedPath = '{escaped_initial}'
}}
$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK -and $dialog.SelectedPath) {{
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
    exit 0
}}
exit 2
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True,
        text=True,
    )
    stdout_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    stdout = stdout_lines[0] if stdout_lines else ""
    stderr = completed.stderr.strip()
    if completed.returncode == 0 and stdout:
        return Path(stdout).expanduser().resolve()
    if completed.returncode == 2:
        return None
    raise RuntimeError(
        "Falha ao abrir o seletor nativo de pasta no Windows. "
        f"stdout={stdout!r} stderr={stderr!r} code={completed.returncode}"
    )


def _prompt_runtime_dirs_via_windows_dialog(initial_input_dir: Path, initial_out_dir: Path) -> Tuple[Path, Path]:
    print("[INFO] Abrindo seletor nativo do Windows para o diretorio de entrada...")
    input_dir = _run_windows_folder_dialog(
        title="Selecione o diretorio de entrada do pipeline",
        initial_dir=initial_input_dir,
    )
    if input_dir is None:
        raise SystemExit("Execucao cancelada pelo usuario na selecao do diretorio de entrada.")

    print("[INFO] Abrindo seletor nativo do Windows para o diretorio de saida...")
    out_dir = _run_windows_folder_dialog(
        title="Selecione o diretorio de saida do pipeline",
        initial_dir=initial_out_dir,
    )
    if out_dir is None:
        raise SystemExit("Execucao cancelada pelo usuario na selecao do diretorio de saida.")
    return input_dir, out_dir


def _prompt_runtime_dirs_via_tk_dialog(initial_input_dir: Path, initial_out_dir: Path) -> Tuple[Path, Path]:
    if tk is None or ttk is None or filedialog is None or messagebox is None:
        raise RuntimeError("Tkinter nao esta disponivel para selecionar RAW_INPUT_DIR e OUT_DIR.")

    root = tk.Tk()
    root.title("Pipeline newgen - Diretorios de execucao")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    input_var = tk.StringVar(master=root, value=str(initial_input_dir))
    out_var = tk.StringVar(master=root, value=str(initial_out_dir))
    result: dict[str, Path] = {}

    root.columnconfigure(1, weight=1)

    ttk.Label(
        root,
        text="Selecione o diretorio de entrada do pipeline e o diretorio de saida para esta execucao.",
    ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 10))

    ttk.Label(root, text="Input dir").grid(row=1, column=0, sticky="w", padx=(12, 8), pady=6)
    input_entry = ttk.Entry(root, textvariable=input_var, width=90)
    input_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=6)

    def browse_input() -> None:
        selected = filedialog.askdirectory(
            parent=root,
            title="Selecione o diretorio de entrada do pipeline",
            initialdir=str(best_existing_dir(input_var.get(), initial_input_dir)),
        )
        if selected:
            input_var.set(selected)

    ttk.Button(root, text="Browse...", command=browse_input).grid(row=1, column=2, sticky="e", padx=(0, 12), pady=6)

    ttk.Label(root, text="Out dir").grid(row=2, column=0, sticky="w", padx=(12, 8), pady=6)
    out_entry = ttk.Entry(root, textvariable=out_var, width=90)
    out_entry.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=6)

    def browse_output() -> None:
        selected = filedialog.askdirectory(
            parent=root,
            title="Selecione o diretorio de saida",
            initialdir=str(best_existing_dir(out_var.get(), initial_out_dir)),
        )
        if selected:
            out_var.set(selected)

    ttk.Button(root, text="Browse...", command=browse_output).grid(row=2, column=2, sticky="e", padx=(0, 12), pady=6)

    ttk.Label(
        root,
        text="A ultima selecao fica salva localmente e volta preenchida na proxima abertura.",
    ).grid(row=3, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 10))

    def confirm() -> None:
        raw_input = input_var.get().strip()
        out_input = out_var.get().strip()
        if not raw_input:
            messagebox.showerror("Pipeline newgen", "Selecione o diretorio de entrada.", parent=root)
            return
        if not out_input:
            messagebox.showerror("Pipeline newgen", "Selecione o diretorio de saida.", parent=root)
            return

        input_dir = Path(raw_input).expanduser().resolve()
        out_dir = Path(out_input).expanduser().resolve()
        if not input_dir.exists():
            messagebox.showerror("Pipeline newgen", f"Input dir nao existe:\n{input_dir}", parent=root)
            return
        if not input_dir.is_dir():
            messagebox.showerror("Pipeline newgen", f"Input dir nao e diretorio:\n{input_dir}", parent=root)
            return
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror(
                "Pipeline newgen",
                f"Nao consegui preparar o diretorio de saida:\n{out_dir}\n\n{exc}",
                parent=root,
            )
            return

        result["input_dir"] = input_dir
        result["out_dir"] = out_dir
        root.destroy()

    def cancel() -> None:
        root.destroy()

    button_row = ttk.Frame(root)
    button_row.grid(row=4, column=0, columnspan=3, sticky="e", padx=12, pady=(0, 12))
    ttk.Button(button_row, text="Cancelar", command=cancel).pack(side="right")
    ttk.Button(button_row, text="Confirmar", command=confirm).pack(side="right", padx=(0, 8))

    root.protocol("WM_DELETE_WINDOW", cancel)
    root.bind("<Return>", lambda _event: confirm())
    root.bind("<Escape>", lambda _event: cancel())
    input_entry.focus_set()

    root.update_idletasks()
    width = max(root.winfo_reqwidth(), 900)
    height = root.winfo_reqheight()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    pos_x = max((screen_w - width) // 2, 0)
    pos_y = max((screen_h - height) // 3, 0)
    root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    root.deiconify()
    root.lift()
    try:
        root.focus_force()
    except Exception:
        pass
    root.after(400, lambda: root.attributes("-topmost", False))
    root.mainloop()

    input_dir = result.get("input_dir")
    out_dir = result.get("out_dir")
    if input_dir is None or out_dir is None:
        raise SystemExit("Execucao cancelada pelo usuario na selecao de diretorios.")
    return input_dir, out_dir


def _prompt_runtime_dirs_via_cli(initial_input_dir: Path, initial_out_dir: Path) -> Tuple[Path, Path]:
    print("[WARN] GUI indisponivel. Caindo para entrada manual no terminal.")
    raw_input = input(f"RAW_INPUT_DIR [{initial_input_dir}]: ").strip()
    out_input = input(f"OUT_DIR [{initial_out_dir}]: ").strip()
    return (
        Path(raw_input or str(initial_input_dir)).expanduser().resolve(),
        Path(out_input or str(initial_out_dir)).expanduser().resolve(),
    )


def prompt_runtime_dirs(initial_input_dir: Path, initial_out_dir: Path) -> Tuple[Path, Path]:
    if os.name == "nt":
        try:
            return _prompt_runtime_dirs_via_windows_dialog(initial_input_dir, initial_out_dir)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"[WARN] Seletor nativo do Windows falhou: {exc}")
    try:
        return _prompt_runtime_dirs_via_tk_dialog(initial_input_dir, initial_out_dir)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[WARN] Popup Tkinter falhou: {exc}")
    return _prompt_runtime_dirs_via_cli(initial_input_dir, initial_out_dir)


def choose_runtime_dirs(
    *,
    initial_input_dir: Path,
    initial_out_dir: Path,
    runtime_state: Optional[RuntimeState] = None,
    prompt_func: Optional[PromptRuntimeDirsFunc] = None,
    force_prompt: bool = False,
) -> Tuple[Path, Path]:
    input_dir = best_existing_dir(
        runtime_state.raw_input_dir if runtime_state is not None else None,
        initial_input_dir,
        fallback=initial_input_dir,
    )
    out_dir = best_existing_dir(
        runtime_state.out_dir if runtime_state is not None else None,
        initial_out_dir,
        fallback=initial_out_dir,
    )

    use_defaults_env = _truthy(
        os.environ.get("PIPELINE_NEWGEN_USE_DEFAULT_RUNTIME_DIRS", "")
        or os.environ.get("PIPELINE30_USE_DEFAULT_RUNTIME_DIRS", "")
        or os.environ.get("PIPELINE29_USE_DEFAULT_RUNTIME_DIRS", "")
        or os.environ.get("PIPELINE28_USE_DEFAULT_RUNTIME_DIRS", "")
    )
    if use_defaults_env:
        print("[INFO] PIPELINE_NEWGEN_USE_DEFAULT_RUNTIME_DIRS ativo; usando RAW_INPUT_DIR/OUT_DIR sem popup.")
        return input_dir, out_dir

    use_gui_saved_dirs = (
        not force_prompt
        and runtime_state is not None
        and bool(runtime_state.dirs_configured_in_gui)
        and runtime_state.raw_input_dir is not None
        and runtime_state.out_dir is not None
    )
    if use_gui_saved_dirs:
        print("[INFO] Usando RAW_INPUT_DIR/OUT_DIR salvos pela GUI compartilhada; pulando popup de diretorios.")
        return input_dir, out_dir

    print("[INFO] Abrindo popup para selecionar RAW_INPUT_DIR e OUT_DIR...")
    return (prompt_func or prompt_runtime_dirs)(input_dir, out_dir)

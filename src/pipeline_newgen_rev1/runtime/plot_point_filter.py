from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from ..adapters import InputFileMeta
from ..config import default_app_state_dir

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QDialog,
        QHeaderView,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QStyleFactory,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except Exception:
    QApplication = None
    QCheckBox = None
    QDialog = None
    QHeaderView = None
    QHBoxLayout = None
    QLabel = None
    QMessageBox = None
    QPushButton = None
    QStyleFactory = None
    QTableWidget = None
    QTableWidgetItem = None
    QVBoxLayout = None
    QWidget = None
    Qt = None

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except Exception:
    tk = None
    messagebox = None
    ttk = None


PlotPointKey = Tuple[str, float]
PromptPlotPointFunc = Callable[[List[str], List[float], Dict[PlotPointKey, int]], Optional[Set[PlotPointKey]]]
PLOT_POINT_FILTER_STATE_PATH = default_app_state_dir() / "plot_point_filter_last.json"


def _canon_name(value: object) -> str:
    text = str(value).replace("\ufeff", "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def _to_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except Exception:
            return default
    text = str(value).replace("\ufeff", "").strip()
    if not text:
        return default
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return default


def _format_pct_for_label(value: object) -> str:
    numeric = _to_float(value, default=float("nan"))
    if not np.isfinite(numeric):
        return str(value or "").strip()
    if abs(numeric - round(numeric)) <= 1e-9:
        return str(int(round(numeric)))
    return f"{numeric:g}"


def _format_load_kw_label(value: object) -> str:
    numeric = _to_float(value, default=float("nan"))
    if not np.isfinite(numeric):
        return ""
    if abs(numeric - round(numeric)) <= 1e-9:
        return f"{int(round(numeric))}"
    return f"{numeric:g}"


def _fuel_label_from_components(
    dies_pct: object,
    biod_pct: object,
    etoh_pct: object,
    h2o_pct: object,
    tol: float = 0.6,
) -> str:
    dies = _to_float(dies_pct, default=float("nan"))
    biod = _to_float(biod_pct, default=float("nan"))
    etoh = _to_float(etoh_pct, default=float("nan"))
    h2o = _to_float(h2o_pct, default=float("nan"))

    def _near_zero(value: float) -> bool:
        return (not np.isfinite(value)) or abs(value) <= tol

    if np.isfinite(dies) and np.isfinite(biod) and abs(dies - 85.0) <= tol and abs(biod - 15.0) <= tol and _near_zero(etoh) and _near_zero(h2o):
        return "D85B15"
    if np.isfinite(etoh) and np.isfinite(h2o) and abs(etoh - 94.0) <= tol and abs(h2o - 6.0) <= tol and _near_zero(dies) and _near_zero(biod):
        return "E94H6"
    if np.isfinite(etoh) and np.isfinite(h2o) and abs(etoh - 75.0) <= tol and abs(h2o - 25.0) <= tol and _near_zero(dies) and _near_zero(biod):
        return "E75H25"
    if np.isfinite(etoh) and np.isfinite(h2o) and abs(etoh - 65.0) <= tol and abs(h2o - 35.0) <= tol and _near_zero(dies) and _near_zero(biod):
        return "E65H35"
    if np.isfinite(dies) and np.isfinite(biod) and _near_zero(etoh) and _near_zero(h2o):
        if abs(dies) <= tol:
            return f"B{_format_pct_for_label(biod)}"
        if abs(biod) <= tol:
            return f"D{_format_pct_for_label(dies)}"
        return f"D{_format_pct_for_label(dies)}B{_format_pct_for_label(biod)}"
    if np.isfinite(biod) and np.isfinite(etoh) and _near_zero(dies) and _near_zero(h2o):
        if abs(etoh) <= tol:
            return f"B{_format_pct_for_label(biod)}"
        if abs(biod) <= tol:
            return f"E{_format_pct_for_label(etoh)}"
        return f"B{_format_pct_for_label(biod)}E{_format_pct_for_label(etoh)}"
    if np.isfinite(dies) and np.isfinite(etoh) and _near_zero(biod) and _near_zero(h2o):
        if abs(etoh) <= tol:
            return f"D{_format_pct_for_label(dies)}"
        if abs(dies) <= tol:
            return f"E{_format_pct_for_label(etoh)}"
        return f"D{_format_pct_for_label(dies)}E{_format_pct_for_label(etoh)}"
    return ""


def _normalize_plot_point_key(fuel_label: object, load_kw: object) -> Optional[PlotPointKey]:
    label = str(fuel_label or "").strip()
    if not label:
        return None
    try:
        load = round(float(load_kw), 6)
    except Exception:
        return None
    if not np.isfinite(load):
        return None
    return label, load


def _plot_point_keys_to_jsonable(points: Set[PlotPointKey]) -> List[Dict[str, object]]:
    return [
        {"fuel_label": fuel_label, "load_kw": round(float(load_kw), 6)}
        for fuel_label, load_kw in sorted(points, key=lambda item: (_canon_name(item[0]), item[1]))
    ]


def load_plot_point_filter_state() -> Optional[Dict[str, object]]:
    try:
        if not PLOT_POINT_FILTER_STATE_PATH.exists():
            return None
        payload = json.loads(PLOT_POINT_FILTER_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    selected_points: Set[PlotPointKey] = set()
    for row in payload.get("selected_points", []) or []:
        if not isinstance(row, dict):
            continue
        key = _normalize_plot_point_key(row.get("fuel_label", ""), row.get("load_kw"))
        if key is not None:
            selected_points.add(key)
    available_points: Set[PlotPointKey] = set()
    for row in payload.get("available_points", []) or []:
        if not isinstance(row, dict):
            continue
        key = _normalize_plot_point_key(row.get("fuel_label", ""), row.get("load_kw"))
        if key is not None:
            available_points.add(key)
    return {
        "selected_points": selected_points,
        "available_points": available_points,
        "saved_at": str(payload.get("saved_at", "")).strip(),
    }


def save_plot_point_filter_state(selected_points: Set[PlotPointKey], available_points: Set[PlotPointKey]) -> None:
    try:
        PLOT_POINT_FILTER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "selected_points": _plot_point_keys_to_jsonable(selected_points),
            "available_points": _plot_point_keys_to_jsonable(available_points),
        }
        PLOT_POINT_FILTER_STATE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        print(f"[WARN] Nao consegui salvar a ultima selecao do filtro de plots: {exc}")


def _resolve_initial_selection(available_points: Set[PlotPointKey]) -> Tuple[Dict[PlotPointKey, bool], str]:
    defaults = {key: True for key in available_points}
    state = load_plot_point_filter_state()
    if state is None:
        return defaults, "Sem ultima selecao salva. Todos os pontos vieram marcados."
    saved_available = set(state.get("available_points", set()) or set())
    saved_selected = set(state.get("selected_points", set()) or set())
    matched_known_points = 0
    for key in sorted(available_points):
        if key in saved_available:
            defaults[key] = key in saved_selected
            matched_known_points += 1
    if matched_known_points == 0:
        return defaults, "Ultima selecao salva nao combinou com este conjunto. Todos os pontos vieram marcados."
    new_points = available_points - saved_available
    selected_count = sum(1 for selected in defaults.values() if selected)
    message = f"Ultima selecao carregada automaticamente: {selected_count} / {len(available_points)} ponto(s) marcados."
    if new_points:
        message += f" {len(new_points)} ponto(s) novo(s) ficaram selecionados por padrao."
    return defaults, message


def _preferred_fuel_label_order(labels: Sequence[str]) -> List[str]:
    preferred = ["D85B15", "E94H6", "E75H25", "E65H35"]
    uniq: List[str] = []
    seen: Set[str] = set()
    for value in labels:
        label = str(value).strip()
        if not label or label in seen:
            continue
        uniq.append(label)
        seen.add(label)
    ordered = [label for label in preferred if label in seen]
    extras = sorted([label for label in uniq if label not in ordered], key=_canon_name)
    return ordered + extras


def _build_plot_point_catalog_from_metas(metas: Sequence[InputFileMeta]) -> Tuple[List[str], List[float], Dict[PlotPointKey, int]]:
    rows: List[PlotPointKey] = []
    for meta in metas:
        label = _fuel_label_from_components(meta.dies_pct, meta.biod_pct, meta.etoh_pct, meta.h2o_pct)
        if not label or meta.load_kw is None or not np.isfinite(meta.load_kw):
            continue
        rows.append((label, round(float(meta.load_kw), 6)))
    if not rows:
        return [], [], {}
    counts: Dict[PlotPointKey, int] = {}
    for key in rows:
        counts[key] = counts.get(key, 0) + 1
    fuel_labels = _preferred_fuel_label_order([fuel_label for fuel_label, _ in counts.keys()])
    load_values = sorted({float(load_kw) for _, load_kw in counts.keys()})
    return fuel_labels, load_values, counts


def _plot_point_fuel_labels(df: pd.DataFrame) -> pd.Series:
    if "Fuel_Label" in df.columns:
        labels = df["Fuel_Label"].copy()
        labels = labels.where(labels.astype("object").map(lambda value: str(value or "").strip() != ""), pd.NA)
    else:
        labels = pd.Series(pd.NA, index=df.index, dtype="object")
    fallback = df.apply(
        lambda row: _fuel_label_from_components(
            row.get("DIES_pct"),
            row.get("BIOD_pct"),
            row.get("EtOH_pct"),
            row.get("H2O_pct"),
        ),
        axis=1,
    )
    labels = labels.where(labels.notna(), fallback)
    return labels.where(labels.astype("object").map(lambda value: str(value or "").strip() != ""), pd.NA)


def _build_plot_point_catalog(df: pd.DataFrame) -> Tuple[List[str], List[float], Dict[PlotPointKey, int]]:
    if df is None or df.empty:
        return [], [], {}
    labels = _plot_point_fuel_labels(df)
    loads = pd.to_numeric(df.get("Load_kW", pd.Series(pd.NA, index=df.index)), errors="coerce").round(6)
    tmp = pd.DataFrame({"Fuel_Label": labels, "Load_kW": loads}, index=df.index).dropna(subset=["Fuel_Label", "Load_kW"])
    if tmp.empty:
        return [], [], {}
    counts_df = tmp.groupby(["Fuel_Label", "Load_kW"], dropna=False, sort=True).size().reset_index(name="N_points")
    counts: Dict[PlotPointKey, int] = {}
    for _, row in counts_df.iterrows():
        key = (str(row["Fuel_Label"]).strip(), float(row["Load_kW"]))
        counts[key] = int(row["N_points"])
    fuel_labels = _preferred_fuel_label_order(counts_df["Fuel_Label"].astype(str).tolist())
    load_values = sorted(float(value) for value in counts_df["Load_kW"].dropna().unique().tolist())
    return fuel_labels, load_values, counts


def _ensure_qt_application() -> Tuple[object, bool]:
    if QApplication is None:
        raise RuntimeError("PySide6 nao esta disponivel.")
    app = QApplication.instance()
    owns_app = False
    if app is None:
        app = QApplication(["pipeline-newgen"])
        owns_app = True
        if QStyleFactory is not None:
            try:
                if "Fusion" in QStyleFactory.keys():
                    app.setStyle("Fusion")
            except Exception:
                pass
    return app, owns_app


def _prompt_plot_point_filter_catalog_via_qt(
    fuel_labels: List[str],
    load_values: List[float],
    counts: Dict[PlotPointKey, int],
) -> Optional[Set[PlotPointKey]]:
    if QApplication is None or QDialog is None or QTableWidget is None or Qt is None:
        raise RuntimeError("PySide6 nao esta disponivel.")
    if not fuel_labels or not load_values or not counts:
        return None

    app, owns_app = _ensure_qt_application()
    _ = app
    dialog = QDialog()
    dialog.setWindowTitle("Pipeline newgen - filtro de pontos para plots")
    dialog.setModal(True)
    dialog.resize(1120, 760)

    main_layout = QVBoxLayout(dialog)
    title = QLabel("Selecione os pontos que entram nos graficos. Os calculos continuam completos.")
    title.setWordWrap(True)
    title.setStyleSheet("font-size: 15px; font-weight: 600;")
    subtitle = QLabel("Colunas = combustiveis | Linhas = cargas nominais | Tudo vem selecionado por padrao.")
    subtitle.setStyleSheet("color: #5f6b76;")
    main_layout.addWidget(title)
    main_layout.addWidget(subtitle)

    available_points = {key for key, count in counts.items() if count > 0}
    initial_selection, initial_message = _resolve_initial_selection(available_points)

    toolbar = QHBoxLayout()
    btn_select_all = QPushButton("Selecionar tudo")
    btn_clear_all = QPushButton("Limpar tudo")
    btn_load_last = QPushButton("Carregar ultima")
    btn_save_last = QPushButton("Salvar atual")
    info_label = QLabel("Numero pequeno = quantidade de linhas/iteracoes do ponto.")
    info_label.setStyleSheet("color: #5f6b76;")
    status_label = QLabel()
    status_label.setStyleSheet("font-weight: 600;")
    toolbar.addWidget(btn_select_all)
    toolbar.addWidget(btn_clear_all)
    toolbar.addWidget(btn_load_last)
    toolbar.addWidget(btn_save_last)
    toolbar.addSpacing(8)
    toolbar.addWidget(info_label)
    toolbar.addStretch(1)
    toolbar.addWidget(status_label)
    main_layout.addLayout(toolbar)

    selection_info_label = QLabel(initial_message)
    selection_info_label.setWordWrap(True)
    selection_info_label.setStyleSheet("color: #5f6b76;")
    main_layout.addWidget(selection_info_label)

    table = QTableWidget(len(load_values), len(fuel_labels))
    table.setHorizontalHeaderLabels(fuel_labels)
    table.setVerticalHeaderLabels([_format_load_kw_label(value) for value in load_values])
    table.setShowGrid(True)
    table.setAlternatingRowColors(True)
    table.setSelectionMode(QTableWidget.NoSelection)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setFocusPolicy(Qt.NoFocus)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
    table.verticalHeader().setDefaultSectionSize(38)
    table.horizontalHeader().setMinimumSectionSize(120)
    main_layout.addWidget(table, stretch=1)

    checkbox_map: Dict[PlotPointKey, object] = {}

    def refresh_status() -> None:
        selected = sum(1 for checkbox in checkbox_map.values() if bool(checkbox.isChecked()))
        status_label.setText(f"Pontos selecionados: {selected} / {len(checkbox_map)}")

    def set_all(value: bool) -> None:
        for checkbox in checkbox_map.values():
            checkbox.setChecked(value)
        refresh_status()

    def selected_points_now() -> Set[PlotPointKey]:
        return {key for key, checkbox in checkbox_map.items() if bool(checkbox.isChecked())}

    def load_last_selection() -> None:
        defaults, message = _resolve_initial_selection(available_points)
        for key, checkbox in checkbox_map.items():
            checkbox.setChecked(bool(defaults.get(key, True)))
        refresh_status()
        selection_info_label.setText(message)

    def save_current_selection() -> None:
        selected = selected_points_now()
        save_plot_point_filter_state(selected, available_points)
        selection_info_label.setText(
            f"Selecao atual salva como ultima: {len(selected)} / {len(available_points)} ponto(s) marcados."
        )

    for row_idx, load_kw in enumerate(load_values):
        for col_idx, fuel_label in enumerate(fuel_labels):
            key = (fuel_label, float(load_kw))
            count = counts.get(key, 0)
            if count <= 0:
                item = QTableWidgetItem("-")
                item.setTextAlignment(int(Qt.AlignCenter))
                item.setFlags(Qt.ItemIsEnabled)
                table.setItem(row_idx, col_idx, item)
                continue
            checkbox = QCheckBox()
            checkbox.setChecked(bool(initial_selection.get(key, True)))
            checkbox.stateChanged.connect(lambda _state, _refresh=refresh_status: _refresh())
            count_label = QLabel("" if count == 1 else f"{count}x")
            count_label.setAlignment(Qt.AlignCenter)
            count_label.setStyleSheet("color: #5f6b76; font-size: 10px;")
            cell_widget = QWidget()
            cell_layout = QVBoxLayout(cell_widget)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(0)
            cell_layout.addWidget(checkbox, alignment=Qt.AlignCenter)
            cell_layout.addWidget(count_label, alignment=Qt.AlignCenter)
            table.setCellWidget(row_idx, col_idx, cell_widget)
            checkbox_map[key] = checkbox

    refresh_status()

    buttons_layout = QHBoxLayout()
    buttons_layout.addStretch(1)
    btn_cancel = QPushButton("Cancelar")
    btn_run = QPushButton("Gerar graficos")
    btn_run.setDefault(True)
    buttons_layout.addWidget(btn_cancel)
    buttons_layout.addWidget(btn_run)
    main_layout.addLayout(buttons_layout)

    btn_select_all.clicked.connect(lambda: set_all(True))
    btn_clear_all.clicked.connect(lambda: set_all(False))
    btn_load_last.clicked.connect(load_last_selection)
    btn_save_last.clicked.connect(save_current_selection)

    selected_result: dict[str, object] = {"selected": None}

    def accept_selection() -> None:
        selected = selected_points_now()
        if not selected:
            QMessageBox.critical(dialog, "Pipeline newgen", "Selecione pelo menos um ponto para gerar os graficos.")
            return
        save_plot_point_filter_state(selected, available_points)
        selected_result["selected"] = selected
        dialog.accept()

    btn_run.clicked.connect(accept_selection)
    btn_cancel.clicked.connect(dialog.reject)

    if dialog.exec() != QDialog.Accepted:
        raise SystemExit("Execucao cancelada pelo usuario na selecao de pontos para plot.")
    selected = selected_result.get("selected")
    if selected is None:
        raise SystemExit("Execucao cancelada pelo usuario na selecao de pontos para plot.")
    if owns_app:
        app.quit()
    return set(selected)


def _prompt_plot_point_filter_catalog_via_tk(
    fuel_labels: List[str],
    load_values: List[float],
    counts: Dict[PlotPointKey, int],
) -> Optional[Set[PlotPointKey]]:
    if tk is None or ttk is None or messagebox is None:
        raise RuntimeError("Tkinter nao esta disponivel.")
    if not fuel_labels or not load_values or not counts:
        return None

    result: dict[str, object] = {"selected": None}
    available_points = {key for key, count in counts.items() if count > 0}
    initial_selection, initial_message = _resolve_initial_selection(available_points)
    root = tk.Tk()
    root.title("Pipeline newgen - filtro de pontos para plots")
    root.withdraw()
    root.resizable(True, True)
    root.attributes("-topmost", True)

    ttk.Label(
        root,
        text="Selecione os pontos que entram nos graficos. Os calculos continuam completos.",
        wraplength=1100,
        justify="left",
    ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 4))
    ttk.Label(
        root,
        text="Colunas = combustiveis | Linhas = cargas nominais. Tudo vem selecionado por padrao.",
    ).grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 8))
    selection_info_var = tk.StringVar(master=root, value=initial_message)
    ttk.Label(
        root,
        textvariable=selection_info_var,
        wraplength=1100,
        justify="left",
    ).grid(row=2, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 8))

    toolbar = ttk.Frame(root)
    toolbar.grid(row=3, column=0, columnspan=3, sticky="we", padx=12, pady=(0, 8))
    toolbar.columnconfigure(5, weight=1)

    body = ttk.Frame(root)
    body.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=12, pady=0)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(4, weight=1)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    canvas = tk.Canvas(body, highlightthickness=0)
    vbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
    hbar = ttk.Scrollbar(body, orient="horizontal", command=canvas.xview)
    canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    vbar.grid(row=0, column=1, sticky="ns")
    hbar.grid(row=1, column=0, sticky="ew")

    grid_frame = ttk.Frame(canvas)
    canvas_window = canvas.create_window((0, 0), window=grid_frame, anchor="nw")

    def _sync_canvas(_event: object = None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(canvas_window, width=max(canvas.winfo_width(), grid_frame.winfo_reqwidth()))

    grid_frame.bind("<Configure>", _sync_canvas)
    canvas.bind("<Configure>", _sync_canvas)

    header_bg = "#f4f6f8"
    cell_border = "#d7dce1"

    def make_cell(row: int, column: int, *, bg: str = "white") -> tk.Frame:
        cell = tk.Frame(
            grid_frame,
            bg=bg,
            highlightbackground=cell_border,
            highlightthickness=1,
            bd=0,
            padx=3,
            pady=0,
        )
        cell.grid(row=row, column=column, sticky="nsew")
        return cell

    header_cell = make_cell(0, 0, bg=header_bg)
    ttk.Label(header_cell, text="Carga (kW)", anchor="center").pack(fill="both", expand=True)
    cell_vars: Dict[PlotPointKey, tk.BooleanVar] = {}

    for col_idx, fuel_label in enumerate(fuel_labels, start=1):
        header_cell = make_cell(0, col_idx, bg=header_bg)
        ttk.Label(header_cell, text=fuel_label, anchor="center", justify="center").pack(fill="both", expand=True)
        grid_frame.columnconfigure(col_idx, weight=1)

    for row_idx, load_kw in enumerate(load_values, start=1):
        load_cell = make_cell(row_idx, 0, bg=header_bg)
        ttk.Label(load_cell, text=_format_load_kw_label(load_kw), anchor="center").pack(fill="both", expand=True)
        for col_idx, fuel_label in enumerate(fuel_labels, start=1):
            key = (fuel_label, float(load_kw))
            count = counts.get(key, 0)
            if count <= 0:
                empty_cell = make_cell(row_idx, col_idx)
                ttk.Label(empty_cell, text="-", anchor="center").pack(fill="both", expand=True)
                continue
            var = tk.BooleanVar(value=True)
            var.set(bool(initial_selection.get(key, True)))
            cell_vars[key] = var
            point_cell = make_cell(row_idx, col_idx)
            inner = ttk.Frame(point_cell)
            inner.pack(fill="both", expand=True)
            ttk.Checkbutton(inner, variable=var).pack(anchor="center", pady=0)
            ttk.Label(inner, text="" if count == 1 else f"{count}x", anchor="center", justify="center").pack(anchor="center")

    status_var = tk.StringVar()

    def refresh_status() -> None:
        selected = sum(1 for var in cell_vars.values() if bool(var.get()))
        status_var.set(f"Pontos selecionados para plot: {selected} / {len(cell_vars)}")

    for var in cell_vars.values():
        var.trace_add("write", lambda *_args: refresh_status())

    def set_all(value: bool) -> None:
        for var in cell_vars.values():
            var.set(value)

    def load_last_selection() -> None:
        defaults, message = _resolve_initial_selection(available_points)
        for key, var in cell_vars.items():
            var.set(bool(defaults.get(key, True)))
        selection_info_var.set(message)

    def save_current_selection() -> None:
        selected = {key for key, var in cell_vars.items() if bool(var.get())}
        save_plot_point_filter_state(selected, available_points)
        selection_info_var.set(
            f"Selecao atual salva como ultima: {len(selected)} / {len(available_points)} ponto(s) marcados."
        )

    def confirm() -> None:
        selected = {key for key, var in cell_vars.items() if bool(var.get())}
        if not selected:
            messagebox.showerror("Pipeline newgen", "Selecione pelo menos um ponto para gerar os graficos.", parent=root)
            return
        save_plot_point_filter_state(selected, available_points)
        result["selected"] = selected
        root.destroy()

    def cancel() -> None:
        root.destroy()

    ttk.Button(toolbar, text="Selecionar tudo", command=lambda: set_all(True)).grid(row=0, column=0, padx=(0, 8), pady=0)
    ttk.Button(toolbar, text="Limpar tudo", command=lambda: set_all(False)).grid(row=0, column=1, padx=(0, 8), pady=0)
    ttk.Button(toolbar, text="Carregar ultima", command=load_last_selection).grid(row=0, column=2, padx=(0, 8), pady=0)
    ttk.Button(toolbar, text="Salvar atual", command=save_current_selection).grid(row=0, column=3, padx=(0, 8), pady=0)
    ttk.Label(toolbar, text="Numero no checkbox = quantidade de linhas/iteracoes para o ponto.").grid(row=0, column=4, sticky="w")
    ttk.Label(toolbar, textvariable=status_var).grid(row=0, column=5, sticky="e")
    refresh_status()

    buttons = ttk.Frame(root)
    buttons.grid(row=5, column=0, columnspan=3, sticky="e", padx=12, pady=(8, 12))
    ttk.Button(buttons, text="Cancelar", command=cancel).pack(side="right")
    ttk.Button(buttons, text="Gerar graficos", command=confirm).pack(side="right", padx=(0, 8))

    root.protocol("WM_DELETE_WINDOW", cancel)
    root.bind("<Return>", lambda _event: confirm())
    root.bind("<Escape>", lambda _event: cancel())

    root.update_idletasks()
    width = min(max(root.winfo_reqwidth(), 1000), max(root.winfo_screenwidth() - 80, 1000))
    height = min(max(root.winfo_reqheight(), 600), max(root.winfo_screenheight() - 120, 600))
    pos_x = max((root.winfo_screenwidth() - width) // 2, 0)
    pos_y = max((root.winfo_screenheight() - height) // 4, 0)
    root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
    root.deiconify()
    root.lift()
    try:
        root.focus_force()
    except Exception:
        pass
    root.after(400, lambda: root.attributes("-topmost", False))
    root.mainloop()

    selected = result.get("selected")
    if selected is None:
        raise SystemExit("Execucao cancelada pelo usuario na selecao de pontos para plot.")
    return set(selected)


def prompt_plot_point_filter(df: pd.DataFrame, *, prompt_func: Optional[PromptPlotPointFunc] = None) -> Optional[Set[PlotPointKey]]:
    fuel_labels, load_values, counts = _build_plot_point_catalog(df)
    if not fuel_labels or not load_values or not counts:
        print("[WARN] Nao encontrei pontos com Fuel_Label e Load_kW para abrir o filtro de plots. Vou usar todos.")
        return None
    if prompt_func is not None:
        return prompt_func(fuel_labels, load_values, counts)
    if QApplication is not None:
        try:
            return _prompt_plot_point_filter_catalog_via_qt(fuel_labels, load_values, counts)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"[WARN] GUI PySide6 de filtro de pontos falhou: {exc}. Tentando fallback...")
    if os.name == "nt" or (tk is not None and ttk is not None):
        try:
            return _prompt_plot_point_filter_catalog_via_tk(fuel_labels, load_values, counts)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"[WARN] GUI de filtro de pontos falhou: {exc}. Vou usar todos os pontos.")
            return None
    print("[WARN] GUI de filtro de pontos indisponivel neste ambiente. Vou usar todos os pontos.")
    return None


def prompt_plot_point_filter_from_metas(
    metas: Sequence[InputFileMeta],
    *,
    prompt_func: Optional[PromptPlotPointFunc] = None,
) -> Optional[Set[PlotPointKey]]:
    valid_meta_count = 0
    for meta in metas:
        label = _fuel_label_from_components(meta.dies_pct, meta.biod_pct, meta.etoh_pct, meta.h2o_pct)
        if label and meta.load_kw is not None and np.isfinite(meta.load_kw):
            valid_meta_count += 1
    if valid_meta_count < len(metas):
        print(
            "[INFO] Alguns pontos dependem de inferencia posterior de carga/composicao; "
            "vou abrir o filtro de plots depois do processamento completo."
        )
        return None
    fuel_labels, load_values, counts = _build_plot_point_catalog_from_metas(metas)
    if not fuel_labels or not load_values or not counts:
        return None
    if prompt_func is not None:
        return prompt_func(fuel_labels, load_values, counts)
    if QApplication is not None:
        try:
            return _prompt_plot_point_filter_catalog_via_qt(fuel_labels, load_values, counts)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"[WARN] GUI PySide6 de filtro de pontos falhou: {exc}. Tentando fallback...")
    if os.name == "nt" or (tk is not None and ttk is not None):
        try:
            return _prompt_plot_point_filter_catalog_via_tk(fuel_labels, load_values, counts)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"[WARN] GUI de filtro de pontos falhou: {exc}. Vou usar todos os pontos.")
            return None
    return None


def apply_plot_point_filter(df: pd.DataFrame, selected_points: Optional[Set[PlotPointKey]]) -> pd.DataFrame:
    if df is None or df.empty or not selected_points:
        return df
    labels = _plot_point_fuel_labels(df)
    loads = pd.to_numeric(df.get("Load_kW", pd.Series(pd.NA, index=df.index)), errors="coerce").round(6)
    mask = pd.Series(False, index=df.index)
    for fuel_label, load_kw in selected_points:
        mask |= (labels.astype("object") == fuel_label) & (loads == round(float(load_kw), 6))
    return df.loc[mask].copy()

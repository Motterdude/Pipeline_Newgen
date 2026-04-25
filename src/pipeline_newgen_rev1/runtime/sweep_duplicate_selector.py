"""Sweep duplicate selector: fuel × sweep_value matrix with per-file checkboxes.

Port of legacy nanum_pipeline_30.py L4575-4920.
Follows the same injectable-prompt pattern as plot_point_filter.py.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set, Tuple

import pandas as pd

from ..ui.runtime_preflight.constants import SWEEP_VALUE_COL
from .plot_point_filter import (
    _canon_name,
    _plot_point_fuel_labels,
    _preferred_fuel_label_order,
)
from .sweep_binning import format_sweep_bin_label

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
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except Exception:
    QApplication = None  # type: ignore[assignment,misc]
    QCheckBox = None  # type: ignore[assignment,misc]
    QDialog = None  # type: ignore[assignment,misc]
    QHeaderView = None  # type: ignore[assignment,misc]
    QHBoxLayout = None  # type: ignore[assignment,misc]
    QLabel = None  # type: ignore[assignment,misc]
    QMessageBox = None  # type: ignore[assignment,misc]
    QPushButton = None  # type: ignore[assignment,misc]
    QTableWidget = None  # type: ignore[assignment,misc]
    QTableWidgetItem = None  # type: ignore[assignment,misc]
    QVBoxLayout = None  # type: ignore[assignment,misc]
    QWidget = None  # type: ignore[assignment,misc]
    Qt = None  # type: ignore[assignment,misc]

SweepDuplicateKey = Tuple[str, float]
SweepDuplicateCatalog = Dict[SweepDuplicateKey, List[str]]
PromptSweepDuplicateFunc = Callable[
    [List[str], List[float], SweepDuplicateCatalog],
    Optional[Set[str]],
]


def _to_str_or_empty(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def build_sweep_duplicate_catalog(
    df: pd.DataFrame,
    *,
    x_col: str,
) -> Tuple[List[str], List[float], SweepDuplicateCatalog]:
    if df is None or df.empty or "BaseName" not in df.columns or x_col not in df.columns:
        return [], [], {}

    labels = _plot_point_fuel_labels(df)
    x_values = pd.to_numeric(
        df.get(x_col, pd.Series(pd.NA, index=df.index)), errors="coerce"
    ).round(4)
    basenames = (
        df.get("BaseName", pd.Series(pd.NA, index=df.index, dtype="object"))
        .map(_to_str_or_empty)
    )
    tmp = pd.DataFrame(
        {
            "Fuel_Label": labels,
            "Sweep_Value_Runtime": x_values,
            "BaseName": basenames,
        },
        index=df.index,
    ).dropna(subset=["Fuel_Label", "Sweep_Value_Runtime"])
    tmp = tmp[tmp["BaseName"].astype(str).str.strip().ne("")]
    if tmp.empty:
        return [], [], {}

    cell_map: SweepDuplicateCatalog = {}
    for (fuel_label, sweep_value), group in tmp.groupby(
        ["Fuel_Label", "Sweep_Value_Runtime"], dropna=False, sort=True
    ):
        names = sorted(
            dict.fromkeys(group["BaseName"].astype(str).tolist()),
            key=_canon_name,
        )
        cell_map[(str(fuel_label), float(sweep_value))] = names

    fuel_labels = _preferred_fuel_label_order(
        [fuel for fuel, _value in cell_map.keys()]
    )
    sweep_values = sorted({float(value) for _fuel, value in cell_map.keys()})
    return fuel_labels, sweep_values, cell_map


def apply_sweep_duplicate_filter(
    df: pd.DataFrame,
    selected_basenames: Optional[Set[str]],
) -> pd.DataFrame:
    if df is None or df.empty or not selected_basenames or "BaseName" not in df.columns:
        return df
    out = df[df["BaseName"].map(_to_str_or_empty).isin(selected_basenames)].copy()
    print(
        f"[INFO] Sweep selector: mantive {len(out)}/{len(df)} "
        f"ensaio(s) apos o filtro de duplicatas."
    )
    return out


def _ensure_qt_application() -> Tuple["QApplication", bool]:
    if QApplication is None:
        raise RuntimeError("PySide6 nao esta disponivel.")
    app = QApplication.instance()
    if app is not None:
        return app, False
    return QApplication([]), True


class _SweepDuplicateSelectorDialog(QDialog if QDialog is not None else object):  # type: ignore[misc]
    def __init__(
        self,
        *,
        fuel_labels: List[str],
        sweep_values: List[float],
        cell_map: SweepDuplicateCatalog,
        axis_label: str,
        parent=None,
    ) -> None:
        if QDialog is None:
            raise RuntimeError("PySide6 nao esta disponivel para o seletor de duplicatas.")
        super().__init__(parent)
        self.setWindowTitle("Pipeline newgen — seletor de ensaios por combustivel x varredura")
        self.resize(1280, 780)
        self.fuel_labels = fuel_labels
        self.sweep_values = sweep_values
        self.cell_map = cell_map
        self.axis_label = axis_label
        self._file_checkboxes: Dict[SweepDuplicateKey, List[Tuple[str, QCheckBox]]] = {}
        self._master_checkboxes: Dict[SweepDuplicateKey, QCheckBox] = {}
        self._syncing_keys: set = set()

        root = QVBoxLayout(self)
        intro = QLabel(
            "Colunas = valores da varredura. Linhas = combustiveis. "
            "Cada celula lista os arquivos do ponto. Em duplicatas, o checkbox principal "
            "marca todos os arquivos daquele ponto; os checkboxes individuais permitem "
            "selecionar arquivo por arquivo."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        toolbar = QHBoxLayout()
        keep_all_btn = QPushButton("Selecionar tudo", self)
        clear_all_btn = QPushButton("Limpar tudo", self)
        keep_first_btn = QPushButton("Manter primeiro nas duplicatas", self)
        self.status_label = QLabel(self)
        self.status_label.setStyleSheet("font-weight: 600;")
        toolbar.addWidget(keep_all_btn)
        toolbar.addWidget(clear_all_btn)
        toolbar.addWidget(keep_first_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.status_label)
        root.addLayout(toolbar)

        self.table = QTableWidget(len(fuel_labels), len(sweep_values), self)
        self.table.setHorizontalHeaderLabels(
            [format_sweep_bin_label(v) for v in sweep_values]
        )
        self.table.setVerticalHeaderLabels(fuel_labels)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setWordWrap(True)
        self.table.setStyleSheet(
            "QTableWidget { gridline-color: #d7dce1; background: #ffffff; "
            "alternate-background-color: #fbfcfd; border: 1px solid #d7dce1; } "
            "QHeaderView::section { background: #f3f5f7; color: #1f2933; "
            "padding: 6px; border: 1px solid #d7dce1; font-weight: 600; }"
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(280)
        self.table.horizontalHeader().setMinimumSectionSize(170)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        ok_btn = QPushButton("Aplicar", self)
        cancel_btn = QPushButton("Cancelar", self)
        button_row.addStretch(1)
        button_row.addWidget(ok_btn)
        button_row.addWidget(cancel_btn)
        root.addLayout(button_row)

        keep_all_btn.clicked.connect(self._select_all)
        clear_all_btn.clicked.connect(self._clear_all)
        keep_first_btn.clicked.connect(self._keep_first_per_duplicate)
        ok_btn.clicked.connect(self._accept_selection)
        cancel_btn.clicked.connect(self.reject)

        for row_idx, fuel_label in enumerate(self.fuel_labels):
            for col_idx, sweep_value in enumerate(self.sweep_values):
                key = (fuel_label, sweep_value)
                available = self.cell_map.get(key, [])
                if not available:
                    item = QTableWidgetItem("-")
                    item.setTextAlignment(int(Qt.AlignCenter))
                    item.setFlags(Qt.ItemIsEnabled)
                    self.table.setItem(row_idx, col_idx, item)
                    continue
                self.table.setCellWidget(
                    row_idx, col_idx, self._build_cell_widget(key, available)
                )
        self.table.resizeRowsToContents()
        self._refresh_status()

    def _build_cell_widget(
        self, key: SweepDuplicateKey, available: List[str]
    ) -> "QWidget":
        cell_widget = QWidget(self.table)
        cell_widget.setStyleSheet(
            "QWidget { background: transparent; } "
            "QLabel { color: #1f2933; background: transparent; } "
            "QCheckBox { color: #1f2933; background: transparent; }"
        )
        cell_layout = QVBoxLayout(cell_widget)
        cell_layout.setContentsMargins(6, 6, 6, 6)
        cell_layout.setSpacing(4)

        if len(available) > 1:
            master_cb = QCheckBox(
                f"Todos ({len(available)}/{len(available)})", cell_widget
            )
            master_cb.setTristate(True)
            master_cb.stateChanged.connect(
                lambda state, _key=key: self._handle_master_change(_key, state)
            )
            cell_layout.addWidget(master_cb)
            self._master_checkboxes[key] = master_cb

        children: List[Tuple[str, "QCheckBox"]] = []
        for basename in available:
            row_w = QWidget(cell_widget)
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(6)
            cb = QCheckBox(row_w)
            cb.setChecked(True)
            cb.stateChanged.connect(
                lambda _state, _key=key: self._handle_child_change(_key)
            )
            lbl = QLabel(basename, row_w)
            lbl.setWordWrap(True)
            lbl.setToolTip(basename)
            lbl.setStyleSheet("color: #1f2933;")
            row_l.addWidget(cb, alignment=Qt.AlignTop)
            row_l.addWidget(lbl, 1)
            cell_layout.addWidget(row_w)
            children.append((basename, cb))

        self._file_checkboxes[key] = children
        self._refresh_master(key)
        return cell_widget

    def _selected_for_key(self, key: SweepDuplicateKey) -> List[str]:
        return [
            bn for bn, cb in self._file_checkboxes.get(key, []) if cb.isChecked()
        ]

    def _refresh_master(self, key: SweepDuplicateKey) -> None:
        master = self._master_checkboxes.get(key)
        if master is None:
            return
        children = self._file_checkboxes.get(key, [])
        n = sum(1 for _, cb in children if cb.isChecked())
        total = len(children)
        self._syncing_keys.add(key)
        try:
            master.setText(f"Todos ({n}/{total})")
            if n <= 0:
                master.setCheckState(Qt.Unchecked)
            elif n >= total:
                master.setCheckState(Qt.Checked)
            else:
                master.setCheckState(Qt.PartiallyChecked)
        finally:
            self._syncing_keys.discard(key)

    def _handle_master_change(self, key: SweepDuplicateKey, state: int) -> None:
        if key in self._syncing_keys:
            return
        if state not in {int(Qt.Checked), int(Qt.Unchecked)}:
            return
        checked = state == int(Qt.Checked)
        self._syncing_keys.add(key)
        try:
            for _, cb in self._file_checkboxes.get(key, []):
                cb.setChecked(checked)
        finally:
            self._syncing_keys.discard(key)
        self._refresh_master(key)
        self._refresh_status()

    def _handle_child_change(self, key: SweepDuplicateKey) -> None:
        if key in self._syncing_keys:
            return
        self._refresh_master(key)
        self._refresh_status()

    def _refresh_status(self) -> None:
        total_pts = len(self.cell_map)
        sel_pts = 0
        sel_files = 0
        dup_pts = sum(1 for v in self.cell_map.values() if len(v) > 1)
        for key in self.cell_map:
            sel = self._selected_for_key(key)
            if sel:
                sel_pts += 1
                sel_files += len(sel)
        self.status_label.setText(
            f"Pontos selecionados: {sel_pts}/{total_pts} | "
            f"Arquivos marcados: {sel_files} | Duplicatas: {dup_pts}"
        )

    def _select_all(self) -> None:
        for key, children in self._file_checkboxes.items():
            self._syncing_keys.add(key)
            try:
                for _, cb in children:
                    cb.setChecked(True)
            finally:
                self._syncing_keys.discard(key)
            self._refresh_master(key)
        self._refresh_status()

    def _clear_all(self) -> None:
        for key, children in self._file_checkboxes.items():
            self._syncing_keys.add(key)
            try:
                for _, cb in children:
                    cb.setChecked(False)
            finally:
                self._syncing_keys.discard(key)
            self._refresh_master(key)
        self._refresh_status()

    def _keep_first_per_duplicate(self) -> None:
        for key, children in self._file_checkboxes.items():
            self._syncing_keys.add(key)
            try:
                for idx, (_, cb) in enumerate(children):
                    cb.setChecked(len(children) == 1 or idx == 0)
            finally:
                self._syncing_keys.discard(key)
            self._refresh_master(key)
        self._refresh_status()

    def _accept_selection(self) -> None:
        if not self.selected_basenames():
            QMessageBox.critical(
                self,
                "Pipeline newgen",
                "Selecione pelo menos um ensaio para seguir com o sweep.",
            )
            return
        self.accept()

    def selected_basenames(self) -> Set[str]:
        selected: Set[str] = set()
        for key in self.cell_map:
            selected.update(
                s for s in (str(n).strip() for n in self._selected_for_key(key)) if s
            )
        return selected


def prompt_sweep_duplicate_selector(
    df: pd.DataFrame,
    *,
    x_col: str,
    axis_label: str,
    prompt_func: Optional[PromptSweepDuplicateFunc] = None,
) -> Optional[Set[str]]:
    fuel_labels, sweep_values, cell_map = build_sweep_duplicate_catalog(df, x_col=x_col)
    if not cell_map:
        return None

    duplicate_cells = {k: v for k, v in cell_map.items() if len(v) > 1}
    if not duplicate_cells:
        print("[INFO] Sweep selector: nao encontrei duplicatas por combustivel x varredura.")
        return None

    if prompt_func is not None:
        return prompt_func(fuel_labels, sweep_values, cell_map)

    try:
        app, owns_app = _ensure_qt_application()
    except Exception as exc:
        print(
            f"[WARN] GUI de duplicatas sweep indisponivel: {exc}. "
            f"Vou manter todos os ensaios."
        )
        return None

    try:
        dialog = _SweepDuplicateSelectorDialog(
            fuel_labels=fuel_labels,
            sweep_values=sweep_values,
            cell_map=cell_map,
            axis_label=axis_label,
        )
        if dialog.exec() != QDialog.Accepted:
            print("[INFO] Sweep selector cancelado; vou manter todos os ensaios.")
            return None
        selected = dialog.selected_basenames()
        if not selected:
            print(
                "[WARN] Sweep selector retornou selecao vazia; vou manter todos os ensaios."
            )
            return None
        return selected
    finally:
        if owns_app:
            app.quit()

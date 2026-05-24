"""Preview Plot tab -- inline matplotlib rendering for plot configuration.

Provides a split-panel widget: left panel with plot parameter controls,
right panel with live-rendered matplotlib figure canvas.  All edits
auto-trigger a debounced re-render after 400 ms.
"""
from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtCore import QEvent, QStringListModel, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..runtime.unitary_plots.renderers import (
    plot_all_fuels,
    plot_all_fuels_xy,
    plot_all_fuels_with_value_labels,
    plot_all_fuels_delta_ref,
)
from ..runtime.unitary_plots.renderer_all_iterations import plot_all_iterations
from ..runtime.fuel_colors import fuel_color_map
from ..runtime.unitary_plots.config_parsing import (
    _parse_axis_spec,
    _parse_axis_limits,
    _parse_axis_value,
    _parse_csv_list_ints,
)
from ..runtime.final_table._helpers import _to_float, resolve_col


def _find_latest_kpis_xlsx(search_dirs: List[Path]) -> Optional[Path]:
    """Find the most recently modified lv_kpis_clean.xlsx across directories."""
    best: Optional[Path] = None
    best_mtime: float = 0.0
    for d in search_dirs:
        if not d.exists():
            continue
        for xlsx in d.rglob("lv_kpis_clean.xlsx"):
            try:
                mt = xlsx.stat().st_mtime
                if mt > best_mtime:
                    best_mtime = mt
                    best = xlsx
            except OSError:
                continue
    return best


_BUILTIN_PRESETS: Dict[str, Dict[str, str]] = {
    "Load (kW)": {
        "x_col": "Load_kW", "x_label": "Power (kW)",
        "x_min": "0", "x_max": "55", "x_step": "5", "series_col": "",
    },
    "Lambda Sweep": {
        "x_col": "Motec_Exhaust Lambda_mean_of_windows", "x_label": "Lambda",
        "x_min": "0.95", "x_max": "1.35", "x_step": "0.05", "series_col": "",
    },
    "Spark Sweep": {
        "x_col": "Motec_Ignition Timing_mean_of_windows", "x_label": "Spark Advance (deg)",
        "x_min": "", "x_max": "", "x_step": "2", "series_col": "",
    },
    "Nanum All Iterations": {
        "x_col": "Load_kW", "x_label": "Carga nominal (kW)",
        "x_min": "0", "x_max": "55", "x_step": "5", "series_col": "",
        "plot_type": "all_iterations_yx",
    },
    "Nanum Compare": {
        "x_col": "Load_kW", "x_label": "Carga nominal (kW)",
        "x_min": "0", "x_max": "55", "x_step": "5", "series_col": "",
        "plot_type": "compare_bl_vs_adtv",
    },
}


_AVAILABLE_MARKERS = [
    ("o", "Circle"), ("s", "Square"), ("D", "Diamond"), ("^", "Triangle up"),
    ("v", "Triangle down"), ("<", "Triangle left"), (">", "Triangle right"),
    ("P", "Plus filled"), ("X", "X filled"), ("*", "Star"), ("h", "Hexagon"),
    ("p", "Pentagon"),
]


_COMMENT_POSITIONS = [
    ("bottom-left", "Inferior esquerdo", 0.01, 0.01, "bottom", "left"),
    ("bottom-right", "Inferior direito", 0.99, 0.01, "bottom", "right"),
    ("top-left", "Superior esquerdo", 0.01, 0.97, "top", "left"),
    ("top-right", "Superior direito", 0.99, 0.97, "top", "right"),
]


def _empty_comment_data() -> Dict[str, Any]:
    return {"text": "", "font_size": 9, "bold": False, "italic": True, "color": "#333333", "position": "bottom-left"}


class CommentDialog(QDialog):
    """Dialog for editing a rich-text comment annotation on the plot."""

    applied = None  # signal-like: set by caller to receive Apply callbacks

    def __init__(self, data: Dict[str, Any], apply_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comentario do Grafico")
        self.setMinimumWidth(500)
        self.setMinimumHeight(320)
        self._apply_callback = apply_callback

        self._color = str(data.get("color", "#333333"))

        layout = QVBoxLayout(self)

        # Text editor
        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(str(data.get("text", "")))
        self._text_edit.setPlaceholderText("Digite o comentario aqui...")
        layout.addWidget(self._text_edit, 1)

        # Formatting toolbar
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(8)

        fmt_row.addWidget(QLabel("Tamanho:"))
        self._spin_size = QSpinBox()
        self._spin_size.setRange(6, 28)
        self._spin_size.setValue(int(data.get("font_size", 9)))
        fmt_row.addWidget(self._spin_size)

        self._chk_bold = QCheckBox("Negrito")
        self._chk_bold.setChecked(bool(data.get("bold", False)))
        fmt_row.addWidget(self._chk_bold)

        self._chk_italic = QCheckBox("Italico")
        self._chk_italic.setChecked(bool(data.get("italic", True)))
        fmt_row.addWidget(self._chk_italic)

        self._btn_color = QPushButton("Cor")
        self._btn_color.setFixedWidth(50)
        self._btn_color.setStyleSheet(
            f"background-color: {self._color}; color: white; border: 1px solid #333;"
        )
        self._btn_color.clicked.connect(self._pick_color)
        fmt_row.addWidget(self._btn_color)

        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        # Position selector
        pos_row = QHBoxLayout()
        pos_row.setSpacing(8)
        pos_row.addWidget(QLabel("Posicao:"))
        self._combo_position = QComboBox()
        for pos_key, pos_label, *_ in _COMMENT_POSITIONS:
            self._combo_position.addItem(pos_label, pos_key)
        current_pos = data.get("position", "bottom-left")
        pos_idx = next((i for i, (k, *_) in enumerate(_COMMENT_POSITIONS) if k == current_pos), 0)
        self._combo_position.setCurrentIndex(pos_idx)
        pos_row.addWidget(self._combo_position)
        pos_row.addStretch()
        layout.addLayout(pos_row)

        # Preview
        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        self._preview_label.setMinimumHeight(30)
        self._preview_label.setStyleSheet("border: 1px solid #ccc; padding: 4px; margin-top: 4px;")
        layout.addWidget(self._preview_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(self._clear_all)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        btn_apply = QPushButton("Apply")
        btn_apply.setToolTip("Aplicar no grafico sem fechar")
        btn_apply.clicked.connect(self._on_apply)
        btn_row.addWidget(btn_apply)
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        # Live preview connections
        self._text_edit.textChanged.connect(self._update_preview)
        self._spin_size.valueChanged.connect(self._update_preview)
        self._chk_bold.stateChanged.connect(self._update_preview)
        self._chk_italic.stateChanged.connect(self._update_preview)
        self._combo_position.currentIndexChanged.connect(self._update_preview)
        self._update_preview()

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Cor do comentario")
        if color.isValid():
            self._color = color.name()
            self._btn_color.setStyleSheet(
                f"background-color: {self._color}; color: white; border: 1px solid #333;"
            )
            self._update_preview()

    def _clear_all(self) -> None:
        self._text_edit.clear()

    def _on_apply(self) -> None:
        if self._apply_callback:
            self._apply_callback(self.get_data())

    def _update_preview(self) -> None:
        text = self._text_edit.toPlainText().strip() or "(vazio)"
        size = self._spin_size.value()
        bold = "font-weight: bold;" if self._chk_bold.isChecked() else ""
        italic = "font-style: italic;" if self._chk_italic.isChecked() else ""
        pos_label = self._combo_position.currentText()
        self._preview_label.setText(f"[{pos_label}] {text}")
        self._preview_label.setStyleSheet(
            f"border: 1px solid #ccc; padding: 4px; margin-top: 4px; "
            f"font-size: {size}px; {bold} {italic} color: {self._color};"
        )

    def get_data(self) -> Dict[str, Any]:
        return {
            "text": self._text_edit.toPlainText().strip(),
            "font_size": self._spin_size.value(),
            "bold": self._chk_bold.isChecked(),
            "italic": self._chk_italic.isChecked(),
            "color": self._color,
            "position": self._combo_position.currentData(),
        }


class SeriesStyleDialog(QDialog):
    """Dialog for customizing color and marker per detected series."""

    def __init__(self, series_keys: List[str], current_styles: Dict[str, Dict[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Series Colors & Markers")
        self.setMinimumWidth(420)
        self._styles: Dict[str, Dict[str, str]] = {}

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setSpacing(6)

        grid.addWidget(QLabel("Serie"), 0, 0)
        grid.addWidget(QLabel("Cor"), 0, 1)
        grid.addWidget(QLabel("Marker"), 0, 2)

        self._color_buttons: Dict[str, QPushButton] = {}
        self._marker_combos: Dict[str, QComboBox] = {}

        for row, key in enumerate(sorted(series_keys), start=1):
            existing = current_styles.get(key, {})
            color = existing.get("color", "#888888")
            marker = existing.get("marker", "o")

            lbl = QLabel(key)
            lbl.setToolTip(key)
            grid.addWidget(lbl, row, 0)

            btn_color = QPushButton("")
            btn_color.setFixedSize(32, 24)
            btn_color.setStyleSheet(f"background-color: {color}; border: 1px solid #333;")
            btn_color.setProperty("series_key", key)
            btn_color.setProperty("current_color", color)
            btn_color.clicked.connect(self._pick_color)
            grid.addWidget(btn_color, row, 1)
            self._color_buttons[key] = btn_color

            combo_marker = QComboBox()
            for m_code, m_label in _AVAILABLE_MARKERS:
                combo_marker.addItem(f"{m_label} ({m_code})", m_code)
            idx = next((i for i, (mc, _) in enumerate(_AVAILABLE_MARKERS) if mc == marker), 0)
            combo_marker.setCurrentIndex(idx)
            grid.addWidget(combo_marker, row, 2)
            self._marker_combos[key] = combo_marker

        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_reset = QPushButton("Reset (auto)")
        btn_reset.clicked.connect(self._reset_all)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _pick_color(self) -> None:
        btn = self.sender()
        key = btn.property("series_key")
        current = QColor(btn.property("current_color"))
        color = QColorDialog.getColor(current, self, f"Cor para {key}")
        if color.isValid():
            hex_color = color.name()
            btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #333;")
            btn.setProperty("current_color", hex_color)

    def _reset_all(self) -> None:
        self._styles = {}
        self.accept()

    def get_styles(self) -> Dict[str, Dict[str, str]]:
        """Return the configured styles. Empty dict means 'use auto'."""
        if not self._color_buttons:
            return {}
        result = {}
        for key, btn in self._color_buttons.items():
            color = btn.property("current_color")
            combo = self._marker_combos[key]
            marker = combo.currentData()
            result[key] = {"color": color, "marker": marker}
        return result


class PreviewPlotTab(QWidget):
    """Inline plot preview widget for the pipeline configuration GUI."""

    def __init__(
        self,
        get_preview_df: Callable[[], pd.DataFrame],
        get_plots_records: Callable[[], List[Dict[str, str]]],
        get_fuel_colors: Callable[[], Dict[str, str]],
        get_mappings: Callable[[], Dict[str, Any]],
        variable_catalog_provider: Callable[[], List[str]],
        status_callback: Callable[[str], None],
        apply_back_callback: Optional[Callable[[int, Dict[str, str]], None]] = None,
        save_config_callback: Optional[Callable[[], None]] = None,
        get_output_dir: Optional[Callable[[], Path]] = None,
        get_config_dir: Optional[Callable[[], Path]] = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._get_preview_df_fallback = get_preview_df
        self._get_plots_records = get_plots_records
        self._get_fuel_colors = get_fuel_colors
        self._get_mappings = get_mappings
        self._variable_catalog_provider = variable_catalog_provider
        self._show_status = status_callback
        self._apply_back_callback = apply_back_callback
        self._save_config_callback = save_config_callback
        self._get_output_dir = get_output_dir
        self._get_config_dir = get_config_dir

        self._current_fig: Optional[Figure] = None
        self._selected_plot_idx: int = -1
        self._loaded_df: Optional[pd.DataFrame] = None
        self._loaded_path: Optional[Path] = None
        self._draft_overrides: Dict[int, Dict[str, str]] = {}
        self._series_style_overrides: Dict[str, Dict[str, str]] = {}
        self._last_y_col: str = ""
        self._exclusion_mode_active: bool = False
        self._pending_pick_key = None
        self._pending_picks: List[Dict[str, Any]] = []
        self._highlight_artists: List = []
        self._cursor_mode_active: bool = False
        self._cursor_line = None
        self._cursor_arrow = None
        self._compare_comment_data: Dict[str, Any] = _empty_comment_data()
        self._cursor_x: float = 0.0
        self._compare_df: Optional[pd.DataFrame] = None
        self._compare_path: Optional[Path] = None

        # Hover tooltip
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(600)
        self._hover_timer.timeout.connect(self._show_hover_tooltip)
        self._hover_last_event = None
        self._hover_tooltip: Optional[QLabel] = None

        # Raw / Excl toggle data sources
        self._raw_path: Optional[Path] = None
        self._raw_df: Optional[pd.DataFrame] = None
        self._excl_path: Optional[Path] = None
        self._excl_df: Optional[pd.DataFrame] = None
        self._active_source: str = "raw"   # "raw" | "excl"

        # Unified session state -- persisted as preview_workspace.json
        self._session: Dict[str, Any] = {
            "data_source": {"path": "", "compare_path": "",
                            "raw_path": "", "excl_path": "", "active_source": "raw"},
            "axis": {"x_col": "Load_kW", "x_label": "", "x_min": "", "x_max": "", "x_step": ""},
            "y_scales": {},
            "comments": {},
            "series_styles": {},
            "display": {"cursor_font_size": 15, "filter_h2o_list": "", "label_variant": "tag", "lock_x": False, "series_col": ""},
            "compare": {"active_metric": ""},
            "active_mode": "all_iterations_yx",
        }

        self._populating = False

        self._setup_ui()

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._render_preview)

        self._debounce_timer_slow = QTimer(self)
        self._debounce_timer_slow.setSingleShot(True)
        self._debounce_timer_slow.setInterval(700)
        self._debounce_timer_slow.timeout.connect(self._render_preview)

        self._connect_signals()
        self._load_workspace()
        self._restore_session_to_ui()

        self.installEventFilter(self)
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(6, 6, 6, 6)
        outer_layout.setSpacing(4)

        # -- Top bar: data source indicator + browse --
        data_bar = QHBoxLayout()
        data_bar.setSpacing(6)
        self.lbl_data_source = QLabel("Dados: (nenhum carregado)")
        self.lbl_data_source.setStyleSheet("color: #666; font-size: 11px;")
        self.lbl_data_source.setWordWrap(True)
        data_bar.addWidget(self.lbl_data_source, 1)
        self.btn_browse_data = QPushButton("Browse...")
        self.btn_browse_data.setFixedWidth(80)
        self.btn_browse_data.setToolTip("Carregar outro lv_kpis_clean.xlsx")
        data_bar.addWidget(self.btn_browse_data)
        self.btn_reload_data = QPushButton("Reload")
        self.btn_reload_data.setFixedWidth(60)
        self.btn_reload_data.setToolTip("Recarregar do mesmo arquivo")
        data_bar.addWidget(self.btn_reload_data)
        self.btn_series_colors = QPushButton("Series Colors...")
        self.btn_series_colors.setFixedWidth(110)
        self.btn_series_colors.setToolTip(
            "Customizar cor e marker de cada serie detectada no DataFrame"
        )
        data_bar.addWidget(self.btn_series_colors)
        self.btn_excl_mode = QPushButton("Dataset Filter")
        self.btn_excl_mode.setFixedWidth(110)
        self.btn_excl_mode.setCheckable(True)
        self.btn_excl_mode.setToolTip(
            "Left-click: excluir ponto individual\n"
            "Right-click: excluir serie inteira"
        )
        data_bar.addWidget(self.btn_excl_mode)
        self.btn_view_exclusions = QPushButton("Exclusions...")
        self.btn_view_exclusions.setFixedWidth(90)
        self.btn_view_exclusions.setToolTip("Revisar e restaurar pontos excluidos")
        data_bar.addWidget(self.btn_view_exclusions)
        self.btn_cursor = QPushButton("Cursor")
        self.btn_cursor.setFixedWidth(65)
        self.btn_cursor.setCheckable(True)
        self.btn_cursor.setToolTip("Cursor vertical: arraste para ler valores interpolados de cada serie")
        data_bar.addWidget(self.btn_cursor)
        self.edit_cursor_font = QLineEdit("11")
        self.edit_cursor_font.setFixedWidth(28)
        self.edit_cursor_font.setToolTip("Tamanho da fonte da tabela cursor (px)")
        self.edit_cursor_font.setVisible(False)
        data_bar.addWidget(self.edit_cursor_font)
        self.btn_comment = QPushButton("Comment...")
        self.btn_comment.setFixedWidth(90)
        self.btn_comment.setToolTip("Editar comentario com formatacao (aparece no grafico)")
        data_bar.addWidget(self.btn_comment)
        outer_layout.addLayout(data_bar)

        # -- Raw / Excl toggle bar --
        rawexcl_bar = QHBoxLayout()
        rawexcl_bar.setSpacing(4)
        # Raw side
        self.lbl_raw_data = QLabel("Raw: (nenhum)")
        self.lbl_raw_data.setStyleSheet("color: #66aaff; font-size: 10px;")
        self.lbl_raw_data.setWordWrap(False)
        rawexcl_bar.addWidget(self.lbl_raw_data, 1)
        self.btn_browse_raw = QPushButton("Browse Raw")
        self.btn_browse_raw.setFixedWidth(90)
        self.btn_browse_raw.setToolTip("Carregar arquivo RAW (sem exclusoes) para comparacao")
        rawexcl_bar.addWidget(self.btn_browse_raw)
        self.btn_reload_raw = QPushButton("↺")
        self.btn_reload_raw.setFixedWidth(24)
        self.btn_reload_raw.setToolTip("Recarregar arquivo raw")
        rawexcl_bar.addWidget(self.btn_reload_raw)
        # Separator
        sep_lbl = QLabel("|")
        sep_lbl.setStyleSheet("color: #555; font-size: 12px;")
        rawexcl_bar.addWidget(sep_lbl)
        # Excl side
        self.lbl_excl_data = QLabel("Excl: (nenhum)")
        self.lbl_excl_data.setStyleSheet("color: #ffaa44; font-size: 10px;")
        self.lbl_excl_data.setWordWrap(False)
        rawexcl_bar.addWidget(self.lbl_excl_data, 1)
        self.btn_browse_excl = QPushButton("Browse Excl")
        self.btn_browse_excl.setFixedWidth(90)
        self.btn_browse_excl.setToolTip("Carregar arquivo pos-exclusao para comparacao")
        rawexcl_bar.addWidget(self.btn_browse_excl)
        self.btn_reload_excl = QPushButton("↺")
        self.btn_reload_excl.setFixedWidth(24)
        self.btn_reload_excl.setToolTip("Recarregar arquivo excl")
        rawexcl_bar.addWidget(self.btn_reload_excl)
        # Toggle combo
        self.combo_active_source = QComboBox()
        self.combo_active_source.addItems(["raw", "excl"])
        self.combo_active_source.setFixedWidth(60)
        self.combo_active_source.setToolTip(
            "Toggle entre arquivo Raw e arquivo Excl.\n"
            "Raw = dados originais (com series excluidas).\n"
            "Excl = dados pos-processamento com exclusion list."
        )
        rawexcl_bar.addWidget(QLabel("Ativo:"))
        rawexcl_bar.addWidget(self.combo_active_source)
        outer_layout.addLayout(rawexcl_bar)

        # -- Main split panel --
        main_layout = QHBoxLayout()
        main_layout.setSpacing(8)

        # -- Left panel (controls) --
        left_container = QWidget()
        left_container.setMinimumWidth(280)
        left_form = QFormLayout(left_container)
        left_form.setContentsMargins(4, 4, 4, 4)
        left_form.setSpacing(6)

        self.combo_plot_selector = QComboBox()
        left_form.addRow("Plot:", self.combo_plot_selector)

        self.edit_title = QLineEdit()
        left_form.addRow("Title:", self.edit_title)

        self.combo_plot_type = QComboBox()
        self.combo_plot_type.addItems([
            "all_fuels_yx",
            "all_fuels_xy",
            "all_fuels_labels",
            "all_fuels_delta_ref",
            "all_iterations_yx",
            "compare_bl_vs_adtv",
            "kibox_all",
        ])
        left_form.addRow("Plot type:", self.combo_plot_type)

        self.edit_x_col = QLineEdit()
        self._completer_x = QCompleter([], self)
        self._completer_x.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer_x.setFilterMode(Qt.MatchContains)
        self.edit_x_col.setCompleter(self._completer_x)
        left_form.addRow("X col:", self.edit_x_col)

        self.edit_y_col = QLineEdit()
        self._completer_y = QCompleter([], self)
        self._completer_y.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer_y.setFilterMode(Qt.MatchContains)
        self.edit_y_col.setCompleter(self._completer_y)
        left_form.addRow("Y col:", self.edit_y_col)

        self.combo_y_browse = QComboBox()
        self.combo_y_browse.setToolTip("Selecionar qualquer coluna numerica do DataFrame como Y")
        self.combo_y_browse.addItem("(browse columns...)")
        left_form.addRow("Y browse:", self.combo_y_browse)

        self.edit_yerr_col = QLineEdit()
        self._completer_yerr = QCompleter([], self)
        self._completer_yerr.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer_yerr.setFilterMode(Qt.MatchContains)
        self.edit_yerr_col.setCompleter(self._completer_yerr)
        left_form.addRow("Yerr col:", self.edit_yerr_col)

        self.chk_show_uncertainty = QCheckBox("Show uncertainty bars")
        self.chk_show_uncertainty.setChecked(True)
        left_form.addRow("", self.chk_show_uncertainty)

        self.combo_compare_metric = QComboBox()
        self.combo_compare_metric.setVisible(False)
        left_form.addRow("Metrica:", self.combo_compare_metric)

        self.combo_compare_pair = QComboBox()
        self.combo_compare_pair.setVisible(False)
        left_form.addRow("Comparacao:", self.combo_compare_pair)


        self.edit_x_label = QLineEdit()
        left_form.addRow("X label:", self.edit_x_label)

        self.edit_y_label = QLineEdit()
        left_form.addRow("Y label:", self.edit_y_label)

        # X axis row
        x_axis_row = QHBoxLayout()
        self.edit_x_min = QLineEdit()
        self.edit_x_min.setPlaceholderText("min")
        self.edit_x_max = QLineEdit()
        self.edit_x_max.setPlaceholderText("max")
        self.edit_x_step = QLineEdit()
        self.edit_x_step.setPlaceholderText("step")
        x_axis_row.addWidget(self.edit_x_min)
        x_axis_row.addWidget(self.edit_x_max)
        x_axis_row.addWidget(self.edit_x_step)
        x_axis_widget = QWidget()
        x_axis_widget.setLayout(x_axis_row)
        left_form.addRow("X min/max/step:", x_axis_widget)

        self.chk_lock_x = QCheckBox("Lock X axis (keep across plots)")
        self.chk_lock_x.setToolTip(
            "Quando ativo, X col / X label / X scale / Series col\n"
            "nao mudam ao navegar entre plots."
        )
        left_form.addRow("", self.chk_lock_x)

        # X Preset (builtin templates only)
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        self.combo_preset = QComboBox()
        self.combo_preset.setMinimumWidth(140)
        self.combo_preset.setToolTip("Selecionar template de eixo X")
        self.combo_preset.addItem("(nenhum)")
        for name in _BUILTIN_PRESETS:
            self.combo_preset.addItem(name)
        preset_row.addWidget(self.combo_preset, 1)
        preset_widget = QWidget()
        preset_widget.setLayout(preset_row)
        left_form.addRow("X Preset:", preset_widget)

        # Y axis row
        y_axis_row = QHBoxLayout()
        self.edit_y_min = QLineEdit()
        self.edit_y_min.setPlaceholderText("min")
        self.edit_y_max = QLineEdit()
        self.edit_y_max.setPlaceholderText("max")
        self.edit_y_step = QLineEdit()
        self.edit_y_step.setPlaceholderText("step")
        y_axis_row.addWidget(self.edit_y_min)
        y_axis_row.addWidget(self.edit_y_max)
        y_axis_row.addWidget(self.edit_y_step)
        y_axis_widget = QWidget()
        y_axis_widget.setLayout(y_axis_row)
        left_form.addRow("Y min/max/step:", y_axis_widget)

        # Y tolerance row
        tol_row = QHBoxLayout()
        self.edit_y_tol_plus = QLineEdit()
        self.edit_y_tol_plus.setPlaceholderText("tol+")
        self.edit_y_tol_minus = QLineEdit()
        self.edit_y_tol_minus.setPlaceholderText("tol-")
        tol_row.addWidget(self.edit_y_tol_plus)
        tol_row.addWidget(self.edit_y_tol_minus)
        tol_widget = QWidget()
        tol_widget.setLayout(tol_row)
        left_form.addRow("Y tol+/tol-:", tol_widget)

        self.edit_filter_h2o = QLineEdit()
        self.edit_filter_h2o.setPlaceholderText("0,6,25,35")
        self.edit_filter_h2o.setVisible(False)

        self.edit_series_col = QLineEdit()
        self.edit_series_col.setPlaceholderText("(vazio = agrupar por fuel)")
        self._completer_series = QCompleter([], self)
        self._completer_series.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer_series.setFilterMode(Qt.MatchContains)
        self.edit_series_col.setCompleter(self._completer_series)
        self.edit_series_col.setVisible(False)

        self.combo_label_variant = QComboBox()
        self.combo_label_variant.addItems(["box", "tag", "marker", "badge"])
        self.combo_label_variant.setVisible(False)

        # Action buttons
        btn_row1 = QHBoxLayout()
        self.btn_copy = QPushButton("Copy to Clipboard")
        self.btn_export_plot = QPushButton("Export Plot PNG")
        btn_row1.addWidget(self.btn_copy)
        btn_row1.addWidget(self.btn_export_plot)
        btn_widget1 = QWidget()
        btn_widget1.setLayout(btn_row1)
        left_form.addRow(btn_widget1)

        btn_row2 = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_save.setToolTip("Salvar workspace inteiro (preview_workspace.json)")
        self.btn_save_as = QPushButton("Save As...")
        self.btn_save_as.setToolTip("Salvar workspace em outro arquivo")
        self.btn_export_all = QPushButton("Export All Plots")
        btn_row2.addWidget(self.btn_save)
        btn_row2.addWidget(self.btn_save_as)
        btn_row2.addWidget(self.btn_export_all)
        btn_widget2 = QWidget()
        btn_widget2.setLayout(btn_row2)
        left_form.addRow(btn_widget2)

        # Saved workspaces list
        lbl_ws = QLabel("Workspaces salvos:")
        lbl_ws.setStyleSheet("font-weight: bold; margin-top: 8px; font-size: 10px;")
        left_form.addRow(lbl_ws)
        self.list_workspaces = QListWidget()
        self.list_workspaces.setMinimumHeight(120)
        self.list_workspaces.setToolTip("Duplo-clique para carregar um workspace salvo")
        left_form.addRow(self.list_workspaces)

        # Wrap left panel in scroll area
        scroll = QScrollArea()
        scroll.setWidget(left_container)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(280)
        scroll.setMaximumWidth(420)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # -- Right panel (canvas left + cursor table right) --
        self._right_panel = QVBoxLayout()
        self._right_panel.setContentsMargins(0, 0, 0, 0)

        self._placeholder_label = QLabel("Aguardando dados...")
        self._placeholder_label.setAlignment(Qt.AlignCenter)
        self._placeholder_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._right_panel.addWidget(self._placeholder_label)

        self._canvas: Optional[FigureCanvasQTAgg] = None

        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self._cursor_table = QTableWidget()
        self._cursor_table.setColumnCount(2)
        self._cursor_table.setHorizontalHeaderLabels(["Serie", "Valor"])
        self._cursor_table.setVisible(False)
        self._cursor_table.setMinimumWidth(180)
        self._cursor_table.setMaximumWidth(320)
        self._cursor_table.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._cursor_table.verticalHeader().setVisible(False)
        self._cursor_table.verticalHeader().setDefaultSectionSize(22)
        self._cursor_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._cursor_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._apply_cursor_font_size()

        right_widget = QWidget()
        right_inner = QHBoxLayout(right_widget)
        right_inner.setContentsMargins(0, 0, 0, 0)
        right_inner.setSpacing(4)

        self._canvas_container = QWidget()
        self._canvas_container.setLayout(self._right_panel)
        self._canvas_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_inner.addWidget(self._canvas_container, 1)
        right_inner.addWidget(self._cursor_table, 0)

        # -- Thumbnail strip (between controls and canvas) --
        self._thumb_strip = QScrollArea()
        self._thumb_strip.setWidgetResizable(True)
        self._thumb_strip.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._thumb_strip.setFixedWidth(180)
        self._thumb_container = QWidget()
        self._thumb_layout = QVBoxLayout(self._thumb_container)
        self._thumb_layout.setContentsMargins(4, 4, 4, 4)
        self._thumb_layout.setSpacing(4)
        self._thumb_strip.setWidget(self._thumb_container)

        # Splitter: drag to resize left/middle/right panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(self._thumb_strip)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([380, 180, 900])

        main_layout.addWidget(splitter)
        outer_layout.addLayout(main_layout, 1)

        # -- Progress bar (hidden by default, shown during export) --
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedHeight(18)
        outer_layout.addWidget(self._progress_bar)

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        line_edits_fast = [
            self.edit_title, self.edit_x_col, self.edit_y_col,
            self.edit_yerr_col, self.edit_x_label, self.edit_y_label,
            self.edit_x_min, self.edit_x_max,
            self.edit_y_min, self.edit_y_max,
            self.edit_y_tol_plus, self.edit_y_tol_minus, self.edit_filter_h2o,
            self.edit_series_col,
        ]
        for le in line_edits_fast:
            le.textChanged.connect(self._schedule_render)

        line_edits_slow = [self.edit_x_step, self.edit_y_step]
        for le in line_edits_slow:
            le.textChanged.connect(self._schedule_render_slow)

        for le in [self.edit_y_min, self.edit_y_max, self.edit_y_step]:
            le.editingFinished.connect(self._on_y_scale_edited)

        self.edit_x_col.editingFinished.connect(self._on_axis_col_changed)
        self.edit_y_col.editingFinished.connect(self._on_axis_col_changed)
        self._completer_x.activated.connect(self._on_axis_col_changed)
        self._completer_y.activated.connect(self._on_axis_col_changed)

        self.combo_plot_type.currentIndexChanged.connect(self._schedule_render)
        self.combo_label_variant.currentIndexChanged.connect(self._schedule_render)
        self.chk_show_uncertainty.stateChanged.connect(self._schedule_render)
        self.combo_plot_selector.currentIndexChanged.connect(self._on_plot_selected)

        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_export_plot.clicked.connect(self._export_current_plot)
        self.btn_export_all.clicked.connect(self._export_all_plots)
        self.btn_browse_data.clicked.connect(self._browse_data_file)
        self.btn_reload_data.clicked.connect(self._reload_data)

        self.btn_save.clicked.connect(self._save_workspace)
        self.btn_save_as.clicked.connect(self._save_workspace_as)
        self.list_workspaces.itemDoubleClicked.connect(self._on_workspace_double_click)
        self.combo_preset.currentIndexChanged.connect(self._on_preset_selected)
        self.btn_series_colors.clicked.connect(self._open_series_colors_dialog)
        self.btn_excl_mode.toggled.connect(self._on_exclusion_mode_toggled)
        self.btn_view_exclusions.clicked.connect(self._open_exclusions_review)
        self.btn_browse_raw.clicked.connect(self._browse_raw_file)
        self.btn_reload_raw.clicked.connect(self._reload_raw_data)
        self.btn_browse_excl.clicked.connect(self._browse_excl_file)
        self.btn_reload_excl.clicked.connect(self._reload_excl_data)
        self.combo_active_source.currentTextChanged.connect(self._on_active_source_changed)
        self.btn_cursor.toggled.connect(self._on_cursor_mode_toggled)
        self.edit_cursor_font.editingFinished.connect(self._on_cursor_font_changed)
        self.combo_y_browse.currentIndexChanged.connect(self._on_y_browse_selected)
        self.combo_compare_metric.currentIndexChanged.connect(self._on_compare_metric_changed)
        self.combo_compare_pair.currentIndexChanged.connect(self._schedule_render)
        self.btn_comment.clicked.connect(self._open_comment_dialog)
        self.combo_plot_type.currentTextChanged.connect(self._on_plot_type_changed)

    def _schedule_render(self) -> None:
        if self._populating:
            return
        self._debounce_timer.start()

    def _schedule_render_slow(self) -> None:
        if self._populating:
            return
        self._debounce_timer_slow.start()

    def _on_y_scale_edited(self) -> None:
        if self._populating:
            return
        y_key = self._current_y_scale_key()
        if y_key:
            self._session["y_scales"][y_key] = {
                "y_min": self.edit_y_min.text().strip(),
                "y_max": self.edit_y_max.text().strip(),
                "y_step": self.edit_y_step.text().strip(),
            }

    def _on_axis_col_changed(self) -> None:
        if self._populating:
            return
        x_col = self.edit_x_col.text().strip()
        y_col = self.edit_y_col.text().strip()
        if x_col:
            self.edit_x_label.setText(x_col)
        if y_col:
            self.edit_y_label.setText(y_col)
        self._sync_current_to_plots_table()

    def _sync_current_to_plots_table(self) -> None:
        if self._apply_back_callback is None or self._selected_plot_idx < 0:
            return
        values = {
            "x_col": self.edit_x_col.text().strip(),
            "y_col": self.edit_y_col.text().strip(),
            "x_label": self.edit_x_label.text().strip(),
            "y_label": self.edit_y_label.text().strip(),
            "title": self.edit_title.text().strip(),
            "plot_type": self.combo_plot_type.currentText(),
        }
        self._apply_back_callback(self._selected_plot_idx, values)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key_Right:
                self._navigate_next_plot()
                return True
            elif key == Qt.Key_Left:
                self._navigate_prev_plot()
                return True
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                if self._exclusion_mode_active and hasattr(self, "_pending_picks") and self._pending_picks:
                    self._confirm_pending_exclusions()
                    return True
            elif key == Qt.Key_Escape:
                if self._exclusion_mode_active and hasattr(self, "_pending_picks") and self._pending_picks:
                    self._clear_pick_highlight()
                    self._pending_picks = []
                    self._show_status("Selecao limpa.")
                    return True
        elif event.type() == QEvent.Type.Wheel:
            if self._canvas is not None and (
                obj is self._canvas or obj in self._canvas.findChildren(QWidget)
            ):
                delta = event.angleDelta().y()
                if delta > 0:
                    self._navigate_prev_plot()
                elif delta < 0:
                    self._navigate_next_plot()
                return True
            if obj is self._thumb_strip or (
                hasattr(self, "_thumb_container") and obj is self._thumb_container
            ):
                delta = event.angleDelta().y()
                if delta > 0:
                    self._navigate_prev_plot()
                elif delta < 0:
                    self._navigate_next_plot()
                return True
        return super().eventFilter(obj, event)

    def _capture_current_controls(self) -> Dict[str, str]:
        """Snapshot current control values into a dict."""
        return {
            "title": self.edit_title.text(),
            "plot_type": self.combo_plot_type.currentText(),
            "x_col": self.edit_x_col.text(),
            "y_col": self.edit_y_col.text(),
            "yerr_col": self.edit_yerr_col.text(),
            "show_uncertainty": "1" if self.chk_show_uncertainty.isChecked() else "0",
            "x_label": self.edit_x_label.text(),
            "y_label": self.edit_y_label.text(),
            "x_min": self.edit_x_min.text(),
            "x_max": self.edit_x_max.text(),
            "x_step": self.edit_x_step.text(),
            "y_min": self.edit_y_min.text(),
            "y_max": self.edit_y_max.text(),
            "y_step": self.edit_y_step.text(),
            "y_tol_plus": self.edit_y_tol_plus.text(),
            "y_tol_minus": self.edit_y_tol_minus.text(),
            "filter_h2o_list": self.edit_filter_h2o.text(),
            "series_col": self.edit_series_col.text(),
            "label_variant": self.combo_label_variant.currentText(),
        }

    def _save_draft(self) -> None:
        """Save current edits as draft for the active plot index."""
        if self._selected_plot_idx >= 0:
            self._draft_overrides[self._selected_plot_idx] = self._capture_current_controls()

    def _get_effective_record(self, index: int) -> Dict[str, str]:
        """Return draft if available, otherwise the original config record."""
        if index in self._draft_overrides:
            return self._draft_overrides[index]
        records = self._get_plots_records()
        if index < len(records):
            return records[index]
        return {}

    def _on_plot_selected(self, index: int) -> None:
        if index < 0 or self._populating:
            return
        self._save_draft()
        self._selected_plot_idx = index
        self._populate_from_record(self._get_effective_record(index))

    def _navigate_next_plot(self) -> None:
        if self.combo_plot_type.currentText() == "compare_bl_vs_adtv":
            cnt = self.combo_compare_metric.count()
            if cnt > 0:
                nxt = (self.combo_compare_metric.currentIndex() + 1) % cnt
                self.combo_compare_metric.setCurrentIndex(nxt)
            return
        count = self.combo_plot_selector.count()
        if count == 0:
            return
        nxt = (self._selected_plot_idx + 1) % count
        self.combo_plot_selector.setCurrentIndex(nxt)

    def _navigate_prev_plot(self) -> None:
        if self.combo_plot_type.currentText() == "compare_bl_vs_adtv":
            cnt = self.combo_compare_metric.count()
            if cnt > 0:
                prev = (self.combo_compare_metric.currentIndex() - 1) % cnt
                self.combo_compare_metric.setCurrentIndex(prev)
            return
        count = self.combo_plot_selector.count()
        if count == 0:
            return
        prev = (self._selected_plot_idx - 1) % count
        self.combo_plot_selector.setCurrentIndex(prev)

    # ------------------------------------------------------------------
    # Thumbnail strip
    # ------------------------------------------------------------------

    def _refresh_thumbnails(self) -> None:
        """Rebuild or update thumbnail strip. Only rebuilds if items changed."""
        if self.combo_plot_type.currentText() == "compare_bl_vs_adtv":
            items = [self.combo_compare_metric.itemText(i)
                     for i in range(self.combo_compare_metric.count())]
            active_idx = self.combo_compare_metric.currentIndex()
        else:
            items = [self.combo_plot_selector.itemText(i)
                     for i in range(self.combo_plot_selector.count())]
            active_idx = self._selected_plot_idx

        if not hasattr(self, "_thumb_cache"):
            self._thumb_cache: Dict[str, QImage] = {}
        if not hasattr(self, "_thumb_items_snapshot"):
            self._thumb_items_snapshot: List[str] = []

        # Only rebuild widgets if items list changed
        if items != self._thumb_items_snapshot:
            self._thumb_items_snapshot = list(items)
            while self._thumb_layout.count():
                item = self._thumb_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for i, label in enumerate(items):
                thumb = self._make_thumbnail(i, label, is_active=(i == active_idx))
                self._thumb_layout.addWidget(thumb)
            self._thumb_layout.addStretch()

            # Start lazy rendering for uncached thumbnails
            needs_render = [l for l in items if l not in self._thumb_cache]
            if needs_render:
                self._thumb_render_queue = needs_render
                if not hasattr(self, "_thumb_render_timer"):
                    self._thumb_render_timer = QTimer(self)
                    self._thumb_render_timer.setSingleShot(True)
                    self._thumb_render_timer.timeout.connect(self._render_next_thumbnail)
                self._thumb_render_timer.start(80)
        else:
            # Just update active highlight (fast path)
            self._update_thumb_highlight(active_idx)

    def _update_thumb_highlight(self, active_idx: int) -> None:
        """Update only the border highlight without rebuilding widgets."""
        for i in range(self._thumb_layout.count()):
            item = self._thumb_layout.itemAt(i)
            if not item or not item.widget():
                continue
            w = item.widget()
            is_active = (i == active_idx)
            border = "2px solid #4fc3f7" if is_active else "1px solid #555"
            w.setStyleSheet(
                f"QWidget {{ border: {border}; border-radius: 4px; padding: 2px; }}"
            )
        # Scroll to make active visible
        if active_idx >= 0:
            item = self._thumb_layout.itemAt(active_idx)
            if item and item.widget():
                self._thumb_strip.ensureWidgetVisible(item.widget(), 0, 50)

    def _render_next_thumbnail(self) -> None:
        """Render ONE thumbnail per timer tick (non-blocking)."""
        if not hasattr(self, "_thumb_render_queue") or not self._thumb_render_queue:
            return
        label = self._thumb_render_queue.pop(0)
        img = self._render_mini_figure_for(label)
        if img and not img.isNull():
            self._thumb_cache[label] = img
            self._update_thumbnail_image(label, img)
        # Schedule next if queue has more
        if self._thumb_render_queue:
            self._thumb_render_timer.start(30)

    def _render_mini_figure_for(self, label: str) -> Optional[QImage]:
        """Render a high-quality mini-figure for one metric/plot (lines only, no markers)."""
        try:
            if self.combo_plot_type.currentText() == "compare_bl_vs_adtv":
                if self._compare_df is None or self._compare_df.empty:
                    return None
                from ..runtime.compare_iteracoes.preview_renderers import render_compare_delta_all_overlay
                fig = render_compare_delta_all_overlay(
                    self._compare_df, metrica=label, include_uncertainty=False,
                )
            else:
                return None

            if fig is None:
                return None

            fig.set_size_inches(2.4, 1.5)
            ax = fig.gca()
            ax.set_title("")
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.tick_params(labelsize=0, length=0)
            ax.set_xticklabels([])
            ax.set_yticklabels([])
            for line in ax.get_lines():
                line.set_marker("")
                line.set_linewidth(1.5)
            for container in ax.containers:
                try:
                    for child in container:
                        child.set_visible(False)
                except (TypeError, AttributeError):
                    pass
            legend = ax.get_legend()
            if legend:
                legend.remove()
            fig.tight_layout(pad=0.1)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150,
                        facecolor="#1e1e1e", edgecolor="none", bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            img = QImage()
            img.loadFromData(buf.read())
            return img
        except Exception:
            return None

    def _update_thumbnail_image(self, label: str, img: QImage) -> None:
        """Update a specific thumbnail's image label in the strip."""
        from PySide6.QtGui import QPixmap
        for i in range(self._thumb_layout.count()):
            item = self._thumb_layout.itemAt(i)
            if not item or not item.widget():
                continue
            w = item.widget()
            if w.property("thumb_label") == label:
                img_lbl = w.findChild(QLabel, "thumb_img")
                if img_lbl:
                    pixmap = QPixmap.fromImage(img).scaled(
                        170, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    img_lbl.setPixmap(pixmap)
                break

    def _make_thumbnail(self, index: int, label: str, is_active: bool) -> QWidget:
        """Create a clickable thumbnail widget (image loaded from cache or lazily)."""
        frame = QWidget()
        frame.setFixedHeight(135)
        frame.setCursor(Qt.PointingHandCursor)
        frame.setProperty("thumb_label", label)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        # Image area
        img_label = QLabel()
        img_label.setObjectName("thumb_img")
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setMinimumHeight(100)
        img_label.setStyleSheet("background-color: #1e1e1e; border-radius: 3px;")

        # Use cached image if available
        if hasattr(self, "_thumb_cache") and label in self._thumb_cache:
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap.fromImage(self._thumb_cache[label]).scaled(
                170, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            img_label.setPixmap(pixmap)
        else:
            img_label.setText("...")
            img_label.setStyleSheet(
                "background-color: #1e1e1e; border-radius: 3px; color: #555; font-size: 10px;"
            )

        layout.addWidget(img_label)

        # Label below
        lbl = QLabel(label[:30])
        lbl.setStyleSheet("font-size: 11px; color: #ccc; border: none;")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        # Border for active
        border = "2px solid #4fc3f7" if is_active else "1px solid #555"
        frame.setStyleSheet(
            f"QWidget {{ border: {border}; border-radius: 4px; padding: 2px; }}"
        )

        frame.mousePressEvent = lambda ev, idx=index: self._on_thumbnail_clicked(idx)
        return frame

    def _on_thumbnail_clicked(self, index: int) -> None:
        """Navigate to the plot at the given index."""
        if self.combo_plot_type.currentText() == "compare_bl_vs_adtv":
            if index < self.combo_compare_metric.count():
                self.combo_compare_metric.setCurrentIndex(index)
        else:
            if index < self.combo_plot_selector.count():
                self.combo_plot_selector.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Data management
    # ------------------------------------------------------------------

    def _get_effective_df(self) -> pd.DataFrame:
        """Return the active DataFrame based on raw/excl toggle or fallback."""
        if self._active_source == "raw":
            if self._raw_df is None and self._raw_path is not None and self._raw_path.exists():
                self._load_raw_excl_file(self._raw_path, "raw")
            if self._raw_df is not None and not self._raw_df.empty:
                return self._raw_df
        if self._active_source == "excl":
            if self._excl_df is None and self._excl_path is not None and self._excl_path.exists():
                self._load_raw_excl_file(self._excl_path, "excl")
            if self._excl_df is not None and not self._excl_df.empty:
                return self._excl_df
        if self._loaded_df is None and self._loaded_path is not None and self._loaded_path.exists():
            self.load_data_from_file(self._loaded_path)
        if self._loaded_df is not None and not self._loaded_df.empty:
            return self._loaded_df
        return self._get_preview_df_fallback()

    def _refresh_column_completers(self) -> None:
        df = self._get_effective_df()
        if df is None or df.empty:
            return
        cols = sorted([str(c) for c in df.columns], key=str.lower)
        for completer in (self._completer_x, self._completer_y, self._completer_yerr, self._completer_series):
            model = completer.model()
            if isinstance(model, QStringListModel):
                model.setStringList(cols)
            else:
                completer.setModel(QStringListModel(cols))
        self._refresh_y_browse_combo()

    def load_data_from_file(self, path: Path) -> bool:
        """Load a lv_kpis_clean.xlsx and update the indicator.

        If the file contains a 'compare' sheet with Metrica/Comparacao columns
        (embedded by the pipeline since the compare unification feature), it is
        automatically loaded into _compare_df — no separate Browse required.
        """
        try:
            df = pd.read_excel(path, sheet_name=0, engine="calamine")
            self._loaded_df = df
            self._loaded_path = path
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
            self.lbl_data_source.setText(
                f"Dados: {path.name} | {df.shape[0]} rows x {df.shape[1]} cols | {mtime}\n"
                f"{path.parent}"
            )
            self._refresh_column_completers()
            # Auto-detect embedded 'compare' sheet (written by compute_compare_iteracoes)
            try:
                df_cmp = pd.read_excel(path, sheet_name="compare", engine="calamine")
                if "Metrica" in df_cmp.columns and "Comparacao" in df_cmp.columns:
                    self._load_compare_from_df(df_cmp, path)
                    self._show_status(
                        f"Preview data loaded: {path.name} ({df.shape[0]}x{df.shape[1]}) "
                        f"+ compare sheet ({len(df_cmp)} rows)"
                    )
                    return True
            except Exception:
                pass  # No compare sheet — that's fine
            self._show_status(f"Preview data loaded: {path.name} ({df.shape[0]}x{df.shape[1]})")
            return True
        except Exception as e:
            self._show_status(f"Erro ao carregar: {e}")
            return False

    # ------------------------------------------------------------------
    # Raw / Excl data sources
    # ------------------------------------------------------------------

    def _load_raw_excl_file(self, path: Path, target: str) -> bool:
        """Load a file into _raw_df or _excl_df depending on target ('raw'|'excl').

        Also auto-detects the embedded 'compare' sheet so that loading the excl
        file updates the compare mode in the same step.
        """
        try:
            df = pd.read_excel(path, sheet_name=0, engine="calamine")
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
            shape_txt = f"{df.shape[0]}r×{df.shape[1]}c"
            if target == "raw":
                self._raw_df = df
                self._raw_path = path
                self.lbl_raw_data.setText(f"Raw: {path.name}  {shape_txt}  {mtime}")
            else:
                self._excl_df = df
                self._excl_path = path
                self.lbl_excl_data.setText(f"Excl: {path.name}  {shape_txt}  {mtime}")
            # Auto-detect compare sheet (embedded by compute_compare_iteracoes)
            try:
                df_cmp = pd.read_excel(path, sheet_name="compare", engine="calamine")
                if "Metrica" in df_cmp.columns and "Comparacao" in df_cmp.columns:
                    self._load_compare_from_df(df_cmp, path)
            except Exception:
                pass
            self._refresh_column_completers()
            self._show_status(f"{target.capitalize()} data loaded: {path.name} ({df.shape[0]}x{df.shape[1]})")
            return True
        except Exception as e:
            self._show_status(f"Erro ao carregar {target}: {e}")
            return False

    def _browse_raw_file(self) -> None:
        start = str(self._raw_path.parent) if self._raw_path else (
            str(self._loaded_path.parent) if self._loaded_path else "")
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo Raw (sem exclusoes)", start,
            "Excel files (*.xlsx);;All files (*)"
        )
        if path:
            self._load_raw_excl_file(Path(path), "raw")
            self._schedule_render()

    def _reload_raw_data(self) -> None:
        if self._raw_path and self._raw_path.exists():
            self._load_raw_excl_file(self._raw_path, "raw")
            self._schedule_render()

    def _browse_excl_file(self) -> None:
        start = str(self._excl_path.parent) if self._excl_path else (
            str(self._raw_path.parent) if self._raw_path else (
                str(self._loaded_path.parent) if self._loaded_path else ""))
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo pos-exclusao", start,
            "Excel files (*.xlsx);;All files (*)"
        )
        if path:
            self._load_raw_excl_file(Path(path), "excl")
            self._schedule_render()

    def _reload_excl_data(self) -> None:
        if self._excl_path and self._excl_path.exists():
            self._load_raw_excl_file(self._excl_path, "excl")
            self._schedule_render()

    def _on_active_source_changed(self, text: str) -> None:
        if text in ("raw", "excl"):
            self._active_source = text
            self._refresh_column_completers()
            self._refresh_y_browse_combo()
            self._schedule_render()

    def _sync_rawexcl_combo(self) -> None:
        """Keep combo in sync with _active_source without triggering signal loop."""
        self.combo_active_source.blockSignals(True)
        idx = self.combo_active_source.findText(self._active_source)
        if idx >= 0:
            self.combo_active_source.setCurrentIndex(idx)
        self.combo_active_source.blockSignals(False)

    # ------------------------------------------------------------------

    def auto_discover_data(self, search_dirs: Optional[List[Path]] = None) -> bool:
        """Try to auto-discover the most recent lv_kpis_clean.xlsx."""
        dirs = search_dirs or []
        if self._get_output_dir:
            try:
                dirs.insert(0, self._get_output_dir())
            except Exception:
                pass
        home = Path(os.environ.get("USERPROFILE", Path.home()))
        dirs.extend([
            home / "OneDrive - Stellantis" / "Pessoal" / "out_mestrado",
            home / "OneDrive - Stellantis" / "Pessoal" / "pipeline_newgen" / "out",
        ])
        best = _find_latest_kpis_xlsx(dirs)
        if best and self.load_data_from_file(best):
            if self.combo_plot_selector.count() > 0 and self._selected_plot_idx < 0:
                self._selected_plot_idx = 0
                self.combo_plot_selector.blockSignals(True)
                self.combo_plot_selector.setCurrentIndex(0)
                self.combo_plot_selector.blockSignals(False)
                self._populate_from_record(self._get_effective_record(0))
            else:
                self._render_preview()
            return True
        return False

    def _browse_data_file(self) -> None:
        start_dir = str(self._loaded_path.parent) if self._loaded_path else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar xlsx", start_dir,
            "Excel files (*.xlsx);;All files (*)"
        )
        if path:
            p = Path(path)
            self.load_data_from_file(p)
            # Clear stale series styles and plot overrides — they belong to the previous file
            self._series_style_overrides = {}
            self._session["series_styles"] = {}
            self._draft_overrides = {}
            # If this is a compare xlsx, load it into _compare_df directly
            if (self._loaded_df is not None
                    and "Metrica" in self._loaded_df.columns
                    and "Comparacao" in self._loaded_df.columns):
                self._load_compare_from_df(self._loaded_df, p)
            # Populate _raw_df so the Raw/Excl toggle has a "raw" to work with.
            # Only if _raw_df not already set by Browse Raw — avoid overwriting an
            # intentional raw source with a secondary Browse.
            if (self._loaded_df is not None and not self._loaded_df.empty
                    and "Metrica" not in self._loaded_df.columns
                    and self._raw_df is None):
                self._raw_df = self._loaded_df
                self._raw_path = self._loaded_path
                mtime = time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.localtime(self._loaded_path.stat().st_mtime),
                )
                shape_txt = f"{self._raw_df.shape[0]}r×{self._raw_df.shape[1]}c"
                self.lbl_raw_data.setText(f"Raw: {p.name}  {shape_txt}  {mtime}")
            self._schedule_render()

    def _reload_data(self) -> None:
        if self._loaded_path and self._loaded_path.exists():
            self.load_data_from_file(self._loaded_path)
            self._schedule_render()
        else:
            if self.auto_discover_data():
                self._schedule_render()
            else:
                self._show_status("Nenhum arquivo encontrado para recarregar.")

    # ------------------------------------------------------------------
    # Workspace Persistence
    # ------------------------------------------------------------------

    def _workspace_file_path(self) -> Path:
        if self._get_config_dir:
            try:
                return self._get_config_dir() / "preview_workspace.json"
            except Exception:
                pass
        return Path(os.environ.get("USERPROFILE", Path.home())) / ".pipeline_newgen" / "preview_workspace.json"

    def _save_workspace(self) -> None:
        """Save entire session state to disk, including plots.toml config."""
        self._sync_ui_to_session()
        self._sync_current_to_plots_table()
        path = self._workspace_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 2, **self._session}
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if self._save_config_callback is not None:
            self._save_config_callback()
        self._refresh_workspace_list()
        self._show_status(f"Workspace + config salvos: {path.name}")

    def _save_workspace_as(self) -> None:
        start_dir = str(self._workspace_file_path().parent)
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar workspace como...", start_dir,
            "JSON (*.json);;All files (*)"
        )
        if path:
            self._sync_ui_to_session()
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {"version": 2, **self._session}
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self._refresh_workspace_list()
            self._show_status(f"Workspace salvo: {p.name}")

    def _refresh_workspace_list(self) -> None:
        """Refresh the list of saved workspace JSON files.

        Finds all *.json in the config dir that are valid workspaces (version==2,
        contain 'data_source' key).  preview_workspace.json shows as '(default)'.
        """
        self.list_workspaces.clear()
        ws_dir = self._workspace_file_path().parent
        if not ws_dir.exists():
            return
        candidates = []
        for f in ws_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(d, dict) and d.get("version") == 2 and "data_source" in d:
                    candidates.append(f)
            except (json.JSONDecodeError, OSError):
                continue
        for f in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
            if f.stem == "preview_workspace":
                label = "(default)"
            else:
                label = f.stem.replace("preview_workspace_", "").replace("_", " ")
            item = QListWidgetItem(f"{label}  [{time.strftime('%d/%m %H:%M', time.localtime(f.stat().st_mtime))}]")
            item.setData(Qt.UserRole, str(f))
            item.setToolTip(str(f))
            self.list_workspaces.addItem(item)

    def _on_workspace_double_click(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.UserRole)
        if not path_str:
            return
        p = Path(path_str)
        if not p.exists():
            self._show_status(f"Workspace nao encontrado: {p.name}")
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            data.pop("version", None)
            # FULL REPLACE: reset to clean default state, then apply loaded values.
            # Using merge (update) left y_scales/series_styles/comments from the previous
            # session contaminating the newly loaded workspace.
            self._session = {
                "data_source": {"path": "", "compare_path": ""},
                "axis": {"x_col": "Load_kW", "x_label": "", "x_min": "", "x_max": "", "x_step": ""},
                "y_scales": {},
                "comments": {},
                "series_styles": {},
                "display": {"cursor_font_size": 15, "filter_h2o_list": "", "label_variant": "tag",
                            "lock_x": False, "series_col": ""},
                "compare": {"active_metric": ""},
                "active_mode": "all_iterations_yx",
            }
            for key in self._session:
                if key in data:
                    self._session[key] = data[key]
            # Full in-memory reset — _restore_session_to_ui will re-hydrate from paths
            self._loaded_df = None
            self._loaded_path = None
            self._compare_df = None
            self._compare_path = None
            self._raw_df = None
            self._raw_path = None
            self._excl_df = None
            self._excl_path = None
            self._draft_overrides = {}
            self._series_style_overrides = {}
            self._restore_session_to_ui()
            self._show_status(f"Workspace carregado: {p.stem}")
        except (json.JSONDecodeError, OSError) as e:
            self._show_status(f"Erro ao carregar workspace: {e}")

    def _load_workspace(self) -> bool:
        """Load session state from disk. Returns True if loaded successfully."""
        path = self._workspace_file_path()
        if not path.exists():
            return self._migrate_legacy_config()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 2:
                return self._migrate_legacy_config()
            data.pop("version", None)
            for key in self._session:
                if key in data:
                    if isinstance(self._session[key], dict) and isinstance(data[key], dict):
                        self._session[key].update(data[key])
                    else:
                        self._session[key] = data[key]
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def _migrate_legacy_config(self) -> bool:
        """Migrate from old multi-file config to new workspace format."""
        config_dir = self._workspace_file_path().parent
        # Migrate y_scale_memory
        yscale_path = config_dir / "y_scale_memory.json"
        if yscale_path.exists():
            try:
                data = json.loads(yscale_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k, v in data.items():
                        if k != "__cursor_font_size__" and isinstance(v, dict):
                            self._session["y_scales"][k] = v
                        elif k == "__cursor_font_size__":
                            fs = v.get("y_min", "15")
                            self._session["display"]["cursor_font_size"] = int(fs) if fs else 15
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        # Migrate comments
        comments_path = config_dir / "preview_comments.json"
        if comments_path.exists():
            try:
                data = json.loads(comments_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for key, val in data.items():
                        if isinstance(val, dict) and val.get("text"):
                            self._session["comments"][key] = val
            except (json.JSONDecodeError, OSError):
                pass
        # Migrate presets
        presets_path = config_dir / "preview_presets.json"
        if presets_path.exists():
            try:
                data = json.loads(presets_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for name, preset in data.items():
                        if not isinstance(preset, dict):
                            continue
                        dp = preset.get("data_path", "")
                        if dp and Path(dp).exists():
                            if preset.get("plot_type") == "compare_bl_vs_adtv":
                                self._session["data_source"]["compare_path"] = dp
                            else:
                                self._session["data_source"]["path"] = dp
                            for k in ("x_col", "x_label", "x_min", "x_max", "x_step"):
                                if preset.get(k):
                                    self._session["axis"][k] = preset[k]
                            if preset.get("plot_type"):
                                self._session["active_mode"] = preset["plot_type"]
                            if preset.get("series_styles"):
                                self._session["series_styles"] = preset["series_styles"]
                            if preset.get("filter_h2o_list"):
                                self._session["display"]["filter_h2o_list"] = preset["filter_h2o_list"]
            except (json.JSONDecodeError, OSError):
                pass
        return bool(self._session["data_source"]["path"] or self._session["data_source"]["compare_path"])

    def _sync_ui_to_session(self) -> None:
        """Capture current UI control values into the session dict."""
        # Y scale + per-plot overrides for current context
        y_key = self._current_y_scale_key()
        if y_key:
            self._session["y_scales"][y_key] = {
                "y_min": self.edit_y_min.text().strip(),
                "y_max": self.edit_y_max.text().strip(),
                "y_step": self.edit_y_step.text().strip(),
                "x_col": self.edit_x_col.text().strip(),
                "x_min": self.edit_x_min.text().strip(),
                "x_max": self.edit_x_max.text().strip(),
                "x_step": self.edit_x_step.text().strip(),
                "show_uncertainty": "1" if self.chk_show_uncertainty.isChecked() else "0",
            }
        # Axis
        self._session["axis"] = {
            "x_col": self.edit_x_col.text().strip(),
            "x_label": self.edit_x_label.text().strip(),
            "x_min": self.edit_x_min.text().strip(),
            "x_max": self.edit_x_max.text().strip(),
            "x_step": self.edit_x_step.text().strip(),
        }
        # Display
        self._session["display"]["filter_h2o_list"] = self.edit_filter_h2o.text().strip()
        self._session["display"]["label_variant"] = self.combo_label_variant.currentText()
        self._session["display"]["lock_x"] = self.chk_lock_x.isChecked()
        self._session["display"]["series_col"] = self.edit_series_col.text().strip()
        try:
            self._session["display"]["cursor_font_size"] = int(self.edit_cursor_font.text().strip() or "15")
        except ValueError:
            pass
        # Data source
        if self._loaded_path:
            self._session["data_source"]["path"] = str(self._loaded_path)
        if self._compare_path:
            self._session["data_source"]["compare_path"] = str(self._compare_path)
        if self._raw_path:
            self._session["data_source"]["raw_path"] = str(self._raw_path)
        if self._excl_path:
            self._session["data_source"]["excl_path"] = str(self._excl_path)
        self._session["data_source"]["active_source"] = self._active_source
        # Active mode
        self._session["active_mode"] = self.combo_plot_type.currentText()
        # Compare
        self._session["compare"]["active_metric"] = self.combo_compare_metric.currentText() or ""
        # Comment (per-plot, keyed by current y_col or metric)
        cmt_key = self._current_y_scale_key()
        if cmt_key and self._compare_comment_data.get("text"):
            self._session["comments"][cmt_key] = dict(self._compare_comment_data)
        # Series styles
        self._session["series_styles"] = dict(self._series_style_overrides)

    def _current_y_scale_key(self) -> str:
        """Return the key for the current Y scale context."""
        if self.combo_plot_type.currentText() == "compare_bl_vs_adtv":
            return self.combo_compare_metric.currentText() or ""
        return self.edit_y_col.text().strip()

    def _restore_session_to_ui(self) -> None:
        """Restore session state to UI controls after loading."""
        self._populating = True
        s = self._session
        # Reset all loaded data unconditionally
        self._loaded_df = None
        self._loaded_path = None
        self._raw_df = None
        self._raw_path = None
        self._excl_df = None
        self._excl_path = None
        # Determine active source and only load what's needed now
        active_src = s["data_source"].get("active_source", "excl")
        if active_src in ("raw", "excl"):
            self._active_source = active_src
        # Load only the active data source eagerly; others stay lazy (loaded on demand)
        data_path = s["data_source"].get("path", "")
        raw_path = s["data_source"].get("raw_path", "")
        excl_path = s["data_source"].get("excl_path", "")
        compare_path = s["data_source"].get("compare_path", "")
        if active_src == "excl" and excl_path and Path(excl_path).exists():
            self._load_raw_excl_file(Path(excl_path), "excl")
        elif active_src == "raw" and raw_path and Path(raw_path).exists():
            self._load_raw_excl_file(Path(raw_path), "raw")
        elif data_path and Path(data_path).exists():
            self.load_data_from_file(Path(data_path))
        # Store paths for lazy loading later
        if raw_path and Path(raw_path).exists() and self._raw_path is None:
            self._raw_path = Path(raw_path)
        if excl_path and Path(excl_path).exists() and self._excl_path is None:
            self._excl_path = Path(excl_path)
        if data_path and Path(data_path).exists() and self._loaded_path is None:
            self._loaded_path = Path(data_path)
        # Compare — only load if different from main
        if compare_path and compare_path != data_path and compare_path != excl_path:
            p = Path(compare_path)
            if p.exists():
                self._load_compare_xlsx(p)
        self._sync_rawexcl_combo()
        # Axis
        ax = s.get("axis", {})
        self.edit_x_col.setText(ax.get("x_col", "Load_kW"))
        self.edit_x_label.setText(ax.get("x_label", ""))
        self.edit_x_min.setText(ax.get("x_min", ""))
        self.edit_x_max.setText(ax.get("x_max", ""))
        self.edit_x_step.setText(ax.get("x_step", ""))
        # Display
        disp = s.get("display", {})
        self.edit_filter_h2o.setText(disp.get("filter_h2o_list", ""))
        lv = disp.get("label_variant", "tag")
        idx_lv = self.combo_label_variant.findText(lv)
        if idx_lv >= 0:
            self.combo_label_variant.setCurrentIndex(idx_lv)
        self.chk_lock_x.setChecked(disp.get("lock_x", False))
        self.edit_series_col.setText(disp.get("series_col", ""))
        self.edit_cursor_font.setText(str(disp.get("cursor_font_size", 15)))
        self._apply_cursor_font_size(disp.get("cursor_font_size", 15))
        # Active mode
        mode = s.get("active_mode", "all_iterations_yx")
        idx_pt = self.combo_plot_type.findText(mode)
        if idx_pt >= 0:
            self.combo_plot_type.setCurrentIndex(idx_pt)
        # Compare active metric
        metric = s.get("compare", {}).get("active_metric", "")
        if metric and self.combo_compare_metric.count() > 0:
            idx_m = self.combo_compare_metric.findText(metric)
            if idx_m >= 0:
                self.combo_compare_metric.setCurrentIndex(idx_m)
        # Y scale for active context
        y_key = self._current_y_scale_key()
        if y_key and y_key in s.get("y_scales", {}):
            ys = s["y_scales"][y_key]
            self.edit_y_min.setText(ys.get("y_min", ""))
            self.edit_y_max.setText(ys.get("y_max", ""))
            self.edit_y_step.setText(ys.get("y_step", ""))
        # Comment (per-plot)
        comments = s.get("comments", {})
        if y_key and y_key in comments:
            self._compare_comment_data = comments[y_key]
        elif s.get("comment"):
            self._compare_comment_data = s["comment"]
        else:
            self._compare_comment_data = _empty_comment_data()
        # Series styles
        self._series_style_overrides = s.get("series_styles", {})
        self._populating = False
        self._refresh_workspace_list()
        # Ensure plot selector has content and populates y_col from first record
        self.refresh_plot_selector()
        if self.combo_plot_selector.count() > 0 and not self.edit_y_col.text().strip():
            self._selected_plot_idx = 0
            self._populate_from_record(self._get_effective_record(0))
        self._render_preview()

    # ------------------------------------------------------------------
    # Builtin Preset Templates (X axis only)
    # ------------------------------------------------------------------

    def _on_preset_selected(self, index: int) -> None:
        if index <= 0 or self._populating:
            return
        name = self.combo_preset.currentText()
        preset = _BUILTIN_PRESETS.get(name)
        if not preset:
            return
        self._populating = True
        self.edit_x_col.setText(preset.get("x_col", ""))
        self.edit_x_label.setText(preset.get("x_label", ""))
        self.edit_x_min.setText(preset.get("x_min", ""))
        self.edit_x_max.setText(preset.get("x_max", ""))
        self.edit_x_step.setText(preset.get("x_step", ""))
        self.edit_series_col.setText(preset.get("series_col", ""))
        pt = preset.get("plot_type", "")
        if pt:
            idx_pt = self.combo_plot_type.findText(pt)
            if idx_pt >= 0:
                self.combo_plot_type.setCurrentIndex(idx_pt)
        self.chk_lock_x.setChecked(True)
        self._populating = False
        self._schedule_render()
        self._show_status(f"Template '{name}' aplicado.")

    # ------------------------------------------------------------------
    # Cursor Readout
    # ------------------------------------------------------------------

    def _apply_cursor_font_size(self, sz: int = 0) -> None:
        if sz <= 0:
            try:
                sz = int(self.edit_cursor_font.text().strip() or "11")
            except ValueError:
                sz = 11
        sz = max(6, min(24, sz))
        self._cursor_table.setStyleSheet(
            f"QTableWidget {{ font-size: {sz}px; }}"
            f"QHeaderView::section {{ font-size: {sz}px; font-weight: bold; }}"
            "QTableWidget::item { padding: 2px 4px; }"
        )
        self._cursor_table.verticalHeader().setDefaultSectionSize(sz + 11)

    def _on_cursor_font_changed(self) -> None:
        size = self.edit_cursor_font.text().strip()
        try:
            sz = int(size)
            sz = max(6, min(24, sz))
        except ValueError:
            sz = 11
        self.edit_cursor_font.setText(str(sz))
        self._apply_cursor_font_size(sz)
        self._session["display"]["cursor_font_size"] = sz

    def _on_cursor_mode_toggled(self, active: bool) -> None:
        self._cursor_mode_active = active
        self._cursor_table.setVisible(active)
        self.edit_cursor_font.setVisible(active)
        if active:
            self._show_status("Cursor ON — clique ou arraste no grafico para ler valores.")
            self._render_preview()
        else:
            if self._cursor_line:
                try:
                    self._cursor_line.remove()
                except Exception:
                    pass
                self._cursor_line = None
            if self._cursor_arrow:
                try:
                    self._cursor_arrow.remove()
                except Exception:
                    pass
                self._cursor_arrow = None
            if self._canvas:
                self._canvas.draw_idle()
            self._show_status("Cursor OFF.")

    def _build_snap_grid(self) -> None:
        """Cache sorted X datapoints for fast cursor snapping."""
        self._snap_grid: List[float] = []
        self._cursor_interpolating: bool = False
        if not self._current_fig:
            return
        ax = self._current_fig.gca()
        all_x = set()
        for line in ax.get_lines():
            if line == self._cursor_line:
                continue
            lbl = line.get_label()
            if lbl and not lbl.startswith("_"):
                for xv in line.get_xdata():
                    if np.isfinite(xv):
                        all_x.add(float(xv))
        self._snap_grid = sorted(all_x)
        n_unique = len(self._snap_grid)
        self._cursor_interpolating = n_unique > 40

    def _snap_cursor_x(self, raw_x: float) -> float:
        """Snap cursor to nearest actual datapoint X value (uses cache).
        In interpolating mode, returns raw_x for free cursor movement."""
        if not hasattr(self, "_snap_grid") or not self._snap_grid:
            self._build_snap_grid()
        if getattr(self, "_cursor_interpolating", False):
            return raw_x
        if not self._snap_grid:
            return raw_x
        idx = int(np.searchsorted(self._snap_grid, raw_x))
        idx = max(0, min(idx, len(self._snap_grid) - 1))
        if idx > 0 and abs(self._snap_grid[idx - 1] - raw_x) < abs(self._snap_grid[idx] - raw_x):
            idx -= 1
        return self._snap_grid[idx]

    def _move_cursor_to(self, snapped: float) -> None:
        if snapped == self._cursor_x:
            return
        self._cursor_x = snapped
        if self._cursor_line:
            self._cursor_line.set_xdata([snapped, snapped])
        if hasattr(self, "_cursor_arrow") and self._cursor_arrow:
            ax = self._current_fig.gca()
            ylim = ax.get_ylim()
            self._cursor_arrow.xy = (snapped, ylim[0] + (ylim[1] - ylim[0]) * 0.05)
            self._cursor_arrow.xyann = (snapped, ylim[1] - (ylim[1] - ylim[0]) * 0.02)
        if self._canvas:
            self._canvas.draw_idle()
        self._update_cursor_table()

    def _on_cursor_click(self, event) -> None:
        if not self._cursor_mode_active or event.inaxes is None or event.xdata is None:
            return
        if self._exclusion_mode_active:
            return
        if event.button != 1:
            return
        self._move_cursor_to(self._snap_cursor_x(event.xdata))

    # ------------------------------------------------------------------
    # Hover tooltip
    # ------------------------------------------------------------------

    def _on_hover_check(self, event) -> None:
        if self._exclusion_mode_active:
            self._hover_timer.stop()
            self._hide_hover_tooltip()
            return
        if event.inaxes is None or event.xdata is None:
            self._hover_timer.stop()
            self._hide_hover_tooltip()
            return
        self._hover_last_event = event
        self._hover_timer.stop()
        self._hide_hover_tooltip()
        self._hover_timer.start()

    def _show_hover_tooltip(self) -> None:
        event = self._hover_last_event
        if event is None or event.inaxes is None or not self._current_fig:
            return
        ax = event.inaxes
        best_dist = float("inf")
        best_line = None
        best_idx = -1
        display_trans = ax.transData
        for line in ax.get_lines():
            lbl = line.get_label()
            if not lbl or lbl.startswith("_") or line == getattr(self, "_cursor_line", None):
                continue
            xd = np.asarray(line.get_xdata(), dtype=float)
            yd = np.asarray(line.get_ydata(), dtype=float)
            if len(xd) == 0:
                continue
            pts_data = np.column_stack([xd, yd])
            pts_display = display_trans.transform(pts_data)
            mouse_display = display_trans.transform([[event.xdata, event.ydata]])[0]
            dists = np.hypot(pts_display[:, 0] - mouse_display[0], pts_display[:, 1] - mouse_display[1])
            min_idx = int(np.nanargmin(dists))
            if dists[min_idx] < best_dist:
                best_dist = dists[min_idx]
                best_line = line
                best_idx = min_idx
        if best_dist > 15 or best_line is None:
            return
        x_val = float(best_line.get_xdata()[best_idx])
        y_val = float(best_line.get_ydata()[best_idx])
        series_label = best_line.get_label()
        color_hex = matplotlib.colors.to_hex(best_line.get_color())
        df = self._get_effective_df()
        info = self._lookup_point_info(df, x_val, series_label)
        text_lines = [
            f"<b>{series_label}</b>",
            f"Load: {info.get('Load_kW', '—')}",
            f"Consumo: SD {info.get('sd_consumo', '—')}",
            f"Rotacao: {info.get('rotacao', '—')} | SD {info.get('sd_rotacao', '—')}",
            f"T_E_TURB: {info.get('T_E_TURB', '—')} | SD {info.get('sd_T_E_TURB', '—')}",
            f"P_E_TURB: {info.get('P_E_TURB', '—')} | SD {info.get('sd_P_E_TURB', '—')}",
            f"P_COLETOR: {info.get('P_COLETOR', '—')} | SD {info.get('sd_P_COLETOR', '—')}",
        ]
        html = "<br>".join(text_lines)
        if self._hover_tooltip is None:
            self._hover_tooltip = QLabel(self)
            self._hover_tooltip.setWindowFlags(Qt.ToolTip)
            self._hover_tooltip.setTextFormat(Qt.RichText)
        self._hover_tooltip.setStyleSheet(
            f"QLabel {{ background-color: {color_hex}22; border: 2px solid {color_hex}; "
            f"padding: 6px 8px; font-size: 15px; border-radius: 4px; }}"
        )
        self._hover_tooltip.setText(html)
        self._hover_tooltip.adjustSize()
        from PySide6.QtGui import QCursor
        cursor_pos = QCursor.pos()
        self._hover_tooltip.move(cursor_pos.x() + 18, cursor_pos.y() + 18)
        self._hover_tooltip.show()

    def _hide_hover_tooltip(self) -> None:
        if self._hover_tooltip is not None:
            self._hover_tooltip.hide()

    def _lookup_point_info(self, df: pd.DataFrame, x_val: float, series_label: str) -> Dict[str, str]:
        result: Dict[str, str] = {
            "Load_kW": "—", "sd_consumo": "—", "sd_rotacao": "—",
            "rotacao": "—", "T_E_TURB": "—", "P_E_TURB": "—",
            "sd_T_E_TURB": "—", "sd_P_E_TURB": "—",
            "P_COLETOR": "—", "sd_P_COLETOR": "—",
        }
        if df is None or df.empty:
            return result
        x_col = self.edit_x_col.text().strip() or "Load_kW"
        x_vals = pd.to_numeric(df.get(x_col), errors="coerce")
        mask = np.isclose(x_vals, x_val, atol=0.01)
        if not mask.any():
            idx_nearest = (x_vals - x_val).abs().idxmin()
            mask = df.index == idx_nearest
        rows = df.loc[mask]
        if rows.empty:
            return result
        row = rows.iloc[0]

        def _fmt(col, unit="", decimals=1):
            if col not in df.columns:
                return "—"
            v = row.get(col)
            return f"{float(v):.{decimals}f}{' ' + unit if unit else ''}" if pd.notna(v) else "—"

        result["Load_kW"] = _fmt("Load_kW", "kW", 1)
        for cand in ["Consumo_kg_h_sd_of_windows", "Consumo_sd_of_windows"]:
            if cand in df.columns:
                result["sd_consumo"] = _fmt(cand, "kg/h", 3)
                break
        for cand in ["Rotação_mean_of_windows", "Rotacao_mean_of_windows"]:
            if cand in df.columns:
                result["rotacao"] = _fmt(cand, "rpm", 0)
                break
        for cand in ["Rotação_sd_of_windows", "Rotacao_sd_of_windows"]:
            if cand in df.columns:
                result["sd_rotacao"] = _fmt(cand, "rpm", 1)
                break
        result["T_E_TURB"] = _fmt("T_E_TURB_mean_of_windows", "C", 1)
        result["sd_T_E_TURB"] = _fmt("T_E_TURB_sd_of_windows", "C", 1)
        result["P_E_TURB"] = _fmt("P_E_TURB_RAW_mean_of_windows", "kPa", 1)
        result["sd_P_E_TURB"] = _fmt("P_E_TURB_RAW_sd_of_windows", "kPa", 2)
        result["P_COLETOR"] = _fmt("P_COLETOR_RAW_mean_of_windows", "kPa", 1)
        result["sd_P_COLETOR"] = _fmt("P_COLETOR_RAW_sd_of_windows", "kPa", 2)
        return result

    def _on_cursor_move(self, event) -> None:
        if not self._cursor_mode_active or event.inaxes is None or event.xdata is None:
            if self._canvas and not self._exclusion_mode_active:
                self._canvas.setCursor(Qt.ArrowCursor)
            return
        xlim = event.inaxes.get_xlim()
        tolerance = (xlim[1] - xlim[0]) * 0.04
        near_cursor = abs(event.xdata - self._cursor_x) < tolerance
        if self._canvas and not self._exclusion_mode_active:
            self._canvas.setCursor(Qt.SizeHorCursor if near_cursor else Qt.ArrowCursor)
        if event.button != 1:
            return
        if self._exclusion_mode_active and not near_cursor:
            return
        self._move_cursor_to(self._snap_cursor_x(event.xdata))

    def _update_cursor_table(self) -> None:
        if not self._current_fig:
            return
        ax = self._current_fig.gca()
        lines = [l for l in ax.get_lines()
                 if l.get_label() and not l.get_label().startswith("_")
                 and l != self._cursor_line]

        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QPixmap, QIcon, QPainter, QBrush, QPen
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF

        interpolating = getattr(self, "_cursor_interpolating", False)

        self._cursor_table.setRowCount(len(lines))
        for i, line in enumerate(lines):
            xdata = np.asarray(line.get_xdata(), dtype=float)
            ydata = np.asarray(line.get_ydata(), dtype=float)
            if len(xdata) == 0:
                continue

            if interpolating:
                valid = np.isfinite(xdata) & np.isfinite(ydata)
                xv, yv = xdata[valid], ydata[valid]
                if len(xv) >= 2:
                    sort_idx = np.argsort(xv)
                    xv, yv = xv[sort_idx], yv[sort_idx]
                    y_val = float(np.interp(self._cursor_x, xv, yv))
                    val_text = f"{y_val:.1f}"
                elif len(xv) == 1:
                    val_text = f"{yv[0]:.1f}"
                else:
                    val_text = "—"
            else:
                mask = np.isclose(xdata, self._cursor_x, atol=1e-4)
                if mask.any():
                    y_val = ydata[mask][0]
                    val_text = f"{y_val:.1f}"
                else:
                    val_text = "—"

            color_hex = matplotlib.colors.to_hex(line.get_color())
            marker = line.get_marker() or "o"

            px = QPixmap(14, 14)
            px.fill(QColor(0, 0, 0, 0))
            painter = QPainter(px)
            painter.setRenderHint(QPainter.Antialiasing)
            qc = QColor(color_hex)
            painter.setBrush(QBrush(qc))
            painter.setPen(QPen(qc.darker(130), 1))
            if marker in ("s", "S"):
                painter.drawRect(2, 2, 10, 10)
            elif marker in ("^", "v", "<", ">"):
                if marker == "^":
                    tri = QPolygonF([QPointF(7, 1), QPointF(1, 12), QPointF(13, 12)])
                elif marker == "v":
                    tri = QPolygonF([QPointF(7, 13), QPointF(1, 2), QPointF(13, 2)])
                else:
                    tri = QPolygonF([QPointF(7, 1), QPointF(1, 12), QPointF(13, 12)])
                painter.drawPolygon(tri)
            elif marker in ("D", "d"):
                diamond = QPolygonF([QPointF(7, 1), QPointF(13, 7), QPointF(7, 13), QPointF(1, 7)])
                painter.drawPolygon(diamond)
            else:
                painter.drawEllipse(2, 2, 10, 10)
            painter.end()

            item_label = QTableWidgetItem(line.get_label())
            item_label.setIcon(QIcon(px))
            self._cursor_table.setItem(i, 0, item_label)
            self._cursor_table.setItem(i, 1, QTableWidgetItem(val_text))

        x_label = self.edit_x_label.text().strip() or self.edit_x_col.text().strip() or "X"
        mode_tag = "Interpolating" if interpolating else "Exact match"
        self._cursor_table.setHorizontalHeaderLabels([f"Serie [{mode_tag}]", f"@ {self._cursor_x:g} ({x_label})"])

    # ------------------------------------------------------------------
    # Compare Mode
    # ------------------------------------------------------------------

    def _on_plot_type_changed(self, text: str) -> None:
        is_compare = (text == "compare_bl_vs_adtv")
        self.combo_compare_metric.setVisible(is_compare)
        self.combo_compare_pair.setVisible(False)
        if self._populating:
            return
        if is_compare and self._compare_df is None:
            self._auto_discover_compare_xlsx()

    def _on_compare_metric_changed(self) -> None:
        if self._populating:
            return
        # Save Y scale + comment for previous metric
        prev = self._session["compare"].get("active_metric", "")
        if prev:
            self._session["y_scales"][prev] = {
                "y_min": self.edit_y_min.text().strip(),
                "y_max": self.edit_y_max.text().strip(),
                "y_step": self.edit_y_step.text().strip(),
            }
            if self._compare_comment_data.get("text"):
                self._session["comments"][prev] = dict(self._compare_comment_data)
        # Switch to new metric
        new_metric = self.combo_compare_metric.currentText()
        self._session["compare"]["active_metric"] = new_metric
        self._last_y_col = new_metric
        # Recall Y scale
        ys = self._session["y_scales"].get(new_metric, {})
        self._populating = True
        self.edit_y_min.setText(ys.get("y_min", ""))
        self.edit_y_max.setText(ys.get("y_max", ""))
        self.edit_y_step.setText(ys.get("y_step", ""))
        self._populating = False
        # Recall comment for new metric
        self._compare_comment_data = self._session.get("comments", {}).get(new_metric, _empty_comment_data())
        self._debounce_timer.stop()
        self._render_preview()

    def _open_comment_dialog(self) -> None:
        def _apply_cb(data):
            self._compare_comment_data = data
            self._render_preview()

        dlg = CommentDialog(self._compare_comment_data, apply_callback=_apply_cb, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._compare_comment_data = dlg.get_data()
            self._render_preview()

    def _auto_discover_compare_xlsx(self) -> None:
        # If Browse loaded a file that IS the compare xlsx, use it directly
        if (self._loaded_df is not None and not self._loaded_df.empty
                and "Metrica" in self._loaded_df.columns
                and "Comparacao" in self._loaded_df.columns):
            self._load_compare_from_df(self._loaded_df, self._loaded_path)
            return

        search_dirs = []
        if self._loaded_path:
            parent = self._loaded_path.parent
            search_dirs.append(parent / "plots" / "compare_iteracoes_bl_vs_adtv")
            search_dirs.append(parent)
        if self._get_output_dir:
            try:
                out = self._get_output_dir()
                search_dirs.append(out / "plots" / "compare_iteracoes_bl_vs_adtv")
            except Exception:
                pass

        for d in search_dirs:
            candidate = d / "compare_iteracoes_metricas_incertezas.xlsx"
            if candidate.exists():
                self._load_compare_xlsx(candidate)
                return
        self._show_status("Compare xlsx nao encontrado. Use Browse para carregar.")

    def _invalidate_thumb_cache(self) -> None:
        if hasattr(self, "_thumb_cache"):
            self._thumb_cache.clear()
        if hasattr(self, "_thumb_items_snapshot"):
            self._thumb_items_snapshot = []

    def _load_compare_from_df(self, df: pd.DataFrame, path: Optional[Path]) -> None:
        """Load compare data from an already-loaded DataFrame."""
        from ..runtime.compare_iteracoes.preview_renderers import (
            available_metrics, available_comparacoes,
        )
        if "Load_kW" in df.columns:
            df = df.copy()
            df["Load_kW"] = pd.to_numeric(df["Load_kW"], errors="coerce")
        self._compare_df = df
        self._compare_path = path
        self._invalidate_thumb_cache()

        was_populating = self._populating
        self._populating = True
        self.combo_compare_metric.clear()
        metrics = available_metrics(self._compare_df)
        self.combo_compare_metric.addItems(metrics)
        self._populating = was_populating

        name = path.name if path else "(DataFrame)"
        self._show_status(f"Compare: {name} ({len(metrics)} metricas)")

    def _load_compare_xlsx(self, path: Path) -> None:
        from ..runtime.compare_iteracoes.preview_renderers import (
            load_compare_xlsx, available_metrics,
        )
        try:
            self._compare_df = load_compare_xlsx(path)
            self._compare_path = path
            self._invalidate_thumb_cache()
        except Exception as e:
            self._show_status(f"Erro ao carregar compare xlsx: {e}")
            return

        was_populating = self._populating
        self._populating = True
        self.combo_compare_metric.clear()
        metrics = available_metrics(self._compare_df)
        self.combo_compare_metric.addItems(metrics)
        self._populating = was_populating

        self._show_status(f"Compare: {path.name} ({len(metrics)} metricas)")

    def _render_compare_preview(self) -> Optional[Figure]:
        if self._compare_df is None or self._compare_df.empty:
            return None
        metrica = self.combo_compare_metric.currentText()
        if not metrica:
            return None

        from ..runtime.compare_iteracoes.preview_renderers import (
            render_compare_delta_all_overlay,
        )

        return render_compare_delta_all_overlay(
            self._compare_df,
            metrica=metrica,
            include_uncertainty=self.chk_show_uncertainty.isChecked(),
        )

    # ------------------------------------------------------------------
    # Y Column Browser
    # ------------------------------------------------------------------

    def _on_y_browse_selected(self, index: int) -> None:
        if index <= 0 or self._populating:
            return
        col_name = self.combo_y_browse.currentText()
        if col_name and col_name != "(browse columns...)":
            self.edit_y_col.setText(col_name)
            self.edit_y_label.setText(col_name)
            self._sync_current_to_plots_table()
            self._schedule_render()

    def _refresh_y_browse_combo(self) -> None:
        df = self._get_effective_df()
        self.combo_y_browse.blockSignals(True)
        self.combo_y_browse.clear()
        self.combo_y_browse.addItem("(browse columns...)")
        if df is not None and not df.empty:
            numeric_cols = sorted(
                [str(c) for c in df.select_dtypes(include=["number"]).columns],
                key=str.lower,
            )
            for col in numeric_cols:
                self.combo_y_browse.addItem(col)
        self.combo_y_browse.blockSignals(False)

    # ------------------------------------------------------------------
    # Series label computation for filtering
    # ------------------------------------------------------------------

    def _compute_series_labels_for_filter(self, df: pd.DataFrame, plot_type: str) -> Optional[pd.Series]:
        """Compute series labels matching what the renderer actually uses for legend."""
        if df is None or df.empty:
            return None

        if plot_type == "all_iterations_yx" and "BaseName" in df.columns:
            from ..runtime.unitary_plots.renderer_all_iterations import (
                _derive_series_column, _build_series_label,
            )
            return _derive_series_column(df).map(_build_series_label)

        if "Fuel_Label" in df.columns or "DIES_pct" in df.columns:
            from ..runtime.unitary_plots.fuel_groups import fuel_plot_groups
            groups = fuel_plot_groups(df)
            labels = pd.Series("", index=df.index)
            for label, group_df in groups:
                if label:
                    labels.loc[group_df.index] = label
            if labels.any():
                return labels

        if "BaseName" in df.columns:
            from ..runtime.unitary_plots.renderer_all_iterations import (
                _derive_series_column, _build_series_label,
            )
            return _derive_series_column(df).map(_build_series_label)

        return None

    # ------------------------------------------------------------------
    # Point Exclusion
    # ------------------------------------------------------------------

    def _get_exclusion_store(self):
        from .point_exclusion import ExclusionStore
        if not hasattr(self, "_exclusion_store") or self._exclusion_store is None:
            path = self._workspace_file_path().parent / "point_exclusions.json"
            self._exclusion_store = ExclusionStore(path)
        return self._exclusion_store

    def _on_exclusion_mode_toggled(self, active: bool) -> None:
        self._exclusion_mode_active = active
        if active:
            self._show_status("Dataset Filter ON — left-click: ponto, right-click: serie.")
            if self._canvas and not self._cursor_mode_active:
                self._canvas.setCursor(Qt.CrossCursor)
        else:
            self._clear_pick_highlight()
            self._show_status("Dataset Filter OFF.")
            if self._canvas:
                self._canvas.setCursor(Qt.ArrowCursor)

    def _on_pick_event(self, event) -> None:
        if not self._exclusion_mode_active:
            return
        if event.artist is None or event.ind is None or len(event.ind) == 0:
            return

        mouse_event = event.mouseevent
        if mouse_event is None:
            return
        is_right_click = (mouse_event.button == 3)

        idx = event.ind[0]
        artist = event.artist
        try:
            xdata = float(artist.get_xdata()[idx])
            ydata = float(artist.get_ydata()[idx])
        except (IndexError, TypeError, ValueError):
            return
        label = artist.get_label() or ""
        if label.startswith("_"):
            return

        y_col = self.edit_y_col.text().strip()

        if is_right_click:
            self._clear_pick_highlight()
            self._prompt_series_exclusion(label, artist, y_col)
            return

        key = (label, round(xdata, 6))
        modifiers = QApplication.keyboardModifiers()
        is_ctrl = bool(modifiers & Qt.ControlModifier)

        if not is_ctrl:
            if key == self._pending_pick_key:
                self._clear_pick_highlight()
                return
            self._clear_pick_highlight()
            self._pending_pick_key = key
            self._pending_picks = [{"key": key, "label": label, "x": xdata, "y": ydata}]
        else:
            if not hasattr(self, "_pending_picks"):
                self._pending_picks = []
            already = any(p["key"] == key for p in self._pending_picks)
            if already:
                self._pending_picks = [p for p in self._pending_picks if p["key"] != key]
            else:
                self._pending_picks.append({"key": key, "label": label, "x": xdata, "y": ydata})

        self._redraw_pick_highlights()

        n = len(self._pending_picks) if hasattr(self, "_pending_picks") else 0
        if n == 0:
            self._show_status("Dataset Filter: nenhum ponto selecionado.")
        elif n == 1:
            p = self._pending_picks[0]
            self._show_status(
                f"Selecionado: {p['label']} @ {p['x']} kW | "
                f"Ctrl+click = adicionar | Enter = confirmar exclusao"
            )
        else:
            self._show_status(
                f"{n} pontos selecionados | Ctrl+click = add/remove | Enter = confirmar exclusao"
            )

    def _redraw_pick_highlights(self) -> None:
        for a in self._highlight_artists:
            try:
                a.remove()
            except Exception:
                pass
        self._highlight_artists = []

        ax = self._current_fig.gca() if self._current_fig else None
        if not ax or not hasattr(self, "_pending_picks"):
            return

        colors = ["#e41a1c", "#ff7f00", "#984ea3", "#4daf4a", "#377eb8"]
        for i, p in enumerate(self._pending_picks):
            c = colors[i % len(colors)]
            h = ax.plot(p["x"], p["y"], "X", markersize=14, markeredgewidth=3,
                        color=c, zorder=99)
            self._highlight_artists.extend(h)
        if self._canvas:
            self._canvas.draw_idle()

    def _resolve_point_timestamp(self, df, label: str, load_kw: float) -> str:
        """Get acquisition end time for a specific point."""
        from datetime import datetime as _dt
        if df is None or "Time_mean_of_windows" not in df.columns:
            return ""
        try:
            plot_type = self.combo_plot_type.currentText()
            series_labels = self._compute_series_labels_for_filter(df, plot_type)
            if series_labels is None:
                return ""
            load_col = pd.to_numeric(df["Load_kW"], errors="coerce").round(6)
            mask = (series_labels == label) & (load_col == round(load_kw, 6))
            match = df[mask]
            if match.empty:
                return ""
            t_mean = pd.to_numeric(match["Time_mean_of_windows"].iloc[0], errors="coerce")
            t_sd = pd.to_numeric(match.get("Time_sd_of_windows", pd.Series(0)).iloc[0], errors="coerce")
            if pd.isna(t_sd):
                t_sd = 0
            t_end = t_mean + t_sd
            if pd.notna(t_end) and t_end > 0:
                dt = _dt.fromtimestamp(t_end / 1e6)
                return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        return ""

    def _confirm_pending_exclusions(self) -> None:
        """Called by Enter key or dedicated button to confirm all pending picks."""
        if not hasattr(self, "_pending_picks") or not self._pending_picks:
            return

        from .point_exclusion import PointExclusion
        from datetime import datetime

        picks = list(self._pending_picks)
        df = self._get_effective_df()

        if len(picks) == 1:
            p = picks[0]
            ts = self._resolve_point_timestamp(df, p["label"], p["x"])
            ts_info = f"\nAquisicao: {ts}" if ts else ""
            reason, ok = QInputDialog.getText(
                self, "Excluir Ponto",
                f"Excluindo: {p['label']} @ {p['x']} kW (y={p['y']:.4g})"
                f"{ts_info}\n\nJustificativa:",
            )
            if not ok or not reason.strip():
                self._show_status("Exclusao cancelada.")
                return
            reasons = {0: reason.strip()}
        else:
            dlg = QDialog(self)
            dlg.setWindowTitle(f"Excluir {len(picks)} pontos")
            dlg.setMinimumWidth(600)
            layout = QVBoxLayout(dlg)
            layout.addWidget(QLabel(
                f"Confirmar exclusao de {len(picks)} pontos.\n"
                "Preencha a justificativa para cada um (ou uma global):"
            ))

            global_edit = QLineEdit()
            global_edit.setPlaceholderText("Justificativa global (aplica a todos)")
            layout.addWidget(global_edit)

            from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Serie", "Load (kW)", "Valor", "Aquisicao", "Justificativa"])
            table.setRowCount(len(picks))
            reason_edits = []
            for i, p in enumerate(picks):
                table.setItem(i, 0, QTableWidgetItem(p["label"]))
                table.setItem(i, 1, QTableWidgetItem(f"{p['x']:.1f}"))
                table.setItem(i, 2, QTableWidgetItem(f"{p['y']:.4g}"))
                ts = self._resolve_point_timestamp(df, p["label"], p["x"])
                table.setItem(i, 3, QTableWidgetItem(ts))
                edit = QLineEdit()
                edit.setPlaceholderText("(usa global)")
                table.setCellWidget(i, 4, edit)
                reason_edits.append(edit)
            layout.addWidget(table)

            btn_row = QHBoxLayout()
            btn_ok = QPushButton("Excluir Todos")
            btn_ok.clicked.connect(dlg.accept)
            btn_cancel = QPushButton("Cancelar")
            btn_cancel.clicked.connect(dlg.reject)
            btn_row.addStretch()
            btn_row.addWidget(btn_ok)
            btn_row.addWidget(btn_cancel)
            layout.addLayout(btn_row)

            if dlg.exec() != QDialog.Accepted:
                self._show_status("Exclusao cancelada.")
                return

            global_reason = global_edit.text().strip()
            reasons = {}
            for i, edit in enumerate(reason_edits):
                r = edit.text().strip() or global_reason
                reasons[i] = r

            if not any(reasons.values()):
                self._show_status("Exclusao cancelada (justificativa obrigatoria).")
                return

        y_col = self.edit_y_col.text().strip()
        df = self._get_effective_df()
        now = datetime.now().isoformat(timespec="seconds")
        store = self._get_exclusion_store()

        series_labels_col = None
        if df is not None and "BaseName" in df.columns:
            from ..runtime.unitary_plots.renderer_all_iterations import (
                _derive_series_column, _build_series_label,
            )
            series_labels_col = _derive_series_column(df).map(_build_series_label)

        for i, p in enumerate(picks):
            reason = reasons.get(i, "")
            if not reason:
                continue
            basename = ""
            if series_labels_col is not None:
                load_col = pd.to_numeric(df["Load_kW"], errors="coerce").round(6)
                match = df[(series_labels_col == p["label"]) & (load_col == round(p["x"], 6))]
                if not match.empty:
                    basename = str(match.iloc[0]["BaseName"])

            exc = PointExclusion(
                series_label=p["label"],
                load_kw=p["x"],
                y_col=y_col,
                basename=basename,
                reason=reason,
                excluded_at=now,
            )
            store.add(exc)

        self._clear_pick_highlight()
        self._pending_picks = []
        self._render_preview()
        self._show_status(f"{len(picks)} ponto(s) excluido(s).")

    def _prompt_series_exclusion(self, label: str, artist, y_col: str) -> None:
        """Exclude an entire series (all points of a dataset)."""
        from .point_exclusion import PointExclusion
        from datetime import datetime

        xdata = artist.get_xdata()
        n_points = len(xdata)

        ax = self._current_fig.gca() if self._current_fig else None
        if ax:
            artist.set_markeredgewidth(3)
            artist.set_markeredgecolor("#FFD700")
            artist.set_zorder(90)
            bg_line, = ax.plot(
                artist.get_xdata(), artist.get_ydata(), "-",
                color="#FFFF00", linewidth=8, alpha=0.4, zorder=1,
            )
            self._highlight_artists.append(bg_line)
            self._canvas.draw_idle()

        source_info = ""
        df = self._get_effective_df()
        if df is not None and "BaseName" in df.columns:
            from ..runtime.unitary_plots.renderer_all_iterations import (
                _derive_series_column, _build_series_label,
            )
            from datetime import datetime as _dt
            series_col = _derive_series_column(df).map(_build_series_label)
            match = df[series_col == label]
            if not match.empty:
                basenames = match["BaseName"].unique()
                if len(basenames) > 0:
                    parts = str(basenames[0]).split("__")
                    folder = " / ".join(parts[:-1]) if len(parts) > 1 else str(basenames[0])
                    source_info = f"\nOrigem: {folder}\nArquivos: {len(match)} pontos"

                if "Time_mean_of_windows" in match.columns:
                    t_mean = pd.to_numeric(match["Time_mean_of_windows"], errors="coerce")
                    t_sd = pd.to_numeric(match.get("Time_sd_of_windows", pd.Series(0, index=match.index)), errors="coerce").fillna(0)
                    t_end = t_mean + t_sd
                    last_acq_us = t_end.max()
                    first_acq_us = (t_mean - t_sd).min()
                    if pd.notna(last_acq_us) and last_acq_us > 0:
                        try:
                            dt_first = _dt.fromtimestamp(first_acq_us / 1e6)
                            dt_last = _dt.fromtimestamp(last_acq_us / 1e6)
                            source_info += (
                                f"\nAquisicao: {dt_first.strftime('%Y-%m-%d %H:%M')} "
                                f"a {dt_last.strftime('%H:%M')}"
                            )
                        except (OSError, ValueError):
                            pass

        reason, ok = QInputDialog.getText(
            self,
            "Excluir Serie Inteira",
            f"Excluindo TODOS os {n_points} pontos de: {label}\n"
            f"{source_info}\n\n"
            f"Justificativa de engenharia (obrigatoria):",
        )
        self._clear_pick_highlight()
        if not ok or not reason.strip():
            self._show_status("Exclusao de serie cancelada.")
            self._render_preview()
            return

        store = self._get_exclusion_store()
        df = self._get_effective_df()
        now = datetime.now().isoformat(timespec="seconds")

        basename_map: Dict[float, str] = {}
        if df is not None and "BaseName" in df.columns:
            from ..runtime.unitary_plots.renderer_all_iterations import (
                _derive_series_column, _build_series_label,
            )
            series_labels_col = _derive_series_column(df).map(_build_series_label)
            load_col = pd.to_numeric(df["Load_kW"], errors="coerce").round(6)
            match_df = df[series_labels_col == label]
            for _, row in match_df.iterrows():
                lkw = round(float(row["Load_kW"]), 6) if pd.notna(row.get("Load_kW")) else None
                if lkw is not None:
                    basename_map[lkw] = str(row["BaseName"])

        batch = []
        for x_val in xdata:
            if not np.isfinite(x_val):
                continue
            batch.append(PointExclusion(
                series_label=label,
                load_kw=float(x_val),
                y_col="*",  # series exclusion applies globally to all metrics
                basename=basename_map.get(round(float(x_val), 6), ""),
                reason=f"[SERIE] {reason.strip()}",
                excluded_at=now,
            ))
        store.add_batch(batch)

        self._render_preview()
        self._show_status(f"Serie excluida: {label} ({n_points} pontos) — {reason.strip()}")

    def _clear_pick_highlight(self) -> None:
        self._pending_pick_key = None
        self._pending_picks = []
        for artist in self._highlight_artists:
            try:
                artist.remove()
            except Exception:
                pass
        self._highlight_artists = []
        if self._canvas:
            self._canvas.draw_idle()

    def _open_exclusions_review(self) -> None:
        store = self._get_exclusion_store()
        if not store.count():
            QMessageBox.information(self, "Exclusions", "Nenhum ponto excluido.")
            return

        dlg = QDialog(self)
        dlg.setMinimumSize(800, 440)
        layout = QVBoxLayout(dlg)

        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QHeaderView

        tree = QTreeWidget()
        tree.setHeaderLabels(["Exclusao", "Razao", "Data", ""])
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tree.header().setSectionResizeMode(3, QHeaderView.Fixed)
        tree.header().resizeSection(3, 80)
        tree.setIndentation(20)

        def _rebuild() -> None:
            tree.clear()
            series_excls = store.series_exclusions()
            point_excls = store.point_exclusions()
            total = store.count()
            dlg.setWindowTitle(f"Point Exclusions ({total} pontos)")

            for se in series_excls:
                n_pts = store.series_point_count(se.series_label)
                reason_text = se.reason.replace("[SERIE] ", "")
                parent = QTreeWidgetItem(tree, [
                    f"{se.series_label} ({n_pts} pontos)",
                    reason_text,
                    se.excluded_at[:10],
                    "",
                ])
                parent.setExpanded(False)
                btn = QPushButton("Restore")
                btn.clicked.connect(lambda checked, lbl=se.series_label: _restore_series(lbl))
                tree.setItemWidget(parent, 3, btn)
                for pt in store.series_points(se.series_label):
                    QTreeWidgetItem(parent, [
                        f"  {pt.load_kw:g} kW",
                        pt.basename,
                        pt.excluded_at,
                        "",
                    ])

            for pe in point_excls:
                item = QTreeWidgetItem(tree, [
                    f"{pe.series_label} @ {pe.load_kw:g} kW",
                    pe.reason,
                    pe.excluded_at,
                    "",
                ])
                btn = QPushButton("Restore")
                btn.clicked.connect(lambda checked, k=pe.key: _restore_one(k))
                tree.setItemWidget(item, 3, btn)

        def _restore_one(key) -> None:
            store.remove(key)
            _rebuild()
            QTimer.singleShot(0, self._render_preview)

        def _restore_series(series_label: str) -> None:
            store.remove_series(series_label)
            _rebuild()
            QTimer.singleShot(0, self._render_preview)

        def _restore_all() -> None:
            if store.count() == 0:
                return
            if QMessageBox.question(
                dlg, "Restore All",
                f"Restaurar TODOS os {store.count()} pontos excluidos?",
                QMessageBox.Yes | QMessageBox.No,
            ) != QMessageBox.Yes:
                return
            store.remove_all()
            _rebuild()
            QTimer.singleShot(0, self._render_preview)

        def _export_list() -> None:
            from dataclasses import asdict
            start_dir = str(self._workspace_file_path().parent)
            path, _ = QFileDialog.getSaveFileName(
                dlg, "Exportar lista de exclusoes", start_dir,
                "JSON (*.json);;All files (*)"
            )
            if not path:
                return
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 3,
                "type": "exclusion_list",
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "exclusions": [asdict(e) for e in store.all_exclusions()],
            }
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self._show_status(f"Exclusions exportadas: {p.name} ({store.count()} entradas)")

        _rebuild()
        layout.addWidget(tree)

        btn_row = QHBoxLayout()
        btn_restore_all = QPushButton("Restore All")
        btn_restore_all.setToolTip("Restaurar todos os pontos excluidos de uma vez")
        btn_restore_all.clicked.connect(_restore_all)
        btn_row.addWidget(btn_restore_all)
        btn_export = QPushButton("Export...")
        btn_export.setToolTip("Exportar lista de exclusoes para arquivo JSON reutilizavel")
        btn_export.clicked.connect(_export_list)
        btn_row.addWidget(btn_export)
        btn_row.addStretch()
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        dlg.exec()
        self._render_preview()

    def _open_series_colors_dialog(self) -> None:
        """Open dialog to customize colors and markers for detected series."""
        df = self._get_effective_df()
        if df is None or df.empty:
            QMessageBox.information(
                self, "Series Colors",
                "Nenhum dado carregado. Carregue um xlsx primeiro.",
            )
            return

        if "BaseName" not in df.columns:
            QMessageBox.information(
                self, "Series Colors",
                "DataFrame nao possui coluna BaseName.\n"
                "Series Colors funciona com dados do lv_kpis_clean.xlsx.",
            )
            return

        from ..runtime.unitary_plots.renderer_all_iterations import (
            _derive_series_column, _build_series_label, _style_for_series,
        )
        series_keys_raw = _derive_series_column(df).unique().tolist()
        series_keys = sorted(set(series_keys_raw))

        initial_styles: Dict[str, Dict[str, str]] = {}
        for key in series_keys:
            if key in self._series_style_overrides:
                initial_styles[key] = self._series_style_overrides[key]
            else:
                color, marker = _style_for_series(key, {})
                initial_styles[key] = {"color": color, "marker": marker}

        labeled_keys = [_build_series_label(k) for k in series_keys]
        label_to_key = dict(zip(labeled_keys, series_keys))
        initial_by_label = {_build_series_label(k): v for k, v in initial_styles.items()}

        dlg = SeriesStyleDialog(labeled_keys, initial_by_label, parent=self)
        if dlg.exec() == QDialog.Accepted:
            styles_by_label = dlg.get_styles()
            if not styles_by_label:
                self._series_style_overrides = {}
            else:
                self._series_style_overrides = {
                    label_to_key[lbl]: style
                    for lbl, style in styles_by_label.items()
                    if lbl in label_to_key
                }
            self._render_preview()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def sync_from_plots_selection(self, row_idx: int) -> None:
        """Called by parent GUI when user selects a row in Plots tab."""
        records = self._get_plots_records()
        if row_idx < 0 or row_idx >= len(records):
            return
        self._save_draft()
        self._selected_plot_idx = row_idx

        self.combo_plot_selector.blockSignals(True)
        if row_idx < self.combo_plot_selector.count():
            self.combo_plot_selector.setCurrentIndex(row_idx)
        self.combo_plot_selector.blockSignals(False)

        self._populate_from_record(self._get_effective_record(row_idx))

    def refresh_plot_selector(self) -> None:
        """Re-populate the plot selector ComboBox when plots config changes."""
        records = self._get_plots_records()
        self._draft_overrides.clear()
        prev_filename = ""
        if 0 <= self._selected_plot_idx < self.combo_plot_selector.count():
            prev_filename = self.combo_plot_selector.itemText(self._selected_plot_idx)
        self.combo_plot_selector.blockSignals(True)
        self.combo_plot_selector.clear()
        new_idx = 0
        for rec in records:
            filename = str(rec.get("filename", rec.get("name", ""))).strip()
            if not filename:
                continue
            self.combo_plot_selector.addItem(filename)
            if filename == prev_filename:
                new_idx = self.combo_plot_selector.count() - 1
        if self.combo_plot_selector.count() > 0:
            self._selected_plot_idx = new_idx
            self.combo_plot_selector.setCurrentIndex(new_idx)
        self.combo_plot_selector.blockSignals(False)

    # ------------------------------------------------------------------
    # Populate controls from a record dict
    # ------------------------------------------------------------------

    def _populate_from_record(self, rec: Dict[str, str]) -> None:
        self._debounce_timer.stop()

        # Save current Y scale, X axis, uncertainty and comment to session before switching
        if self._last_y_col:
            self._session["y_scales"][self._last_y_col] = {
                "y_min": self.edit_y_min.text().strip(),
                "y_max": self.edit_y_max.text().strip(),
                "y_step": self.edit_y_step.text().strip(),
                "x_col": self.edit_x_col.text().strip(),
                "x_min": self.edit_x_min.text().strip(),
                "x_max": self.edit_x_max.text().strip(),
                "x_step": self.edit_x_step.text().strip(),
                "show_uncertainty": "1" if self.chk_show_uncertainty.isChecked() else "0",
            }
            if self._compare_comment_data.get("text"):
                self._session["comments"][self._last_y_col] = dict(self._compare_comment_data)

        self._populating = True

        self.edit_title.setText(str(rec.get("title", "")))

        lock_x = self.chk_lock_x.isChecked()
        current_ptype = self.combo_plot_type.currentText()
        session_mode = self._session.get("active_mode", "")

        if current_ptype in ("all_iterations_yx", "compare_bl_vs_adtv"):
            pass
        elif session_mode and session_mode != str(rec.get("plot_type", "")):
            idx = self.combo_plot_type.findText(session_mode)
            if idx >= 0:
                self.combo_plot_type.setCurrentIndex(idx)
        elif not lock_x:
            ptype = str(rec.get("plot_type", "all_fuels_yx"))
            idx = self.combo_plot_type.findText(ptype)
            if idx >= 0:
                self.combo_plot_type.setCurrentIndex(idx)
            else:
                self.combo_plot_type.setCurrentIndex(0)

        new_y_col = str(rec.get("y_col", "")).strip()
        mem = self._session.get("y_scales", {}).get(new_y_col, {}) if new_y_col else {}

        rec_x_col = mem.get("x_col", "") or str(rec.get("x_col", ""))
        current_lock_x_col = self.edit_x_col.text().strip()
        plot_has_different_x = bool(rec_x_col and current_lock_x_col and rec_x_col != current_lock_x_col)

        if not lock_x or plot_has_different_x:
            self.edit_x_col.setText(rec_x_col)
            self.edit_x_label.setText(str(rec.get("x_label", "")) or rec_x_col)
            self.edit_x_min.setText(mem.get("x_min", "") or str(rec.get("x_min", "")))
            self.edit_x_max.setText(mem.get("x_max", "") or str(rec.get("x_max", "")))
            self.edit_x_step.setText(mem.get("x_step", "") or str(rec.get("x_step", "")))
            self.edit_series_col.setText(str(rec.get("series_col", "")))

        self.edit_y_col.setText(str(rec.get("y_col", "")))
        self.edit_yerr_col.setText(str(rec.get("yerr_col", "")))
        if "show_uncertainty" in mem:
            self.chk_show_uncertainty.setChecked(mem["show_uncertainty"] not in ("0", "false", "no"))
        else:
            show_unc = str(rec.get("show_uncertainty", "1")).strip()
            self.chk_show_uncertainty.setChecked(show_unc not in ("0", "false", "no"))
        self.edit_y_label.setText(str(rec.get("y_label", "")))

        def _clean_nan(v: str) -> str:
            s = str(v).strip().lower()
            return "" if s in ("nan", "none", "inf", "-inf") else str(v)

        rec_y_min = _clean_nan(rec.get("y_min", ""))
        rec_y_max = _clean_nan(rec.get("y_max", ""))
        rec_y_step = _clean_nan(rec.get("y_step", ""))

        if mem.get("y_min") or mem.get("y_max") or mem.get("y_step"):
            self.edit_y_min.setText(mem.get("y_min", ""))
            self.edit_y_max.setText(mem.get("y_max", ""))
            self.edit_y_step.setText(mem.get("y_step", ""))
        elif rec_y_min or rec_y_max or rec_y_step:
            self.edit_y_min.setText(rec_y_min)
            self.edit_y_max.setText(rec_y_max)
            self.edit_y_step.setText(rec_y_step)
        else:
            self.edit_y_min.setText("")
            self.edit_y_max.setText("")
            self.edit_y_step.setText("")

        self._last_y_col = new_y_col

        # Restore comment for new y_col
        self._compare_comment_data = self._session.get("comments", {}).get(new_y_col, _empty_comment_data())

        self.edit_y_tol_plus.setText(_clean_nan(rec.get("y_tol_plus", "")))
        self.edit_y_tol_minus.setText(_clean_nan(rec.get("y_tol_minus", "")))

        self.edit_filter_h2o.setText(str(rec.get("filter_h2o_list", rec.get("filter_h2o", ""))))

        variant = str(rec.get("label_variant", "box"))
        vidx = self.combo_label_variant.findText(variant)
        if vidx >= 0:
            self.combo_label_variant.setCurrentIndex(vidx)

        self._populating = False
        self._render_preview()

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render_preview(self) -> None:
        t0 = time.perf_counter()

        try:
            plot_type = self.combo_plot_type.currentText()

            # Compare mode: independent path — uses _compare_df, not the main df
            if plot_type == "compare_bl_vs_adtv":
                if self._compare_df is None:
                    self._auto_discover_compare_xlsx()
                if self._compare_df is None or self._compare_df.empty:
                    self._show_placeholder(
                        "Compare xlsx nao carregado.\n\n"
                        "Use Browse para carregar\n"
                        "compare_iteracoes_metricas_incertezas.xlsx"
                    )
                    return
                if self._current_fig is not None:
                    plt.close(self._current_fig)
                    self._current_fig = None

                fig = self._render_compare_preview()
                if fig is None:
                    self._show_placeholder("Selecione uma metrica no combo.")
                    return

                self._apply_y_scale_to_fig(fig)
                self._apply_x_scale_to_fig(fig)
                self._apply_comment_to_fig(fig)
                self._current_fig = fig
                self._update_canvas(fig)
                elapsed = time.perf_counter() - t0
                self._show_status(f"Compare rendered in {elapsed:.2f}s")
                self._refresh_thumbnails()
                return

            df = self._get_effective_df()
            if df is None or df.empty:
                self._show_placeholder(
                    "Sem dados para preview.\n\n"
                    "Use Browse para carregar um lv_kpis_clean.xlsx\n"
                    "ou rode Save & Run primeiro."
                )
                self._show_status("Preview: sem dados carregados.")
                return

            title = self.edit_title.text().strip() or "Preview"
            x_col_raw = self.edit_x_col.text().strip() or "Load_kW"
            y_col_raw = self.edit_y_col.text().strip()
            yerr_col_raw = self.edit_yerr_col.text().strip() or None
            if not self.chk_show_uncertainty.isChecked():
                yerr_col_raw = None

            # Resolve columns case-insensitively
            try:
                x_col = resolve_col(df, x_col_raw)
            except (KeyError, Exception) as e:
                self._show_placeholder(f"X col '{x_col_raw}' nao encontrada.\n{e}")
                self._show_status(f"X col nao resolvida: {x_col_raw}")
                return
            try:
                y_col = resolve_col(df, y_col_raw) if y_col_raw else ""
            except (KeyError, Exception) as e:
                self._show_placeholder(f"Y col '{y_col_raw}' nao encontrada.\n{e}")
                self._show_status(f"Y col nao resolvida: {y_col_raw}")
                return
            yerr_col = None
            if yerr_col_raw:
                try:
                    yerr_col = resolve_col(df, yerr_col_raw)
                except (KeyError, Exception):
                    yerr_col = None

            x_label = self.edit_x_label.text().strip() or x_col
            y_label = self.edit_y_label.text().strip() or y_col

            x_min_text = self.edit_x_min.text().strip()
            x_max_text = self.edit_x_max.text().strip()
            x_step_text = self.edit_x_step.text().strip()
            y_min_text = self.edit_y_min.text().strip()
            y_max_text = self.edit_y_max.text().strip()
            y_step_text = self.edit_y_step.text().strip()

            y_tol_plus_text = self.edit_y_tol_plus.text().strip()
            y_tol_minus_text = self.edit_y_tol_minus.text().strip()
            filter_h2o_text = self.edit_filter_h2o.text().strip()
            series_col_raw = self.edit_series_col.text().strip() or None
            label_variant = self.combo_label_variant.currentText()

            if not y_col:
                self._show_placeholder("Preencha ao menos Y col para renderizar.")
                return

            fixed_x = _parse_axis_spec(x_min_text or pd.NA, x_max_text or pd.NA, x_step_text or pd.NA)
            fixed_y = _parse_axis_spec(y_min_text or pd.NA, y_max_text or pd.NA, y_step_text or pd.NA)
            fixed_y_limits = _parse_axis_limits(y_min_text or pd.NA, y_max_text or pd.NA)

            y_tick_step: Optional[float] = None
            if y_step_text and fixed_y is None:
                step_val = _parse_axis_value(y_step_text, default=np.nan)
                if np.isfinite(step_val) and step_val > 0:
                    y_tick_step = step_val

            fuels_override = _parse_csv_list_ints(filter_h2o_text or pd.NA)
            y_tol_plus = _to_float(y_tol_plus_text or 0, 0.0)
            y_tol_minus = _to_float(y_tol_minus_text or 0, 0.0)
            fuel_colors = self._get_fuel_colors()

            series_col = None
            if series_col_raw:
                try:
                    series_col = resolve_col(df, series_col_raw)
                except (KeyError, Exception):
                    series_col = None

            # Skip exclusion filtering when viewing raw source — raw means unfiltered data.
            # Filtering only makes sense in default mode (loaded_df) or excl mode.
            if self._active_source != "raw":
                store = self._get_exclusion_store()
                if store and store.active_keys():
                    from .point_exclusion import apply_exclusions
                    series_labels = self._compute_series_labels_for_filter(df, plot_type)
                    if series_labels is not None:
                        df = apply_exclusions(df, store, series_labels, x_col=x_col, y_col=y_col)

            if self._current_fig is not None:
                plt.close(self._current_fig)
                self._current_fig = None

            fig = self._call_renderer(
                plot_type=plot_type, df=df, x_col=x_col, y_col=y_col,
                yerr_col=yerr_col, title=title, x_label=x_label, y_label=y_label,
                fixed_x=fixed_x, fixed_y=fixed_y, fixed_y_limits=fixed_y_limits,
                y_tick_step=y_tick_step, fuels_override=fuels_override,
                y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
                fuel_colors=fuel_colors, label_variant=label_variant,
                series_col=series_col,
            )

            if fig is None:
                self._show_placeholder("Renderer retornou None (sem dados para plot).")
                self._show_status("Preview: sem curvas geradas.")
                return

            self._apply_comment_to_fig(fig)
            self._current_fig = fig
            self._update_canvas(fig)

            elapsed = time.perf_counter() - t0
            self._show_status(f"Rendered in {elapsed:.2f}s")
            self._refresh_thumbnails()

        except Exception as exc:
            self._show_placeholder(f"Erro no render:\n{exc}")
            self._show_status(f"Preview error: {exc}")

    def _apply_y_scale_to_fig(self, fig: Figure) -> None:
        """Apply Y min/max/step from controls to an already-rendered figure."""
        y_min_text = self.edit_y_min.text().strip()
        y_max_text = self.edit_y_max.text().strip()
        y_step_text = self.edit_y_step.text().strip()
        if not y_min_text and not y_max_text and not y_step_text:
            return
        ax = fig.gca()
        y_min_val = _parse_axis_value(y_min_text, default=np.nan) if y_min_text else np.nan
        y_max_val = _parse_axis_value(y_max_text, default=np.nan) if y_max_text else np.nan
        if np.isfinite(y_min_val) or np.isfinite(y_max_val):
            cur_min, cur_max = ax.get_ylim()
            new_min = y_min_val if np.isfinite(y_min_val) else cur_min
            new_max = y_max_val if np.isfinite(y_max_val) else cur_max
            ax.set_ylim(new_min, new_max)
        if y_step_text:
            step_val = _parse_axis_value(y_step_text, default=np.nan)
            if np.isfinite(step_val) and step_val > 0:
                cur_min, cur_max = ax.get_ylim()
                ticks = np.arange(cur_min, cur_max + step_val * 0.5, step_val)
                ax.set_yticks(ticks)

    def _apply_x_scale_to_fig(self, fig: Figure) -> None:
        """Apply X min/max/step from controls to an already-rendered figure."""
        x_min_text = self.edit_x_min.text().strip()
        x_max_text = self.edit_x_max.text().strip()
        x_step_text = self.edit_x_step.text().strip()
        if not x_min_text and not x_max_text and not x_step_text:
            return
        ax = fig.gca()
        x_min_val = _parse_axis_value(x_min_text, default=np.nan) if x_min_text else np.nan
        x_max_val = _parse_axis_value(x_max_text, default=np.nan) if x_max_text else np.nan
        if np.isfinite(x_min_val) or np.isfinite(x_max_val):
            cur_min, cur_max = ax.get_xlim()
            new_min = x_min_val if np.isfinite(x_min_val) else cur_min
            new_max = x_max_val if np.isfinite(x_max_val) else cur_max
            ax.set_xlim(new_min, new_max)
        if x_step_text:
            step_val = _parse_axis_value(x_step_text, default=np.nan)
            if np.isfinite(step_val) and step_val > 0:
                cur_min, cur_max = ax.get_xlim()
                ticks = np.arange(cur_min, cur_max + step_val * 0.5, step_val)
                ax.set_xticks(ticks)

    def _apply_comment_to_fig(self, fig: Figure) -> None:
        cmt = self._compare_comment_data
        text = cmt.get("text", "").strip()
        if not text:
            return
        pos_key = cmt.get("position", "bottom-left")
        x, y, va, ha = 0.01, 0.01, "bottom", "left"
        for pk, _, px, py, pva, pha in _COMMENT_POSITIONS:
            if pk == pos_key:
                x, y, va, ha = px, py, pva, pha
                break
        fig.text(
            x, y, text,
            fontsize=cmt.get("font_size", 9),
            fontweight="bold" if cmt.get("bold") else "normal",
            style="italic" if cmt.get("italic", True) else "normal",
            color=cmt.get("color", "#333333"),
            alpha=0.9, transform=fig.transFigure, va=va, ha=ha,
        )

    def _call_renderer(self, *, plot_type, df, x_col, y_col, yerr_col, title,
                       x_label, y_label, fixed_x, fixed_y, fixed_y_limits,
                       y_tick_step, fuels_override, y_tol_plus, y_tol_minus,
                       fuel_colors, label_variant, series_col=None) -> Optional[Figure]:
        filename = "__preview__.png"
        common_kwargs: Dict[str, Any] = dict(
            fixed_y=fixed_y, fixed_y_limits=fixed_y_limits, y_tick_step=y_tick_step,
            fixed_x=fixed_x, fuels_override=fuels_override,
            series_col=series_col,
            y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
            fuel_colors=fuel_colors, return_fig=True,
        )

        if plot_type in ("all_fuels_yx", "all_fuels"):
            return plot_all_fuels(
                df, y_col=y_col, yerr_col=yerr_col, title=title,
                filename=filename, y_label=y_label, x_col=x_col,
                x_label=x_label, **common_kwargs,
            )
        elif plot_type in ("all_fuels_xy", "xy"):
            return plot_all_fuels_xy(
                df, x_col=x_col, y_col=y_col, yerr_col=yerr_col, title=title,
                filename=filename, x_label=x_label, y_label=y_label, **common_kwargs,
            )
        elif plot_type in ("all_fuels_labels", "labels"):
            return plot_all_fuels_with_value_labels(
                df, y_col=y_col, title=title, filename=filename, y_label=y_label,
                label_variant=label_variant, x_col=x_col, x_label=x_label, **common_kwargs,
            )
        elif plot_type in ("all_fuels_delta_ref", "delta_ref"):
            y_col_delta = y_col + "_delta" if y_col else ""
            yerr_col_delta = (yerr_col + "_delta") if yerr_col else None
            y_label_delta = y_label + " (delta %)"
            return plot_all_fuels_delta_ref(
                df, y_col=y_col, y_col_delta=y_col_delta, yerr_col=yerr_col,
                yerr_col_delta=yerr_col_delta, title=title, filename=filename,
                y_label=y_label, y_label_delta=y_label_delta, x_col=x_col,
                x_label=x_label, **common_kwargs,
            )
        elif plot_type == "all_iterations_yx":
            return plot_all_iterations(
                df, y_col=y_col, yerr_col=yerr_col, title=title,
                filename=filename, y_label=y_label, x_col=x_col,
                x_label=x_label, style_overrides=self._series_style_overrides,
                **common_kwargs,
            )
        elif plot_type == "compare_bl_vs_adtv":
            return self._render_compare_preview()
        elif plot_type == "kibox_all":
            kibox_col = next((c for c in df.columns if str(c).upper().startswith("KIBOX_")), None)
            if kibox_col is None:
                return None
            effective_y_col = y_col if y_col and y_col in df.columns else kibox_col
            return plot_all_fuels(
                df, y_col=effective_y_col, yerr_col=yerr_col,
                title=title or f"KIBOX: {effective_y_col}", filename=filename,
                y_label=y_label or effective_y_col, x_col=x_col,
                x_label=x_label, **common_kwargs,
            )
        else:
            return plot_all_fuels(
                df, y_col=y_col, yerr_col=yerr_col, title=title,
                filename=filename, y_label=y_label, x_col=x_col,
                x_label=x_label, **common_kwargs,
            )

    # ------------------------------------------------------------------
    # Canvas management
    # ------------------------------------------------------------------

    def _update_canvas(self, fig: Figure) -> None:
        self._placeholder_label.setVisible(False)
        if self._canvas is not None:
            self._right_panel.removeWidget(self._canvas)
            self._canvas.setParent(None)
            self._canvas.deleteLater()
        try:
            fig.tight_layout()
        except (ValueError, RuntimeError):
            pass
        self._canvas = FigureCanvasQTAgg(fig)
        self._canvas.installEventFilter(self)
        sp = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sp.setRetainSizeWhenHidden(False)
        self._canvas.setSizePolicy(sp)
        self._canvas.setMinimumSize(200, 120)
        self._canvas.setMaximumSize(16777215, 16777215)
        self._right_panel.insertWidget(0, self._canvas)
        self._canvas.draw()
        self._canvas.updateGeometry()
        for ax in fig.get_axes():
            for artist in ax.get_children():
                try:
                    artist.set_picker(5)
                except (AttributeError, TypeError):
                    pass
            for container in ax.containers:
                lbl = container.get_label()
                if lbl and not lbl.startswith("_"):
                    try:
                        container[0].set_label(lbl)
                    except (IndexError, AttributeError):
                        pass
        self._canvas.mpl_connect("pick_event", self._on_pick_event)
        self._canvas.mpl_connect("motion_notify_event", self._on_hover_check)
        if self._exclusion_mode_active and not self._cursor_mode_active:
            self._canvas.setCursor(Qt.CrossCursor)
        elif self._cursor_mode_active:
            self._canvas.setCursor(Qt.ArrowCursor)
        if self._cursor_mode_active:
            self._canvas.mpl_connect("button_press_event", self._on_cursor_click)
            self._canvas.mpl_connect("motion_notify_event", self._on_cursor_move)
            ax = fig.gca()
            xlim = ax.get_xlim()
            x_pos = self._cursor_x if xlim[0] <= self._cursor_x <= xlim[1] else (xlim[0] + xlim[1]) / 2
            self._cursor_line = ax.axvline(x_pos, color="red", linestyle="-", linewidth=1.8, zorder=50)
            ylim = ax.get_ylim()
            self._cursor_arrow = ax.annotate(
                "", xy=(x_pos, ylim[0] + (ylim[1] - ylim[0]) * 0.05),
                xytext=(x_pos, ylim[1] - (ylim[1] - ylim[0]) * 0.02),
                arrowprops=dict(arrowstyle="->", color="red", lw=2.0),
                zorder=51,
            )
            self._cursor_x = x_pos
            self._build_snap_grid()
            self._canvas.draw_idle()
            self._update_cursor_table()

    def _show_placeholder(self, message: str) -> None:
        if self._canvas is not None:
            self._right_panel.removeWidget(self._canvas)
            self._canvas.setParent(None)
            self._canvas.deleteLater()
            self._canvas = None
        self._placeholder_label.setText(message)
        self._placeholder_label.setVisible(True)

    # ------------------------------------------------------------------
    # Export single plot
    # ------------------------------------------------------------------

    def _export_current_plot(self) -> None:
        """Save current preview to PNG file."""
        if self._current_fig is None:
            self._show_status("Nenhum plot para exportar.")
            return

        # Default filename from selector
        default_name = "preview_plot.png"
        records = self._get_plots_records()
        if 0 <= self._selected_plot_idx < len(records):
            default_name = records[self._selected_plot_idx].get("filename", default_name)

        start_dir = ""
        if self._get_output_dir:
            try:
                start_dir = str(self._get_output_dir() / "plots")
            except Exception:
                pass

        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar plot", os.path.join(start_dir, default_name),
            "PNG (*.png);;All files (*)"
        )
        if not path:
            return

        try:
            out = Path(path)
            out.parent.mkdir(parents=True, exist_ok=True)
            self._current_fig.savefig(out, dpi=200, bbox_inches="tight")
            self._show_status(f"Plot exportado: {out}")
        except Exception as e:
            self._show_status(f"Erro ao exportar: {e}")

    # ------------------------------------------------------------------
    # Export all plots (batch)
    # ------------------------------------------------------------------

    def _export_all_plots(self) -> None:
        """Export ALL enabled plots using draft overrides + progress bar."""
        self._save_draft()

        df = self._get_effective_df()
        if df is None or df.empty:
            self._show_status("Sem dados para exportar plots.")
            return

        default_dir = ""
        if self._get_output_dir:
            try:
                default_dir = str(self._get_output_dir() / "plots")
                Path(default_dir).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        out_dir = QFileDialog.getExistingDirectory(
            self, "Pasta de destino para plots", default_dir
        )
        if not out_dir:
            return

        plot_dir = Path(out_dir)
        plot_dir.mkdir(parents=True, exist_ok=True)
        records = self._get_plots_records()
        fuel_colors = self._get_fuel_colors()

        total = len(records)
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        QApplication.processEvents()

        generated = 0
        skipped = 0
        for i, base_rec in enumerate(records):
            rec = self._draft_overrides.get(i, base_rec)

            enabled = str(rec.get("enabled", base_rec.get("enabled", "1"))).strip()
            if enabled.lower() in ("0", "false", "no", ""):
                skipped += 1
                self._progress_bar.setValue(i + 1)
                QApplication.processEvents()
                continue

            y_col_raw = str(rec.get("y_col", "")).strip()
            if not y_col_raw:
                skipped += 1
                self._progress_bar.setValue(i + 1)
                QApplication.processEvents()
                continue

            try:
                x_col = resolve_col(df, str(rec.get("x_col", "Load_kW")).strip() or "Load_kW")
                y_col = resolve_col(df, y_col_raw)
            except (KeyError, Exception):
                skipped += 1
                self._progress_bar.setValue(i + 1)
                QApplication.processEvents()
                continue

            show_unc = str(rec.get("show_uncertainty", "1")).strip()
            yerr_raw = str(rec.get("yerr_col", "")).strip()
            yerr_col = None
            if yerr_raw and show_unc not in ("0", "false", "no"):
                try:
                    yerr_col = resolve_col(df, yerr_raw)
                except (KeyError, Exception):
                    pass

            filename = str(rec.get("filename", base_rec.get("filename", f"plot_{i}.png"))).strip()
            title = str(rec.get("title", "")).strip() or filename
            x_label = str(rec.get("x_label", "")).strip() or x_col
            y_label = str(rec.get("y_label", "")).strip() or y_col
            plot_type = str(rec.get("plot_type", "all_fuels_yx")).strip()

            fixed_x = _parse_axis_spec(rec.get("x_min", pd.NA), rec.get("x_max", pd.NA), rec.get("x_step", pd.NA))
            fixed_y = _parse_axis_spec(rec.get("y_min", pd.NA), rec.get("y_max", pd.NA), rec.get("y_step", pd.NA))
            fixed_y_limits = _parse_axis_limits(rec.get("y_min", pd.NA), rec.get("y_max", pd.NA))
            y_tol_plus = _to_float(rec.get("y_tol_plus", 0), 0.0)
            y_tol_minus = _to_float(rec.get("y_tol_minus", 0), 0.0)
            fuels_override = _parse_csv_list_ints(rec.get("filter_h2o_list", pd.NA))

            common_kw = dict(
                fixed_y=fixed_y, fixed_y_limits=fixed_y_limits, y_tick_step=None,
                fixed_x=fixed_x, fuels_override=fuels_override,
                y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
                fuel_colors=fuel_colors, plot_dir=plot_dir, return_fig=False,
            )

            try:
                if plot_type in ("all_fuels_yx", "all_fuels", ""):
                    plot_all_fuels(df, y_col=y_col, yerr_col=yerr_col, title=title,
                                   filename=filename, y_label=y_label, x_col=x_col,
                                   x_label=x_label, **common_kw)
                elif plot_type in ("all_fuels_xy", "xy"):
                    plot_all_fuels_xy(df, x_col=x_col, y_col=y_col, yerr_col=yerr_col,
                                      title=title, filename=filename, x_label=x_label,
                                      y_label=y_label, **common_kw)
                elif plot_type in ("all_fuels_labels", "labels"):
                    lv = str(rec.get("label_variant", "box")).strip() or "box"
                    plot_all_fuels_with_value_labels(df, y_col=y_col, title=title,
                                                     filename=filename, y_label=y_label,
                                                     label_variant=lv, x_col=x_col,
                                                     x_label=x_label, **common_kw)
                elif plot_type in ("all_fuels_delta_ref", "delta_ref"):
                    plot_all_fuels_delta_ref(df, y_col=y_col, y_col_delta=y_col+"_delta",
                                             yerr_col=yerr_col, yerr_col_delta=None,
                                             title=title, filename=filename, y_label=y_label,
                                             y_label_delta=y_label+" (delta %)",
                                             x_col=x_col, x_label=x_label, **common_kw)
                else:
                    plot_all_fuels(df, y_col=y_col, yerr_col=yerr_col, title=title,
                                   filename=filename, y_label=y_label, x_col=x_col,
                                   x_label=x_label, **common_kw)
                generated += 1
            except Exception:
                skipped += 1

            self._progress_bar.setValue(i + 1)
            QApplication.processEvents()

        self._progress_bar.setVisible(False)
        self._show_status(f"Export All: {generated} gerados, {skipped} pulados -> {plot_dir}")

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self) -> None:
        if self._current_fig is None:
            self._show_status("Nenhum plot para copiar.")
            return
        try:
            buf = io.BytesIO()
            self._current_fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
            buf.seek(0)
            image = QImage()
            image.loadFromData(buf.read())
            QApplication.clipboard().setImage(image)
            self._show_status("Plot copiado para o clipboard.")
        except Exception as exc:
            self._show_status(f"Erro ao copiar: {exc}")

    # ------------------------------------------------------------------
    # Apply back to plots tab
    # ------------------------------------------------------------------


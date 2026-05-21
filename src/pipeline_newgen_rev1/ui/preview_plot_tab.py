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
from PySide6.QtGui import QColor, QImage
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
    QSplitter,
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


_PRESET_X_KEYS = ("x_col", "x_label", "x_min", "x_max", "x_step", "series_col")

_PRESET_FULL_KEYS = (
    "x_col", "x_label", "x_min", "x_max", "x_step", "series_col",
    "y_min", "y_max", "y_step", "y_tol_plus", "y_tol_minus",
    "filter_h2o_list", "plot_type", "label_variant",
    "data_path",
)

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


def _load_presets_file(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_presets_file(path: Path, presets: Dict[str, Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8")


_AVAILABLE_MARKERS = [
    ("o", "Circle"), ("s", "Square"), ("D", "Diamond"), ("^", "Triangle up"),
    ("v", "Triangle down"), ("<", "Triangle left"), (">", "Triangle right"),
    ("P", "Plus filled"), ("X", "X filled"), ("*", "Star"), ("h", "Hexagon"),
    ("p", "Pentagon"),
]


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
        self._user_presets: Dict[str, Dict[str, str]] = {}
        self._series_style_overrides: Dict[str, Dict[str, str]] = {}
        self._y_scale_memory: Dict[str, Dict[str, str]] = {}
        self._last_y_col: str = ""
        self._exclusion_mode_active: bool = False
        self._pending_pick_key = None
        self._pending_picks: List[Dict[str, Any]] = []
        self._highlight_artists: List = []
        self._cursor_mode_active: bool = False
        self._cursor_line = None
        self._cursor_arrow = None
        self._cursor_x: float = 0.0
        self._compare_df: Optional[pd.DataFrame] = None
        self._compare_path: Optional[Path] = None

        self._populating = False

        self._setup_ui()
        self._load_presets()
        self._connect_signals()

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._render_preview)

        self._debounce_timer_slow = QTimer(self)
        self._debounce_timer_slow.setSingleShot(True)
        self._debounce_timer_slow.setInterval(700)
        self._debounce_timer_slow.timeout.connect(self._render_preview)

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
        outer_layout.addLayout(data_bar)

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

        # Preset bar
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        self.combo_preset = QComboBox()
        self.combo_preset.setMinimumWidth(140)
        self.combo_preset.setToolTip("Selecionar preset de eixo X")
        preset_row.addWidget(self.combo_preset, 1)
        self.btn_save_preset = QPushButton("Save")
        self.btn_save_preset.setFixedWidth(48)
        self.btn_save_preset.setToolTip("Salvar workspace: arquivo de dados + eixos + escalas atuais")
        preset_row.addWidget(self.btn_save_preset)
        self.btn_del_preset = QPushButton("Del")
        self.btn_del_preset.setFixedWidth(38)
        self.btn_del_preset.setToolTip("Excluir preset selecionado")
        preset_row.addWidget(self.btn_del_preset)
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
        left_form.addRow("Filter H2O:", self.edit_filter_h2o)

        self.edit_series_col = QLineEdit()
        self.edit_series_col.setPlaceholderText("(vazio = agrupar por fuel)")
        self._completer_series = QCompleter([], self)
        self._completer_series.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer_series.setFilterMode(Qt.MatchContains)
        self.edit_series_col.setCompleter(self._completer_series)
        left_form.addRow("Series col:", self.edit_series_col)

        self.combo_label_variant = QComboBox()
        self.combo_label_variant.addItems(["box", "tag", "marker", "badge"])
        left_form.addRow("Label variant:", self.combo_label_variant)

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
        self.btn_apply_back = QPushButton("Apply Back + Save Config")
        self.btn_export_all = QPushButton("Export All Plots")
        btn_row2.addWidget(self.btn_apply_back)
        btn_row2.addWidget(self.btn_export_all)
        btn_widget2 = QWidget()
        btn_widget2.setLayout(btn_row2)
        left_form.addRow(btn_widget2)

        # Saved workspace presets list
        lbl_presets = QLabel("Workspaces salvos (duplo-clique = carregar):")
        lbl_presets.setStyleSheet("font-weight: bold; margin-top: 8px; font-size: 10px;")
        left_form.addRow(lbl_presets)
        self.list_presets = QListWidget()
        self.list_presets.setMaximumHeight(160)
        self.list_presets.setToolTip(
            "Cada workspace salva: arquivo de dados + eixo X + escalas.\n"
            "Duplo-clique carrega tudo de uma vez.\n"
            "Use o botao [Save] acima para criar um workspace."
        )
        left_form.addRow(self.list_presets)

        # Wrap left panel in scroll area
        scroll = QScrollArea()
        scroll.setWidget(left_container)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(280)
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
        self._cursor_table.setFixedWidth(220)
        self._cursor_table.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._cursor_table.verticalHeader().setVisible(False)
        self._cursor_table.setStyleSheet(
            "QTableWidget { font-size: 11px; }"
            "QHeaderView::section { font-size: 11px; font-weight: bold; }"
            "QTableWidget::item { padding: 2px 4px; }"
        )
        self._cursor_table.verticalHeader().setDefaultSectionSize(22)
        self._cursor_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._cursor_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self._cursor_table.setColumnWidth(1, 60)

        right_widget = QWidget()
        right_inner = QHBoxLayout(right_widget)
        right_inner.setContentsMargins(0, 0, 0, 0)
        right_inner.setSpacing(4)

        self._canvas_container = QWidget()
        self._canvas_container.setLayout(self._right_panel)
        self._canvas_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_inner.addWidget(self._canvas_container, 1)
        right_inner.addWidget(self._cursor_table, 0)

        # Splitter: drag to resize left/right panels
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 900])

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

        self.combo_plot_type.currentIndexChanged.connect(self._schedule_render)
        self.combo_label_variant.currentIndexChanged.connect(self._schedule_render)
        self.chk_show_uncertainty.stateChanged.connect(self._schedule_render)
        self.combo_plot_selector.currentIndexChanged.connect(self._on_plot_selected)

        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        self.btn_apply_back.clicked.connect(self._apply_back)
        self.btn_export_plot.clicked.connect(self._export_current_plot)
        self.btn_export_all.clicked.connect(self._export_all_plots)
        self.btn_browse_data.clicked.connect(self._browse_data_file)
        self.btn_reload_data.clicked.connect(self._reload_data)

        self.combo_preset.currentIndexChanged.connect(self._on_preset_selected)
        self.btn_save_preset.clicked.connect(self._save_preset_dialog)
        self.btn_del_preset.clicked.connect(self._delete_preset)
        self.list_presets.itemDoubleClicked.connect(self._on_preset_list_double_click)
        self.btn_series_colors.clicked.connect(self._open_series_colors_dialog)
        self.btn_excl_mode.toggled.connect(self._on_exclusion_mode_toggled)
        self.btn_view_exclusions.clicked.connect(self._open_exclusions_review)
        self.btn_cursor.toggled.connect(self._on_cursor_mode_toggled)
        self.edit_cursor_font.editingFinished.connect(self._on_cursor_font_changed)
        self.combo_y_browse.currentIndexChanged.connect(self._on_y_browse_selected)
        self.combo_compare_metric.currentIndexChanged.connect(self._schedule_render)
        self.combo_compare_pair.currentIndexChanged.connect(self._schedule_render)
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
        self._remember_y_scale()

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
    # Data management
    # ------------------------------------------------------------------

    def _get_effective_df(self) -> pd.DataFrame:
        """Return loaded DataFrame — from explicit file or fallback provider."""
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
        """Load a lv_kpis_clean.xlsx and update the indicator."""
        try:
            df = pd.read_excel(path, engine="calamine")
            self._loaded_df = df
            self._loaded_path = path
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
            self.lbl_data_source.setText(
                f"Dados: {path.name} | {df.shape[0]} rows x {df.shape[1]} cols | {mtime}\n"
                f"{path.parent}"
            )
            self._refresh_column_completers()
            self._show_status(f"Preview data loaded: {path.name} ({df.shape[0]}x{df.shape[1]})")
            return True
        except Exception as e:
            self._show_status(f"Erro ao carregar: {e}")
            return False

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
            self, "Selecionar lv_kpis_clean.xlsx", start_dir,
            "Excel files (*.xlsx);;All files (*)"
        )
        if path:
            self.load_data_from_file(Path(path))
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
    # Presets
    # ------------------------------------------------------------------

    def _presets_file_path(self) -> Path:
        if self._get_config_dir:
            try:
                return self._get_config_dir() / "preview_presets.json"
            except Exception:
                pass
        return Path(os.environ.get("USERPROFILE", Path.home())) / ".pipeline_newgen" / "preview_presets.json"

    def _y_scale_memory_path(self) -> Path:
        return self._presets_file_path().parent / "y_scale_memory.json"

    def _load_y_scale_memory(self) -> None:
        path = self._y_scale_memory_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._y_scale_memory = data
                    font_entry = data.get("__cursor_font_size__", {})
                    if font_entry.get("y_min", ""):
                        self.edit_cursor_font.setText(font_entry["y_min"])
                        self._on_cursor_font_changed()
            except (json.JSONDecodeError, OSError):
                pass

    def _save_y_scale_memory(self) -> None:
        path = self._y_scale_memory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._y_scale_memory, indent=2, ensure_ascii=False), encoding="utf-8")

    def _remember_y_scale(self) -> None:
        """Save current Y scale fields keyed by the current y_col."""
        y_col = self.edit_y_col.text().strip()
        if not y_col:
            return
        y_min = self.edit_y_min.text().strip()
        y_max = self.edit_y_max.text().strip()
        y_step = self.edit_y_step.text().strip()
        if y_min or y_max or y_step:
            self._y_scale_memory[y_col] = {"y_min": y_min, "y_max": y_max, "y_step": y_step}
        elif y_col in self._y_scale_memory:
            del self._y_scale_memory[y_col]
        self._save_y_scale_memory()

    def _recall_y_scale(self, y_col: str) -> None:
        """Load Y scale from memory for a given y_col, if available."""
        mem = self._y_scale_memory.get(y_col, {})
        if mem:
            self.edit_y_min.setText(mem.get("y_min", ""))
            self.edit_y_max.setText(mem.get("y_max", ""))
            self.edit_y_step.setText(mem.get("y_step", ""))

    def _load_presets(self) -> None:
        self._user_presets = _load_presets_file(self._presets_file_path())
        self._load_y_scale_memory()
        self._refresh_preset_combo()
        self._refresh_preset_list()

    def _refresh_preset_combo(self) -> None:
        self.combo_preset.blockSignals(True)
        self.combo_preset.clear()
        self.combo_preset.addItem("(nenhum)")
        # Builtins first (axis templates, no data switch)
        for name in _BUILTIN_PRESETS:
            if name not in self._user_presets:
                self.combo_preset.addItem(f"{name} [template]")
        # User presets (full: data + axis)
        for name in self._user_presets:
            self.combo_preset.addItem(name)
        self.combo_preset.blockSignals(False)

    def _resolve_combo_preset_name(self) -> str:
        """Get the actual preset name from combo text (strips ' [template]' suffix)."""
        text = self.combo_preset.currentText()
        if text.endswith(" [template]"):
            return text[: -len(" [template]")]
        return text

    def _refresh_preset_list(self) -> None:
        """List shows only user-saved presets (with data file)."""
        self.list_presets.clear()
        for name, preset in self._user_presets.items():
            x_col = preset.get("x_col", "")
            data_path = preset.get("data_path", "")
            folder = Path(data_path).parent.name if data_path else "?"
            item = QListWidgetItem(f"{name}  ({x_col})  [{folder}]")
            item.setData(Qt.UserRole, name)
            item.setToolTip(
                f"X: {x_col} | Scale: {preset.get('x_min','')}-{preset.get('x_max','')}:{preset.get('x_step','')}\n"
                f"Data: {data_path}\n"
                f"Duplo-clique para carregar dados + config"
            )
            self.list_presets.addItem(item)

    def _on_preset_selected(self, index: int) -> None:
        if index <= 0 or self._populating:
            return
        name = self._resolve_combo_preset_name()
        self._apply_preset_by_name(name, load_data=True)

    def _on_preset_list_double_click(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.UserRole)
        if name:
            self._apply_preset_by_name(name, load_data=True)

    def _apply_preset_by_name(self, name: str, load_data: bool = True) -> None:
        all_presets = {**_BUILTIN_PRESETS, **self._user_presets}
        preset = all_presets.get(name)
        if not preset:
            return

        # Kill any pending debounce to avoid stale render
        self._debounce_timer.stop()
        self._populating = True

        # Load data file FIRST (synchronous)
        data_loaded = False
        data_path = preset.get("data_path", "").strip()
        if data_path:
            p = Path(data_path)
            if p.exists():
                try:
                    df = pd.read_excel(p, engine="calamine")
                    self._loaded_df = df
                    self._loaded_path = p
                    mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))
                    self.lbl_data_source.setText(
                        f"Dados: {p.name} | {df.shape[0]} rows x {df.shape[1]} cols | {mtime}\n"
                        f"{p.parent}"
                    )
                    self._refresh_column_completers()
                    data_loaded = True
                except Exception:
                    pass
            else:
                self._populating = False
                self._show_status(f"Arquivo do preset nao encontrado: {p.name}")
                self._populating = True

        if not data_loaded and (self._loaded_df is None or self._loaded_df.empty):
            self._populating = False
            self.auto_discover_data()
            self._populating = True

        # Always reset ALL fields to preset values (empty string clears the field)
        self.edit_x_col.setText(preset.get("x_col", ""))
        self.edit_x_label.setText(preset.get("x_label", ""))
        self.edit_x_min.setText(preset.get("x_min", ""))
        self.edit_x_max.setText(preset.get("x_max", ""))
        self.edit_x_step.setText(preset.get("x_step", ""))
        self.edit_series_col.setText(preset.get("series_col", ""))
        self.edit_y_min.setText(preset.get("y_min", ""))
        self.edit_y_max.setText(preset.get("y_max", ""))
        self.edit_y_step.setText(preset.get("y_step", ""))
        self.edit_y_tol_plus.setText(preset.get("y_tol_plus", ""))
        self.edit_y_tol_minus.setText(preset.get("y_tol_minus", ""))
        self.edit_filter_h2o.setText(preset.get("filter_h2o_list", ""))

        pt = preset.get("plot_type", "")
        if pt:
            idx_pt = self.combo_plot_type.findText(pt)
            if idx_pt >= 0:
                self.combo_plot_type.setCurrentIndex(idx_pt)

        lv = preset.get("label_variant", "")
        if lv:
            idx_lv = self.combo_label_variant.findText(lv)
            if idx_lv >= 0:
                self.combo_label_variant.setCurrentIndex(idx_lv)

        series_styles = preset.get("series_styles")
        if isinstance(series_styles, dict):
            self._series_style_overrides = series_styles
        else:
            self._series_style_overrides = {}

        cursor_font = preset.get("cursor_font_size", "").strip()
        if cursor_font:
            self.edit_cursor_font.setText(cursor_font)
            self._on_cursor_font_changed()

        self.chk_lock_x.setChecked(True)

        # Sync combo without re-triggering
        combo_label = name
        if name in _BUILTIN_PRESETS and name not in self._user_presets:
            combo_label = f"{name} [template]"
        idx_combo = self.combo_preset.findText(combo_label)
        if idx_combo >= 0:
            self.combo_preset.blockSignals(True)
            self.combo_preset.setCurrentIndex(idx_combo)
            self.combo_preset.blockSignals(False)

        self._populating = False

        # Force immediate render (not debounced) to avoid timing issues
        self._render_preview()

        msg = f"Preset '{name}' aplicado"
        if data_loaded:
            msg += f" + dados: {Path(data_path).name}"
        elif not data_path:
            msg += " (sem arquivo vinculado — salve o preset com dados abertos)"
        self._show_status(msg)

    def _save_preset_dialog(self) -> None:
        data_file = self._loaded_path
        if not data_file or not data_file.exists():
            QMessageBox.warning(
                self, "Salvar Preset",
                "Nenhum arquivo de dados carregado.\n"
                "Use Browse para carregar um xlsx antes de salvar o preset.",
            )
            return

        default_name = ""
        current_idx = self.combo_preset.currentIndex()
        if current_idx > 0:
            default_name = self.combo_preset.currentText()

        name, ok = QInputDialog.getText(
            self, "Salvar Preset",
            f"Nome do preset (dados: {data_file.name}):",
            text=default_name,
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        preset: Dict[str, Any] = {
            "x_col": self.edit_x_col.text().strip(),
            "x_label": self.edit_x_label.text().strip(),
            "x_min": self.edit_x_min.text().strip(),
            "x_max": self.edit_x_max.text().strip(),
            "x_step": self.edit_x_step.text().strip(),
            "series_col": self.edit_series_col.text().strip(),
            "y_min": self.edit_y_min.text().strip(),
            "y_max": self.edit_y_max.text().strip(),
            "y_step": self.edit_y_step.text().strip(),
            "y_tol_plus": self.edit_y_tol_plus.text().strip(),
            "y_tol_minus": self.edit_y_tol_minus.text().strip(),
            "filter_h2o_list": self.edit_filter_h2o.text().strip(),
            "plot_type": self.combo_plot_type.currentText(),
            "label_variant": self.combo_label_variant.currentText(),
            "cursor_font_size": self.edit_cursor_font.text().strip(),
            "data_path": str(data_file),
        }
        if self._series_style_overrides:
            preset["series_styles"] = self._series_style_overrides
        self._user_presets[name] = preset
        _save_presets_file(self._presets_file_path(), self._user_presets)
        self._refresh_preset_combo()
        self._refresh_preset_list()
        idx = self.combo_preset.findText(name)
        if idx >= 0:
            self.combo_preset.blockSignals(True)
            self.combo_preset.setCurrentIndex(idx)
            self.combo_preset.blockSignals(False)
        self._show_status(f"Preset '{name}' salvo -> {data_file.parent.name}/{data_file.name}")

    def _delete_preset(self) -> None:
        name = self._resolve_combo_preset_name()
        if not name or name == "(nenhum)":
            return
        if name not in self._user_presets:
            QMessageBox.information(
                self, "Preset",
                f"'{name}' e um template de eixo (nao salvo por voce).\n"
                "Use o botao Save para criar um preset completo primeiro.",
            )
            return
        confirm = QMessageBox.question(
            self, "Excluir Preset", f"Excluir preset '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self._user_presets.pop(name, None)
        _save_presets_file(self._presets_file_path(), self._user_presets)
        self._refresh_preset_combo()
        self._refresh_preset_list()
        self._show_status(f"Preset '{name}' excluido.")

    # ------------------------------------------------------------------
    # Cursor Readout
    # ------------------------------------------------------------------

    def _on_cursor_font_changed(self) -> None:
        size = self.edit_cursor_font.text().strip()
        try:
            sz = int(size)
            if sz < 6:
                sz = 6
            if sz > 24:
                sz = 24
        except ValueError:
            sz = 11
        self.edit_cursor_font.setText(str(sz))
        self._cursor_table.setStyleSheet(
            f"QTableWidget {{ font-size: {sz}px; }}"
            f"QHeaderView::section {{ font-size: {sz}px; font-weight: bold; }}"
            "QTableWidget::item { padding: 2px 4px; }"
        )
        self._cursor_table.verticalHeader().setDefaultSectionSize(sz + 11)
        self._y_scale_memory["__cursor_font_size__"] = {"y_min": str(sz), "y_max": "", "y_step": ""}
        self._save_y_scale_memory()
        self._cursor_table.verticalHeader().setDefaultSectionSize(sz + 11)

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

    def _snap_cursor_x(self, raw_x: float) -> float:
        """Snap cursor to nearest actual datapoint X value (uses cache)."""
        if not hasattr(self, "_snap_grid") or not self._snap_grid:
            self._build_snap_grid()
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

        self._cursor_table.setRowCount(len(lines))
        for i, line in enumerate(lines):
            xdata = np.asarray(line.get_xdata(), dtype=float)
            ydata = np.asarray(line.get_ydata(), dtype=float)
            if len(xdata) == 0:
                continue

            # Exact match at snapped X (no interpolation)
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
        self._cursor_table.setHorizontalHeaderLabels(["Serie", f"@ {self._cursor_x:.1f} kW"])

    # ------------------------------------------------------------------
    # Compare Mode
    # ------------------------------------------------------------------

    def _on_plot_type_changed(self, text: str) -> None:
        is_compare = (text == "compare_bl_vs_adtv")
        self.combo_compare_metric.setVisible(is_compare)
        self.combo_compare_pair.setVisible(is_compare)
        if is_compare and self._compare_df is None:
            self._auto_discover_compare_xlsx()

    def _auto_discover_compare_xlsx(self) -> None:
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

    def _load_compare_xlsx(self, path: Path) -> None:
        from ..runtime.compare_iteracoes.preview_renderers import (
            load_compare_xlsx, available_metrics, available_comparacoes,
        )
        try:
            self._compare_df = load_compare_xlsx(path)
            self._compare_path = path
        except Exception as e:
            self._show_status(f"Erro ao carregar compare xlsx: {e}")
            return

        self._populating = True
        self.combo_compare_metric.clear()
        metrics = available_metrics(self._compare_df)
        self.combo_compare_metric.addItems(metrics)

        self.combo_compare_pair.clear()
        pairs = available_comparacoes(self._compare_df)
        self.combo_compare_pair.addItems(pairs)
        self._populating = False

        self._show_status(f"Compare: {path.name} ({len(metrics)} metricas, {len(pairs)} pares)")

    def _render_compare_preview(self) -> Optional[Figure]:
        if self._compare_df is None or self._compare_df.empty:
            return None
        metrica = self.combo_compare_metric.currentText()
        comparacao = self.combo_compare_pair.currentText()
        if not metrica or not comparacao:
            return None

        from ..runtime.compare_iteracoes.preview_renderers import (
            render_compare_absolute_preview,
            render_compare_delta_preview,
        )

        fig_abs = render_compare_absolute_preview(
            self._compare_df, metrica=metrica, comparacao=comparacao,
            include_uncertainty=self.chk_show_uncertainty.isChecked(),
        )
        fig_delta = render_compare_delta_preview(
            self._compare_df, metrica=metrica, comparacao=comparacao,
            include_uncertainty=self.chk_show_uncertainty.isChecked(),
        )

        if fig_abs is None and fig_delta is None:
            return None

        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True,
                                 gridspec_kw={"hspace": 0.3})

        if fig_abs is not None:
            src_ax = fig_abs.gca()
            for line in src_ax.get_lines():
                axes[0].plot(line.get_xdata(), line.get_ydata(),
                             color=line.get_color(), marker=line.get_marker(),
                             linestyle=line.get_linestyle(), linewidth=line.get_linewidth(),
                             markersize=line.get_markersize(), label=line.get_label(),
                             picker=5)
            axes[0].set_xlabel(src_ax.get_xlabel())
            axes[0].set_ylabel(src_ax.get_ylabel())
            axes[0].set_title(src_ax.get_title())
            axes[0].grid(True, which="both", linestyle="--", linewidth=0.5)
            axes[0].legend(loc="best", fontsize=9)
            plt.close(fig_abs)

        if fig_delta is not None:
            src_ax = fig_delta.gca()
            for line in src_ax.get_lines():
                axes[1].plot(line.get_xdata(), line.get_ydata(),
                             color=line.get_color(), marker=line.get_marker(),
                             linestyle=line.get_linestyle(), linewidth=line.get_linewidth(),
                             markersize=line.get_markersize(), label=line.get_label(),
                             picker=5)
            axes[1].set_xlabel(src_ax.get_xlabel())
            axes[1].set_ylabel(src_ax.get_ylabel())
            axes[1].set_title(src_ax.get_title())
            axes[1].grid(True, which="both", linestyle="--", linewidth=0.5)
            axes[1].legend(loc="best", fontsize=9)
            plt.close(fig_delta)

        return fig

    # ------------------------------------------------------------------
    # Y Column Browser
    # ------------------------------------------------------------------

    def _on_y_browse_selected(self, index: int) -> None:
        if index <= 0 or self._populating:
            return
        col_name = self.combo_y_browse.currentText()
        if col_name and col_name != "(browse columns...)":
            self.edit_y_col.setText(col_name)
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
            path = self._presets_file_path().parent / "point_exclusions.json"
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
                y_col=y_col,
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
        from .point_exclusion import ExclusionStore
        store = self._get_exclusion_store()
        exclusions = store.all_exclusions()
        if not exclusions:
            QMessageBox.information(self, "Exclusions", "Nenhum ponto excluido.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Point Exclusions ({len(exclusions)})")
        dlg.setMinimumSize(750, 400)
        layout = QVBoxLayout(dlg)

        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Serie", "Load (kW)", "Detectado em", "Razao", "Data", ""])
        table.setRowCount(len(exclusions))
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        def _restore(key, row):
            store.remove(key)
            table.removeRow(row)
            dlg.setWindowTitle(f"Point Exclusions ({store.count()})")

        for i, exc in enumerate(exclusions):
            table.setItem(i, 0, QTableWidgetItem(exc.series_label))
            table.setItem(i, 1, QTableWidgetItem(f"{exc.load_kw:g}"))
            table.setItem(i, 2, QTableWidgetItem(exc.y_col))
            table.setItem(i, 3, QTableWidgetItem(exc.reason))
            table.setItem(i, 4, QTableWidgetItem(exc.excluded_at))
            btn = QPushButton("Restore")
            btn.clicked.connect(lambda checked, k=exc.key, r=i: _restore(k, r))
            table.setCellWidget(i, 5, btn)

        layout.addWidget(table)
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)
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
        self.combo_plot_selector.blockSignals(True)
        self.combo_plot_selector.clear()
        for rec in records:
            filename = rec.get("filename", rec.get("name", "untitled"))
            self.combo_plot_selector.addItem(filename)
        self.combo_plot_selector.blockSignals(False)

    # ------------------------------------------------------------------
    # Populate controls from a record dict
    # ------------------------------------------------------------------

    def _populate_from_record(self, rec: Dict[str, str]) -> None:
        self._debounce_timer.stop()

        if self._last_y_col:
            self._remember_y_scale()

        self._populating = True

        self.edit_title.setText(str(rec.get("title", "")))

        lock_x = self.chk_lock_x.isChecked()
        current_ptype = self.combo_plot_type.currentText()

        if not (lock_x and current_ptype in ("all_iterations_yx", "compare_bl_vs_adtv")):
            ptype = str(rec.get("plot_type", "all_fuels_yx"))
            idx = self.combo_plot_type.findText(ptype)
            if idx >= 0:
                self.combo_plot_type.setCurrentIndex(idx)
            else:
                self.combo_plot_type.setCurrentIndex(0)

        if not lock_x:
            self.edit_x_col.setText(str(rec.get("x_col", "")))
            self.edit_x_label.setText(str(rec.get("x_label", "")))
            self.edit_x_min.setText(str(rec.get("x_min", "")))
            self.edit_x_max.setText(str(rec.get("x_max", "")))
            self.edit_x_step.setText(str(rec.get("x_step", "")))
            self.edit_series_col.setText(str(rec.get("series_col", "")))

        self.edit_y_col.setText(str(rec.get("y_col", "")))
        self.edit_yerr_col.setText(str(rec.get("yerr_col", "")))
        show_unc = str(rec.get("show_uncertainty", "1")).strip()
        self.chk_show_uncertainty.setChecked(show_unc not in ("0", "false", "no"))
        if not lock_x:
            self.edit_x_label.setText(str(rec.get("x_label", "")))
        self.edit_y_label.setText(str(rec.get("y_label", "")))

        def _clean_nan(v: str) -> str:
            s = str(v).strip().lower()
            return "" if s in ("nan", "none", "inf", "-inf") else str(v)

        rec_y_min = _clean_nan(rec.get("y_min", ""))
        rec_y_max = _clean_nan(rec.get("y_max", ""))
        rec_y_step = _clean_nan(rec.get("y_step", ""))

        new_y_col = str(rec.get("y_col", "")).strip()
        has_explicit_y_scale = bool(rec_y_min or rec_y_max or rec_y_step)

        if has_explicit_y_scale:
            self.edit_y_min.setText(rec_y_min)
            self.edit_y_max.setText(rec_y_max)
            self.edit_y_step.setText(rec_y_step)
        elif new_y_col and new_y_col in self._y_scale_memory:
            mem = self._y_scale_memory[new_y_col]
            self.edit_y_min.setText(mem.get("y_min", ""))
            self.edit_y_max.setText(mem.get("y_max", ""))
            self.edit_y_step.setText(mem.get("y_step", ""))
        else:
            self.edit_y_min.setText("")
            self.edit_y_max.setText("")
            self.edit_y_step.setText("")

        self._last_y_col = new_y_col

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
            plot_type = self.combo_plot_type.currentText()
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

            store = self._get_exclusion_store()
            if store and store.active_keys():
                from .point_exclusion import apply_exclusions
                series_labels = self._compute_series_labels_for_filter(df, plot_type)
                if series_labels is not None:
                    df = apply_exclusions(df, store, series_labels, x_col=x_col)

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

            self._current_fig = fig
            self._update_canvas(fig)

            elapsed = time.perf_counter() - t0
            self._show_status(f"Rendered in {elapsed:.2f}s")

        except Exception as exc:
            self._show_placeholder(f"Erro no render:\n{exc}")
            self._show_status(f"Preview error: {exc}")

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
        self._canvas = FigureCanvasQTAgg(fig)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._right_panel.insertWidget(0, self._canvas)
        self._canvas.draw()
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

    def _apply_back(self) -> None:
        """Apply ALL pending drafts back to the Plots tab config and save to disk."""
        self._save_draft()

        if self._apply_back_callback is None:
            self._show_status("Sem callback de apply back configurado.")
            return

        if not self._draft_overrides:
            self._show_status("Nenhuma alteracao pendente para aplicar.")
            return

        applied = 0
        for idx, values in self._draft_overrides.items():
            stripped = {k: v.strip() for k, v in values.items()}
            self._apply_back_callback(idx, stripped)
            applied += 1

        self._draft_overrides.clear()

        if self._save_config_callback is not None:
            self._save_config_callback()
            self._show_status(f"Aplicados {applied} plot(s) e config salvo no disco.")
        else:
            self._show_status(f"Aplicados {applied} plot(s). Salve manualmente para persistir.")

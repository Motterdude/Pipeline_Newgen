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
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFormLayout,
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

        self._populating = False

        self._setup_ui()
        self._load_presets()
        self._connect_signals()

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._render_preview)

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

        self.edit_yerr_col = QLineEdit()
        self._completer_yerr = QCompleter([], self)
        self._completer_yerr.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer_yerr.setFilterMode(Qt.MatchContains)
        self.edit_yerr_col.setCompleter(self._completer_yerr)
        left_form.addRow("Yerr col:", self.edit_yerr_col)

        self.chk_show_uncertainty = QCheckBox("Show uncertainty bars")
        self.chk_show_uncertainty.setChecked(True)
        left_form.addRow("", self.chk_show_uncertainty)

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

        # -- Right panel (canvas) --
        self._right_panel = QVBoxLayout()
        self._right_panel.setContentsMargins(0, 0, 0, 0)

        self._placeholder_label = QLabel("Aguardando dados...")
        self._placeholder_label.setAlignment(Qt.AlignCenter)
        self._placeholder_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._right_panel.addWidget(self._placeholder_label)

        self._canvas: Optional[FigureCanvasQTAgg] = None

        right_widget = QWidget()
        right_widget.setLayout(self._right_panel)
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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
        line_edits = [
            self.edit_title, self.edit_x_col, self.edit_y_col,
            self.edit_yerr_col, self.edit_x_label, self.edit_y_label,
            self.edit_x_min, self.edit_x_max, self.edit_x_step,
            self.edit_y_min, self.edit_y_max, self.edit_y_step,
            self.edit_y_tol_plus, self.edit_y_tol_minus, self.edit_filter_h2o,
            self.edit_series_col,
        ]
        for le in line_edits:
            le.textChanged.connect(self._schedule_render)

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

    def _schedule_render(self) -> None:
        if self._populating:
            return
        self._debounce_timer.start()

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key_Right:
                self._navigate_next_plot()
                return True
            elif key == Qt.Key_Left:
                self._navigate_prev_plot()
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
        count = self.combo_plot_selector.count()
        if count == 0:
            return
        nxt = (self._selected_plot_idx + 1) % count
        self.combo_plot_selector.setCurrentIndex(nxt)

    def _navigate_prev_plot(self) -> None:
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

    def _load_presets(self) -> None:
        self._user_presets = _load_presets_file(self._presets_file_path())
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
        preset: Dict[str, str] = {
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
            "data_path": str(data_file),
        }
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
        self._populating = True

        self.edit_title.setText(str(rec.get("title", "")))

        ptype = str(rec.get("plot_type", "all_fuels_yx"))
        idx = self.combo_plot_type.findText(ptype)
        if idx >= 0:
            self.combo_plot_type.setCurrentIndex(idx)
        else:
            self.combo_plot_type.setCurrentIndex(0)

        lock_x = self.chk_lock_x.isChecked()

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

        self.edit_y_min.setText(str(rec.get("y_min", "")))
        self.edit_y_max.setText(str(rec.get("y_max", "")))
        self.edit_y_step.setText(str(rec.get("y_step", "")))

        self.edit_y_tol_plus.setText(str(rec.get("y_tol_plus", "")))
        self.edit_y_tol_minus.setText(str(rec.get("y_tol_minus", "")))

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

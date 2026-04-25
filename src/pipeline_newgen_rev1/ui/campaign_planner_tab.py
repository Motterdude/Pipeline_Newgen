"""Campaign Planner tab — scan input structure and configure comparisons.

Replaces the hardcoded Compare tab with a dynamic, data-driven panel that
works for both Stellantis campaigns (baseline/aditivado × subida/descida)
and thesis data (fuel percentages, no directions).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ComparisonPairRow(QWidget):
    def __init__(self, labels: List[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.left_combo = QComboBox()
        self.right_combo = QComboBox()
        for combo in (self.left_combo, self.right_combo):
            combo.addItems(labels)
        if len(labels) >= 2:
            self.right_combo.setCurrentIndex(1)
        row.addWidget(QLabel("Esquerda:"))
        row.addWidget(self.left_combo, 1)
        row.addWidget(QLabel("Direita:"))
        row.addWidget(self.right_combo, 1)
        self.btn_remove = QPushButton("-")
        self.btn_remove.setFixedWidth(30)
        row.addWidget(self.btn_remove)

    def pair(self) -> Tuple[str, str]:
        return (self.left_combo.currentText(), self.right_combo.currentText())


class CampaignPlannerTab(QWidget):
    def __init__(
        self,
        get_raw_input_dir: Callable[[], Path],
        status_callback: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_raw_input_dir = get_raw_input_dir
        self._show_status = status_callback or (lambda s: None)
        self._catalog: Any = None
        self._group_checks: Dict[str, QCheckBox] = {}
        self._pair_rows: List[ComparisonPairRow] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # -- Scan section
        scan_row = QHBoxLayout()
        self.btn_scan = QPushButton("Escanear Pasta de Entrada")
        self.btn_scan.clicked.connect(self._run_scan)
        scan_row.addWidget(self.btn_scan)
        scan_row.addStretch(1)
        outer.addLayout(scan_row)

        self.lbl_structure = QLabel("Estrutura: (clique Escanear)")
        self.lbl_structure.setWordWrap(True)
        outer.addWidget(self.lbl_structure)

        # -- Mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Modo:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Auto", "Por combustivel", "Por campanha"])
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.combo_mode)
        mode_row.addStretch(1)
        outer.addLayout(mode_row)

        # -- Groups section
        self.groups_box = QGroupBox("Grupos detectados")
        self.groups_layout = QVBoxLayout(self.groups_box)
        self.groups_layout.setSpacing(4)
        outer.addWidget(self.groups_box)

        # -- Comparison pairs
        self.pairs_box = QGroupBox("Pares de comparacao (delta)")
        pairs_outer = QVBoxLayout(self.pairs_box)
        self.pairs_container = QVBoxLayout()
        pairs_outer.addLayout(self.pairs_container)
        btn_row = QHBoxLayout()
        self.btn_add_pair = QPushButton("+ Adicionar par")
        self.btn_add_pair.clicked.connect(self._add_pair_row)
        btn_row.addWidget(self.btn_add_pair)
        btn_row.addStretch(1)
        pairs_outer.addLayout(btn_row)
        outer.addWidget(self.pairs_box)

        # -- Aggregation
        agg_row = QHBoxLayout()
        agg_row.addWidget(QLabel("Agregacao:"))
        self.combo_agg = QComboBox()
        self.combo_agg.addItems(["Media", "Individual", "Media com subida/descida"])
        agg_row.addWidget(self.combo_agg)
        agg_row.addStretch(1)
        outer.addLayout(agg_row)

        # -- Plot families
        self.plots_box = QGroupBox("Familias de plots")
        plots_layout = QVBoxLayout(self.plots_box)
        self.chk_unitary = QCheckBox("Unitarios por grupo (cada combustivel nos mesmos eixos)")
        self.chk_delta = QCheckBox("Delta entre pares (% diferenca)")
        self.chk_absolute = QCheckBox("Valores absolutos sobrepostos")
        self.chk_individual = QCheckBox("Iteracoes individuais (sem media)")
        self.chk_unitary.setChecked(True)
        self.chk_delta.setChecked(True)
        self.chk_absolute.setChecked(True)
        for chk in (self.chk_unitary, self.chk_delta, self.chk_absolute, self.chk_individual):
            plots_layout.addWidget(chk)
        outer.addWidget(self.plots_box)

        outer.addStretch(1)

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _run_scan(self) -> None:
        raw_dir = self._get_raw_input_dir()
        if not raw_dir.is_dir():
            self._show_status(f"Pasta nao encontrada: {raw_dir}")
            return

        from ..adapters import discover_runtime_inputs
        from ..runtime.campaign_scan import scan_campaign_structure

        discovery = discover_runtime_inputs(raw_dir)
        self._catalog = scan_campaign_structure(discovery)
        self._populate_from_catalog()
        self._show_status(
            f"Scan: {self._catalog.total_files} arquivos, "
            f"modo={self._catalog.iteration_mode}, "
            f"{len(self._catalog.fuel_labels)} combustiveis"
        )

    def _populate_from_catalog(self) -> None:
        cat = self._catalog
        if cat is None:
            return

        parts = []
        if cat.fuel_labels:
            parts.append(f"{len(cat.fuel_labels)} combustiveis ({', '.join(cat.fuel_labels)})")
        if cat.load_points:
            pts = ", ".join(str(int(lp)) if lp == int(lp) else str(lp) for lp in cat.load_points)
            parts.append(f"{len(cat.load_points)} pontos de carga ({pts} kW)")
        if cat.directions:
            parts.append(f"Direcoes: {', '.join(cat.directions)}")
        if cat.campaigns:
            parts.append(f"Campanhas: {', '.join(cat.campaigns)}")
        parts.append(f"Modo: {cat.iteration_mode}")
        parts.append(f"Total: {cat.total_files} arquivos")
        self.lbl_structure.setText("Estrutura detectada: " + " | ".join(parts))

        if cat.iteration_mode == "fuel":
            self.combo_mode.setCurrentIndex(1)
        elif cat.iteration_mode == "direction":
            self.combo_mode.setCurrentIndex(2)
        else:
            self.combo_mode.setCurrentIndex(0)

        self._rebuild_groups()
        self._rebuild_default_pairs()

    def _rebuild_groups(self) -> None:
        while self.groups_layout.count():
            item = self.groups_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._group_checks.clear()

        cat = self._catalog
        if cat is None:
            return

        labels = cat.fuel_labels if cat.iteration_mode == "fuel" else cat.campaigns
        counts = cat.file_count_by_fuel if cat.iteration_mode == "fuel" else cat.file_count_by_campaign
        for label in labels:
            n = counts.get(label, 0)
            chk = QCheckBox(f"{label}  ({n} arquivos)", self.groups_box)
            chk.setChecked(True)
            self.groups_layout.addWidget(chk)
            self._group_checks[label] = chk

    def _rebuild_default_pairs(self) -> None:
        for row in self._pair_rows:
            row.setParent(None)
            row.deleteLater()
        self._pair_rows.clear()

        cat = self._catalog
        if cat is None:
            return

        from ..runtime.campaign_scan import default_comparison_pairs
        pairs = default_comparison_pairs(cat)
        for left, right in pairs:
            self._add_pair_row_with_values(left, right)

    def _on_mode_changed(self, index: int) -> None:
        pass

    # ------------------------------------------------------------------
    # Comparison pairs
    # ------------------------------------------------------------------

    def _available_series_labels(self) -> List[str]:
        cat = self._catalog
        if cat is None:
            return []
        if cat.iteration_mode == "fuel":
            return list(cat.fuel_labels)
        labels = []
        for camp in cat.campaigns:
            for d in (cat.directions or [""]):
                lbl = f"{camp}_{d}" if d else camp
                labels.append(lbl)
            if cat.directions:
                labels.append(f"{camp}_media")
        return labels

    def _add_pair_row(self) -> None:
        labels = self._available_series_labels()
        if len(labels) < 2:
            return
        row = ComparisonPairRow(labels, parent=self.pairs_box)
        row.btn_remove.clicked.connect(lambda: self._remove_pair_row(row))
        self.pairs_container.addWidget(row)
        self._pair_rows.append(row)

    def _add_pair_row_with_values(self, left: str, right: str) -> None:
        labels = self._available_series_labels()
        if len(labels) < 2:
            return
        row = ComparisonPairRow(labels, parent=self.pairs_box)
        row.btn_remove.clicked.connect(lambda: self._remove_pair_row(row))
        idx_left = row.left_combo.findText(left)
        idx_right = row.right_combo.findText(right)
        if idx_left >= 0:
            row.left_combo.setCurrentIndex(idx_left)
        if idx_right >= 0:
            row.right_combo.setCurrentIndex(idx_right)
        self.pairs_container.addWidget(row)
        self._pair_rows.append(row)

    def _remove_pair_row(self, row: ComparisonPairRow) -> None:
        if row in self._pair_rows:
            self._pair_rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    # ------------------------------------------------------------------
    # Public API for save
    # ------------------------------------------------------------------

    @property
    def catalog(self) -> Any:
        return self._catalog

    def selected_groups(self) -> List[str]:
        return [label for label, chk in self._group_checks.items() if chk.isChecked()]

    def comparison_pairs(self) -> List[Tuple[str, str]]:
        return [row.pair() for row in self._pair_rows]

    def aggregation_mode(self) -> str:
        idx = self.combo_agg.currentIndex()
        return ["media", "individual", "media_subida_descida"][idx]

    def plot_families(self) -> Dict[str, bool]:
        return {
            "unitary": self.chk_unitary.isChecked(),
            "delta": self.chk_delta.isChecked(),
            "absolute": self.chk_absolute.isChecked(),
            "individual": self.chk_individual.isChecked(),
        }

    def campaign_planner_state(self) -> Dict[str, Any]:
        return {
            "groups": self.selected_groups(),
            "pairs": self.comparison_pairs(),
            "aggregation": self.aggregation_mode(),
            "plot_families": self.plot_families(),
            "iteration_mode": self._catalog.iteration_mode if self._catalog else None,
        }

    # ------------------------------------------------------------------
    # Load from saved state
    # ------------------------------------------------------------------

    def load_compare_checkboxes(
        self,
        *,
        enable_unitary: bool = True,
        enable_up: bool = True,
        enable_down: bool = True,
        enable_mean: bool = True,
    ) -> None:
        self.chk_unitary.setChecked(enable_unitary)
        self.chk_delta.setChecked(enable_up or enable_down or enable_mean)
        self.chk_absolute.setChecked(enable_up or enable_down)

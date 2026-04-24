from __future__ import annotations

from typing import Dict

from ..models import normalize_workflow_mode
from ..workflows.load_sweep.feature_flags import LOAD_SWEEP_FEATURE_SPECS, merge_feature_selection

try:
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QDialog,
        QDialogButtonBox,
        QLabel,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )
except Exception:
    QApplication = None
    QCheckBox = None
    QDialog = object
    QDialogButtonBox = None
    QLabel = None
    QScrollArea = None
    QVBoxLayout = None
    QWidget = None


class LoadSweepFeatureDialog(QDialog if QDialog is not object else object):
    def __init__(self, *, mode: object, selection: Dict[str, bool] | None = None) -> None:
        if QApplication is None or QDialogButtonBox is None:
            raise RuntimeError("PySide6 is not available for the load/sweep feature dialog.")
        super().__init__()
        self.mode = normalize_workflow_mode(mode)
        self.setWindowTitle(f"Pipeline_newgen_rev1 - {self.mode} features")
        self.resize(760, 620)
        self._checkboxes: Dict[str, QCheckBox] = {}
        merged = merge_feature_selection(self.mode, selection)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Each checkbox controls one migrated feature from the legacy load/sweep flow. "
            "Sweep-only features default to off in load mode so they do not interfere with the pipeline29 behavior."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        content_widget = QWidget(self)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(10)

        for spec in LOAD_SWEEP_FEATURE_SPECS:
            checkbox = QCheckBox(f"{spec.label} [{spec.stage}]", content_widget)
            checkbox.setChecked(bool(merged.get(spec.key, False)))
            checkbox.setToolTip(spec.description)
            content_layout.addWidget(checkbox)

            desc = QLabel(spec.description, content_widget)
            desc.setWordWrap(True)
            content_layout.addWidget(desc)

            self._checkboxes[spec.key] = checkbox

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selection(self) -> Dict[str, bool]:
        return {key: bool(box.isChecked()) for key, box in self._checkboxes.items()}


from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget


@dataclass(frozen=True)
class PlotSelection:
    x_col: str
    y_col: str
    y_err_col: str = ""


class ControlsPanel(QWidget):
    """Top controls row: X/Y selection.

    - Dropdowns are disabled until columns are set.
    - Emits `selection_changed` whenever X or Y changes.
    """

    selection_changed = pyqtSignal(object)  # emits PlotSelection

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 0)

        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        self.y_err_combo = QComboBox()
        self.x_combo.setEnabled(False)
        self.y_combo.setEnabled(False)
        self.y_err_combo.setEnabled(False)

        layout.addWidget(QLabel("X:"))
        layout.addWidget(self.x_combo, 1)
        layout.addWidget(QLabel("Y:"))
        layout.addWidget(self.y_combo, 1)
        layout.addWidget(QLabel("Y Err:"))
        layout.addWidget(self.y_err_combo, 1)
        layout.addStretch(1)

        self.x_combo.currentIndexChanged.connect(self._emit_selection)  # type: ignore[attr-defined]
        self.y_combo.currentIndexChanged.connect(self._emit_selection)  # type: ignore[attr-defined]
        self.y_err_combo.currentIndexChanged.connect(self._emit_selection)  # type: ignore[attr-defined]

    def set_columns(self, all_cols: Sequence[str], numeric_cols: Sequence[str]) -> PlotSelection:
        cols = [str(c) for c in all_cols]
        nums = [str(c) for c in numeric_cols]

        self.x_combo.blockSignals(True)
        self.y_combo.blockSignals(True)
        self.y_err_combo.blockSignals(True)
        try:
            self.x_combo.clear()
            self.y_combo.clear()
            self.y_err_combo.clear()
            self.x_combo.addItems(cols)
            self.y_combo.addItems(cols)
            self.y_err_combo.addItem("")
            self.y_err_combo.addItems(cols)

            x_default = ""
            y_default = ""
            if len(nums) >= 2:
                x_default, y_default = nums[0], nums[1]
            else:
                padded = cols + ["", ""]
                x_default, y_default = padded[0], padded[1]

            if x_default:
                self.x_combo.setCurrentText(x_default)
            if y_default:
                self.y_combo.setCurrentText(y_default)
        finally:
            self.x_combo.blockSignals(False)
            self.y_combo.blockSignals(False)
            self.y_err_combo.blockSignals(False)

        self.x_combo.setEnabled(True)
        self.y_combo.setEnabled(True)
        self.y_err_combo.setEnabled(True)

        sel = self.get_selection()
        self.selection_changed.emit(sel)
        return sel

    def set_selection(self, x_col: str, y_col: str, y_err_col: str = "") -> PlotSelection:
        """Programmatically set X/Y/(optional) Y-error selection without emitting intermediate signals.

        Returns the resulting PlotSelection and emits a single `selection_changed`.
        """
        self.x_combo.blockSignals(True)
        self.y_combo.blockSignals(True)
        self.y_err_combo.blockSignals(True)
        try:
            if x_col:
                self.x_combo.setCurrentText(str(x_col))
            if y_col:
                self.y_combo.setCurrentText(str(y_col))
            self.y_err_combo.setCurrentText(str(y_err_col or ""))
        finally:
            self.x_combo.blockSignals(False)
            self.y_combo.blockSignals(False)
            self.y_err_combo.blockSignals(False)

        sel = self.get_selection()
        if sel.x_col and sel.y_col:
            self.selection_changed.emit(sel)
        return sel

    def get_selection(self) -> PlotSelection:
        return PlotSelection(
            x_col=self.x_combo.currentText().strip(),
            y_col=self.y_combo.currentText().strip(),
            y_err_col=self.y_err_combo.currentText().strip(),
        )

    def set_enabled(self, enabled: bool) -> None:
        self.x_combo.setEnabled(enabled)
        self.y_combo.setEnabled(enabled)
        self.y_err_combo.setEnabled(enabled)

    def _emit_selection(self) -> None:
        sel = self.get_selection()
        if not sel.x_col or not sel.y_col:
            return
        self.selection_changed.emit(sel)
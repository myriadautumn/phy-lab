

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QWidget,
)


@dataclass(frozen=True)
class PlotSelection:
    x_col: str
    y_col: str
    mode: str  # "line" or "scatter"


class ControlsPanel(QWidget):
    """Top controls row: X/Y selection + plot mode.

    - Dropdowns are disabled until columns are set.
    - Emits `selection_changed` whenever X, Y, or mode changes.
    """

    selection_changed = pyqtSignal(object)  # emits PlotSelection

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 0)

        self.x_combo = QComboBox()
        self.y_combo = QComboBox()
        self.x_combo.setEnabled(False)
        self.y_combo.setEnabled(False)

        layout.addWidget(QLabel("X:"))
        layout.addWidget(self.x_combo, 1)
        layout.addWidget(QLabel("Y:"))
        layout.addWidget(self.y_combo, 1)

        self.mode_group = QButtonGroup(self)
        self.line_radio = QRadioButton("Line")
        self.scatter_radio = QRadioButton("Scatter")
        self.line_radio.setChecked(True)
        self.mode_group.addButton(self.line_radio)
        self.mode_group.addButton(self.scatter_radio)

        layout.addWidget(self.line_radio)
        layout.addWidget(self.scatter_radio)
        layout.addStretch(1)

        # Wire events
        self.x_combo.currentIndexChanged.connect(self._emit_selection)  # type: ignore[attr-defined]
        self.y_combo.currentIndexChanged.connect(self._emit_selection)  # type: ignore[attr-defined]
        self.line_radio.toggled.connect(self._emit_selection)  # type: ignore[attr-defined]

    def set_columns(
        self,
        all_cols: Sequence[str],
        numeric_cols: Sequence[str],
    ) -> PlotSelection:
        """Populate dropdowns and pick defaults.

        Defaults:
        - Prefer first two numeric columns if available.
        - Otherwise, use the first two columns.

        Returns the resulting selection.
        """
        cols = [str(c) for c in all_cols]
        nums = [str(c) for c in numeric_cols]

        self.x_combo.blockSignals(True)
        self.y_combo.blockSignals(True)
        try:
            self.x_combo.clear()
            self.y_combo.clear()
            self.x_combo.addItems(cols)
            self.y_combo.addItems(cols)

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

        self.x_combo.setEnabled(True)
        self.y_combo.setEnabled(True)

        selection = self.get_selection()
        self.selection_changed.emit(selection)
        return selection

    def get_selection(self) -> PlotSelection:
        x = self.x_combo.currentText().strip()
        y = self.y_combo.currentText().strip()
        mode = "scatter" if self.scatter_radio.isChecked() else "line"
        return PlotSelection(x_col=x, y_col=y, mode=mode)

    def set_enabled(self, enabled: bool) -> None:
        self.x_combo.setEnabled(enabled)
        self.y_combo.setEnabled(enabled)

    def _emit_selection(self) -> None:
        # Guard against emitting empty selections during init.
        sel = self.get_selection()
        if not sel.x_col or not sel.y_col:
            return
        self.selection_changed.emit(sel)
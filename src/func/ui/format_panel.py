from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from func.models.plot_format import AxisLimits, PlotFormat


class FormatPanel(QWidget):
    """Format controls (plot formatting; excludes export formatting)."""

    format_changed = pyqtSignal(object)  # emits PlotFormat
    overlay_toggled = pyqtSignal(bool)
    add_curve_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._updating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 0, 8, 8)
        root.setSpacing(8)

        # --- Mode & Style ---
        style_box = QGroupBox("Style")
        style_layout = QFormLayout(style_box)

        mode_row = QWidget()
        mode_row_layout = QHBoxLayout(mode_row)
        mode_row_layout.setContentsMargins(0, 0, 0, 0)

        self.mode_group = QButtonGroup(self)
        self.line_radio = QRadioButton("Line")
        self.scatter_radio = QRadioButton("Scatter")
        self.line_radio.setChecked(True)
        self.mode_group.addButton(self.line_radio)
        self.mode_group.addButton(self.scatter_radio)

        mode_row_layout.addWidget(self.line_radio)
        mode_row_layout.addWidget(self.scatter_radio)
        mode_row_layout.addStretch(1)
        style_layout.addRow("Mode", mode_row)

        self.sort_by_x_chk = QCheckBox("Sort by X (line plots)")
        self.sort_by_x_chk.setChecked(True)
        style_layout.addRow("", self.sort_by_x_chk)

        self.line_width_spin = QSpinBox()
        self.line_width_spin.setRange(0, 20)
        self.line_width_spin.setValue(0)  # 0 = auto
        self.line_width_spin.setToolTip("0 = auto/default")
        style_layout.addRow("Line width", self.line_width_spin)

        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setRange(1, 30)
        self.marker_size_spin.setValue(5)
        style_layout.addRow("Marker size", self.marker_size_spin)

        # Multi-curve controls (state lives in AppState; panel emits events)
        self.overlay_chk = QCheckBox("Overlay (keep existing curves)")
        self.overlay_chk.setChecked(True)
        style_layout.addRow("", self.overlay_chk)

        self.add_curve_btn = QPushButton("Add Curve")
        self.add_curve_btn.setToolTip("Add the current X/Y as a new curve (used when Overlay is enabled).")
        style_layout.addRow("", self.add_curve_btn)

        # Curve color
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Auto", "b", "r", "g", "m", "c", "y", "k"])
        style_layout.addRow("Curve color", self.color_combo)

        # Curve symbol
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["Auto", "o", "s", "t", "d", "+", "x"])
        style_layout.addRow("Curve symbol", self.symbol_combo)

        root.addWidget(style_box)

        # --- Text ---
        text_box = QGroupBox("Text")
        text_layout = QFormLayout(text_box)

        self.title_enabled = QCheckBox("Enable")
        self.title_edit = QLineEdit()
        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.addWidget(self.title_enabled)
        title_row_layout.addWidget(self.title_edit, 1)
        text_layout.addRow("Title", title_row)

        self.x_label_enabled = QCheckBox("Override")
        self.x_label_edit = QLineEdit()
        xlab_row = QWidget()
        xlab_row_layout = QHBoxLayout(xlab_row)
        xlab_row_layout.setContentsMargins(0, 0, 0, 0)
        xlab_row_layout.addWidget(self.x_label_enabled)
        xlab_row_layout.addWidget(self.x_label_edit, 1)
        text_layout.addRow("X label", xlab_row)

        self.y_label_enabled = QCheckBox("Override")
        self.y_label_edit = QLineEdit()
        ylab_row = QWidget()
        ylab_row_layout = QHBoxLayout(ylab_row)
        ylab_row_layout.setContentsMargins(0, 0, 0, 0)
        ylab_row_layout.addWidget(self.y_label_enabled)
        ylab_row_layout.addWidget(self.y_label_edit, 1)
        text_layout.addRow("Y label", ylab_row)

        root.addWidget(text_box)

        # --- Axes ---
        axes_box = QGroupBox("Axes")
        axes_layout = QFormLayout(axes_box)

        self.grid_chk = QCheckBox("Show grid")
        self.grid_chk.setChecked(True)
        axes_layout.addRow("", self.grid_chk)

        self.legend_chk = QCheckBox("Show legend")
        self.legend_chk.setChecked(False)
        axes_layout.addRow("", self.legend_chk)

        self.x_scale_combo = QComboBox()
        self.x_scale_combo.addItems(["linear", "log"])
        axes_layout.addRow("X scale", self.x_scale_combo)

        self.y_scale_combo = QComboBox()
        self.y_scale_combo.addItems(["linear", "log"])
        axes_layout.addRow("Y scale", self.y_scale_combo)

        # Limits
        self.x_auto_chk = QCheckBox("Auto")
        self.x_auto_chk.setChecked(True)
        self.x_min_edit = QLineEdit()
        self.x_max_edit = QLineEdit()
        self._apply_double_validator(self.x_min_edit)
        self._apply_double_validator(self.x_max_edit)
        xlim_row = self._limits_row(self.x_auto_chk, self.x_min_edit, self.x_max_edit)
        axes_layout.addRow("X limits", xlim_row)

        self.y_auto_chk = QCheckBox("Auto")
        self.y_auto_chk.setChecked(True)
        self.y_min_edit = QLineEdit()
        self.y_max_edit = QLineEdit()
        self._apply_double_validator(self.y_min_edit)
        self._apply_double_validator(self.y_max_edit)
        ylim_row = self._limits_row(self.y_auto_chk, self.y_min_edit, self.y_max_edit)
        axes_layout.addRow("Y limits", ylim_row)

        root.addWidget(axes_box)

        # Wire events to emit
        for w in [
            self.line_radio,
            self.scatter_radio,
            self.sort_by_x_chk,
            self.line_width_spin,
            self.marker_size_spin,
            self.title_enabled,
            self.title_edit,
            self.x_label_enabled,
            self.x_label_edit,
            self.y_label_enabled,
            self.y_label_edit,
            self.grid_chk,
            self.legend_chk,
            self.x_scale_combo,
            self.y_scale_combo,
            self.x_auto_chk,
            self.x_min_edit,
            self.x_max_edit,
            self.y_auto_chk,
            self.y_min_edit,
            self.y_max_edit,
        ]:
            self._connect_change(w)

        # Multi-curve events
        self.overlay_chk.toggled.connect(self.overlay_toggled.emit)  # type: ignore[attr-defined]
        self.add_curve_btn.clicked.connect(self.add_curve_requested.emit)  # type: ignore[attr-defined]

        self.color_combo.currentIndexChanged.connect(self._emit_format)  # type: ignore
        self.symbol_combo.currentIndexChanged.connect(self._emit_format)  # type: ignore

        # Ensure mode selection affects the curve added
        self.mode_group.buttonToggled.connect(lambda b, checked: self._update_mode())

        # Keep min/max disabled when Auto is checked
        self.x_auto_chk.toggled.connect(self._sync_limits_enabled)  # type: ignore[attr-defined]
        self.y_auto_chk.toggled.connect(self._sync_limits_enabled)  # type: ignore[attr-defined]
        self._sync_limits_enabled()

    def _apply_double_validator(self, edit: QLineEdit) -> None:
        # Accept empty string; validator helps prevent non-numeric input.
        edit.setValidator(QDoubleValidator())
        edit.setPlaceholderText("min / max")

    def _limits_row(self, auto_chk: QCheckBox, min_edit: QLineEdit, max_edit: QLineEdit) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(auto_chk)
        lay.addWidget(QLabel("min"))
        lay.addWidget(min_edit)
        lay.addWidget(QLabel("max"))
        lay.addWidget(max_edit)
        lay.addStretch(1)
        return row

    def _connect_change(self, widget: QWidget) -> None:
        # Connect appropriate signals to _emit_format.
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._emit_format)  # type: ignore[attr-defined]
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(self._emit_format)  # type: ignore[attr-defined]
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(self._emit_format)  # type: ignore[attr-defined]
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(self._emit_format)  # type: ignore[attr-defined]
        elif isinstance(widget, QRadioButton):
            widget.toggled.connect(self._emit_format)  # type: ignore[attr-defined]

    def _sync_limits_enabled(self) -> None:
        x_manual = not self.x_auto_chk.isChecked()
        self.x_min_edit.setEnabled(x_manual)
        self.x_max_edit.setEnabled(x_manual)

        y_manual = not self.y_auto_chk.isChecked()
        self.y_min_edit.setEnabled(y_manual)
        self.y_max_edit.setEnabled(y_manual)

    def get_format(self) -> PlotFormat:
        mode = "scatter" if self.scatter_radio.isChecked() else "line"

        def parse_opt_float(s: str) -> Optional[float]:
            s = (s or "").strip()
            if not s:
                return None
            try:
                return float(s)
            except Exception:
                return None

        x_limits = AxisLimits(
            auto=self.x_auto_chk.isChecked(),
            vmin=parse_opt_float(self.x_min_edit.text()),
            vmax=parse_opt_float(self.x_max_edit.text()),
        )
        y_limits = AxisLimits(
            auto=self.y_auto_chk.isChecked(),
            vmin=parse_opt_float(self.y_min_edit.text()),
            vmax=parse_opt_float(self.y_max_edit.text()),
        )

        lw = int(self.line_width_spin.value())
        line_width = None if lw <= 0 else lw

        color = None if self.color_combo.currentText() == "Auto" else self.color_combo.currentText()
        symbol = None if self.symbol_combo.currentText() == "Auto" else self.symbol_combo.currentText()

        return PlotFormat(
            mode=mode,
            title_enabled=self.title_enabled.isChecked(),
            title=self.title_edit.text(),
            x_label_enabled=self.x_label_enabled.isChecked(),
            x_label=self.x_label_edit.text(),
            y_label_enabled=self.y_label_enabled.isChecked(),
            y_label=self.y_label_edit.text(),
            grid=self.grid_chk.isChecked(),
            legend=self.legend_chk.isChecked(),
            x_scale=self.x_scale_combo.currentText(),
            y_scale=self.y_scale_combo.currentText(),
            x_limits=x_limits,
            y_limits=y_limits,
            line_width=line_width,
            marker_size=int(self.marker_size_spin.value()),
            sort_by_x=self.sort_by_x_chk.isChecked(),
            color=color,
            symbol=symbol,
        )

    def set_format(self, fmt: PlotFormat) -> None:
        self._updating = True
        try:
            # Mode
            self.line_radio.setChecked(fmt.mode != "scatter")
            self.scatter_radio.setChecked(fmt.mode == "scatter")

            # Style
            self.sort_by_x_chk.setChecked(bool(fmt.sort_by_x))
            self.line_width_spin.setValue(0 if fmt.line_width is None else int(fmt.line_width))
            self.marker_size_spin.setValue(int(fmt.marker_size))

            # Text
            self.title_enabled.setChecked(bool(fmt.title_enabled))
            self.title_edit.setText(fmt.title or "")

            self.x_label_enabled.setChecked(bool(fmt.x_label_enabled))
            self.x_label_edit.setText(fmt.x_label or "")

            self.y_label_enabled.setChecked(bool(fmt.y_label_enabled))
            self.y_label_edit.setText(fmt.y_label or "")

            # Display
            self.grid_chk.setChecked(bool(fmt.grid))
            self.legend_chk.setChecked(bool(fmt.legend))

            # Scales
            self._set_combo_text(self.x_scale_combo, fmt.x_scale)
            self._set_combo_text(self.y_scale_combo, fmt.y_scale)

            # Limits
            self.x_auto_chk.setChecked(bool(fmt.x_limits.auto))
            self.x_min_edit.setText("" if fmt.x_limits.vmin is None else str(fmt.x_limits.vmin))
            self.x_max_edit.setText("" if fmt.x_limits.vmax is None else str(fmt.x_limits.vmax))

            self.y_auto_chk.setChecked(bool(fmt.y_limits.auto))
            self.y_min_edit.setText("" if fmt.y_limits.vmin is None else str(fmt.y_limits.vmin))
            self.y_max_edit.setText("" if fmt.y_limits.vmax is None else str(fmt.y_limits.vmax))

            # Curve color
            color = getattr(fmt, "color", None)
            if color is None or color == "":
                self._set_combo_text(self.color_combo, "Auto")
            else:
                self._set_combo_text(self.color_combo, color)

            # Curve symbol
            symbol = getattr(fmt, "symbol", None)
            if symbol is None or symbol == "":
                self._set_combo_text(self.symbol_combo, "Auto")
            else:
                self._set_combo_text(self.symbol_combo, symbol)

            self._sync_limits_enabled()
        finally:
            self._updating = False

    def _set_combo_text(self, combo: QComboBox, text: str) -> None:
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _emit_format(self) -> None:
        if self._updating:
            return
        self._sync_limits_enabled()
        self.format_changed.emit(self.get_format())
    def set_overlay_state(self, enabled: bool) -> None:
        """Set the overlay checkbox state to match AppState."""
        self.overlay_chk.setChecked(enabled)

    def _update_mode(self) -> None:
        # Emit format_changed immediately to propagate mode selection
        self.format_changed.emit(self.get_format())
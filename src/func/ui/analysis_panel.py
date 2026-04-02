from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QAbstractTableModel, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class AnalysisRequest:
    """Payload emitted when the user requests a derived dataset."""

    result_name: str
    expression: str
    value_column: str
    use_error_propagation: bool = False
    error_column_name: str = ""


@dataclass(frozen=True)
class PeakAnalysisRequest:
    dataset_name: str
    direction: str  # 'Peaks' or 'Troughs'
    x_column: str
    y_column: str
    min_height: float
    min_prominence: float
    min_distance: float
    width: float


@dataclass(frozen=True)
class FitRequest:
    """Payload emitted when the user requests a curve fit."""

    x_column: str
    y_column: str
    model_name: str
    initial_params: str  # comma-separated or empty


class AnalysisPanel(QWidget):
    """UI for expression-based analysis / transformation.

    This panel is intentionally lightweight for the first iteration:
    - define a dataset/result name
    - define the output value column name
    - define the expression
    - optionally enable Gaussian error propagation
    - optionally define the propagated error column name

    Column-to-error-column mapping is expected to be collected elsewhere
    (for example by a future dedicated mapping dialog or panel).
    """

    analysis_requested = pyqtSignal(object)  # emits AnalysisRequest
    clear_requested = pyqtSignal()
    peak_analysis_requested = pyqtSignal(object)  # emits PeakAnalysisRequest
    fit_requested = pyqtSignal(object)  # emits FitRequest
    clear_fit_requested = pyqtSignal()
    roi_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Main layout for the widget itself
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        outer_layout.addWidget(self.scroll_area)

        # Container widget for scroll area
        self.container = QWidget()
        self.scroll_area.setWidget(self.container)

        root = QVBoxLayout(self.container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Analysis / Transformation")
        root.addWidget(title)

        # ── ROI Group ────────────────────────────────────────────────
        roi_box = QGroupBox("Region of Interest (ROI)")
        roi_layout = QVBoxLayout(roi_box)
        
        self.roi_checkbox = QCheckBox("Enable ROI bounds for stats & analysis")
        self.roi_checkbox.toggled.connect(self.roi_toggled.emit)
        
        self.roi_stats_text = QTextEdit()
        self.roi_stats_text.setReadOnly(True)
        self.roi_stats_text.setMaximumHeight(80)
        self.roi_stats_text.setPlaceholderText("ROI disabled. Check above to enable.")
        
        roi_layout.addWidget(self.roi_checkbox)
        roi_layout.addWidget(self.roi_stats_text)
        root.addWidget(roi_box)

        # ── Derived Dataset Group ────────────────────────────────────
        expr_box = QGroupBox("Derived Dataset")
        expr_layout = QFormLayout(expr_box)

        self.result_name_edit = QLineEdit()
        self.result_name_edit.setPlaceholderText("e.g. Derived dataset")

        self.value_column_combo = QComboBox()
        self.value_column_combo.setEditable(True)
        self.value_column_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.value_column_combo.setPlaceholderText("Select or type output column")

        self.expression_edit = QLineEdit()
        self.expression_edit.setPlaceholderText("e.g. distance / time")

        self.use_error_chk = QCheckBox("Enable Gaussian error propagation")
        self.error_column_name_edit = QLineEdit()
        self.error_column_name_edit.setPlaceholderText("e.g. velocity_err")
        self.error_column_name_edit.setEnabled(False)

        expr_layout.addRow("Result name", self.result_name_edit)
        expr_layout.addRow("Value column", self.value_column_combo)
        expr_layout.addRow("Expression", self.expression_edit)
        expr_layout.addRow("", self.use_error_chk)
        expr_layout.addRow("Error column", self.error_column_name_edit)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Create Derived Dataset")
        self.clear_btn = QPushButton("Clear")
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.clear_btn)
        expr_layout.addRow(btn_row)

        root.addWidget(expr_box)

        # Peak Analyzer Group
        peak_box = QGroupBox("Peak Analyzer")
        peak_layout = QFormLayout(peak_box)

        self.peak_direction_combo = QComboBox()
        self.peak_direction_combo.addItems(["Peaks", "Troughs"])
        self.peak_x_combo = QComboBox()
        self.peak_y_combo = QComboBox()
        self.peak_height_edit = QLineEdit()
        self.peak_prominence_edit = QLineEdit()
        self.peak_distance_edit = QLineEdit()
        self.peak_width_edit = QLineEdit()

        self.peak_height_edit.setPlaceholderText("Min Height (optional)")
        self.peak_prominence_edit.setPlaceholderText("Min Prominence (optional)")
        self.peak_distance_edit.setPlaceholderText("Min Distance (optional)")
        self.peak_width_edit.setPlaceholderText("Width (optional)")

        peak_layout.addRow("Direction", self.peak_direction_combo)
        peak_layout.addRow("X column", self.peak_x_combo)
        peak_layout.addRow("Y column", self.peak_y_combo)
        peak_layout.addRow("Min Height", self.peak_height_edit)
        peak_layout.addRow("Min Prominence", self.peak_prominence_edit)
        peak_layout.addRow("Min Distance", self.peak_distance_edit)
        peak_layout.addRow("Width", self.peak_width_edit)

        # Add a button to trigger peak detection
        self.peak_detect_btn = QPushButton("Detect Peaks")
        peak_layout.addRow(self.peak_detect_btn)

        peak_layout.addRow(QLabel("Peaks Found:"))
        self.peak_table = QTableView()
        # Configuration for the table
        self.peak_table.verticalHeader().setVisible(False)
        self.peak_table.horizontalHeader().setStretchLastSection(True)
        self.peak_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.peak_table.setAlternatingRowColors(True)
        self.peak_table.setMinimumHeight(150)
        self.peak_table.setMaximumHeight(300)
        peak_layout.addRow(self.peak_table)

        # Add to main layout
        root.addWidget(peak_box)

        # ── Curve Fitting Group ──────────────────────────────────────
        fit_box = QGroupBox("Curve Fitting")
        fit_layout = QFormLayout(fit_box)

        self.fit_x_combo = QComboBox()
        self.fit_y_combo = QComboBox()

        self.fit_model_combo = QComboBox()
        # Populated later via set_fit_models()
        try:
            from func.analysis.curve_fitter import get_model_names
            self.fit_model_combo.addItems(get_model_names())
        except Exception:
            pass

        self.fit_p0_edit = QLineEdit()
        self.fit_p0_edit.setPlaceholderText("e.g. 1.0, 0.0, 1.0 (optional)")

        fit_layout.addRow("X column", self.fit_x_combo)
        fit_layout.addRow("Y column", self.fit_y_combo)
        fit_layout.addRow("Fit type", self.fit_model_combo)
        fit_layout.addRow("Initial params", self.fit_p0_edit)

        fit_btn_row = QHBoxLayout()
        self.fit_btn = QPushButton("Fit")
        self.clear_fit_btn = QPushButton("Clear Fit")
        fit_btn_row.addWidget(self.fit_btn)
        fit_btn_row.addWidget(self.clear_fit_btn)
        fit_layout.addRow(fit_btn_row)

        self.fit_results_text = QTextEdit()
        self.fit_results_text.setReadOnly(True)
        self.fit_results_text.setMaximumHeight(200)
        self.fit_results_text.setPlaceholderText("Fit results will appear here…")
        fit_layout.addRow(self.fit_results_text)

        root.addWidget(fit_box)

        root.addStretch(1)

        self.use_error_chk.toggled.connect(self._sync_error_controls)  # type: ignore[attr-defined]
        self.apply_btn.clicked.connect(self._emit_request)  # type: ignore[attr-defined]
        self.clear_btn.clicked.connect(self._clear_form)  # type: ignore[attr-defined]
        self.peak_detect_btn.clicked.connect(self._emit_peak_request)
        self.fit_btn.clicked.connect(self._emit_fit_request)
        self.clear_fit_btn.clicked.connect(self._emit_clear_fit)

    def set_available_columns(self, columns: list[str]) -> None:
        """Populate the value-column dropdown from the current dataset columns.

        The combo remains editable so the user can still type a brand-new output
        column name if they do not want to reuse an existing column name.
        """
        current_text = self.value_column_combo.currentText().strip()

        self.value_column_combo.blockSignals(True)
        try:
            self.value_column_combo.clear()
            self.value_column_combo.addItems([str(c) for c in columns if str(c).strip()])
            if current_text:
                self.value_column_combo.setCurrentText(current_text)
        finally:
            self.value_column_combo.blockSignals(False)

    def set_peak_columns(self, columns: list[str]) -> None:
        current_x = self.peak_x_combo.currentText()
        current_y = self.peak_y_combo.currentText()

        self.peak_x_combo.blockSignals(True)
        self.peak_y_combo.blockSignals(True)
        try:
            self.peak_x_combo.clear()
            self.peak_y_combo.clear()
            self.peak_x_combo.addItems([str(c) for c in columns])
            self.peak_y_combo.addItems([str(c) for c in columns])

            # restore previous selection if still in the list
            if current_x in columns:
                self.peak_x_combo.setCurrentText(current_x)
            else:
                self.peak_x_combo.setCurrentIndex(0)

            if current_y in columns:
                self.peak_y_combo.setCurrentText(current_y)
            else:
                self.peak_y_combo.setCurrentIndex(0)
        finally:
            self.peak_x_combo.blockSignals(False)
            self.peak_y_combo.blockSignals(False)

    def set_peak_model(self, model: "QAbstractTableModel") -> None:
        """Display the PeakTableModel in the Peak Analyzer table."""
        self.peak_table.setModel(model)
        self.peak_table.resizeColumnsToContents()

    def set_roi_stats(self, text: str) -> None:
        """Update the ROI statistics text area."""
        self.roi_stats_text.setPlainText(text)

    def set_fit_columns(self, columns: list[str]) -> None:
        """Populate X/Y column dropdowns for the curve fitting group."""
        current_x = self.fit_x_combo.currentText()
        current_y = self.fit_y_combo.currentText()

        self.fit_x_combo.blockSignals(True)
        self.fit_y_combo.blockSignals(True)
        try:
            self.fit_x_combo.clear()
            self.fit_y_combo.clear()
            self.fit_x_combo.addItems([str(c) for c in columns])
            self.fit_y_combo.addItems([str(c) for c in columns])

            if current_x in columns:
                self.fit_x_combo.setCurrentText(current_x)
            elif len(columns) > 0:
                self.fit_x_combo.setCurrentIndex(0)

            if current_y in columns:
                self.fit_y_combo.setCurrentText(current_y)
            elif len(columns) > 1:
                self.fit_y_combo.setCurrentIndex(1)
            elif len(columns) > 0:
                self.fit_y_combo.setCurrentIndex(0)
        finally:
            self.fit_x_combo.blockSignals(False)
            self.fit_y_combo.blockSignals(False)

    def set_fit_results(self, text: str) -> None:
        """Display fit results in the results text area."""
        self.fit_results_text.setPlainText(text)

    def _sync_error_controls(self, checked: bool) -> None:
        self.error_column_name_edit.setEnabled(bool(checked))
        if not checked:
            self.error_column_name_edit.clear()

    def _emit_request(self) -> None:
        req = AnalysisRequest(
            result_name=self.result_name_edit.text().strip(),
            expression=self.expression_edit.text().strip(),
            value_column=self.value_column_combo.currentText().strip(),
            use_error_propagation=self.use_error_chk.isChecked(),
            error_column_name=self.error_column_name_edit.text().strip(),
        )
        self.analysis_requested.emit(req)

    def _emit_peak_request(self) -> None:
        req = PeakAnalysisRequest(
            dataset_name="",
            direction=self.peak_direction_combo.currentText().strip(),
            x_column=self.peak_x_combo.currentText().strip(),
            y_column=self.peak_y_combo.currentText().strip(),
            min_height=float(self.peak_height_edit.text() or 0),
            min_prominence=float(self.peak_prominence_edit.text() or 0),
            min_distance=float(self.peak_distance_edit.text() or 1),
            width=float(self.peak_width_edit.text() or 0),
        )
        self.peak_analysis_requested.emit(req)

    def _emit_fit_request(self) -> None:
        req = FitRequest(
            x_column=self.fit_x_combo.currentText().strip(),
            y_column=self.fit_y_combo.currentText().strip(),
            model_name=self.fit_model_combo.currentText().strip(),
            initial_params=self.fit_p0_edit.text().strip(),
        )
        self.fit_requested.emit(req)

    def _emit_clear_fit(self) -> None:
        self.fit_results_text.clear()
        self.clear_fit_requested.emit()

    def _clear_form(self) -> None:
        self.result_name_edit.clear()
        self.value_column_combo.setCurrentText("")
        self.expression_edit.clear()
        self.use_error_chk.setChecked(False)
        self.error_column_name_edit.clear()
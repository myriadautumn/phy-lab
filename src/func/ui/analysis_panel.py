from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Analysis / Transformation")
        root.addWidget(title)

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

        root.addWidget(expr_box)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Create Derived Dataset")
        self.clear_btn = QPushButton("Clear")
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        root.addStretch(1)

        self.use_error_chk.toggled.connect(self._sync_error_controls)  # type: ignore[attr-defined]
        self.apply_btn.clicked.connect(self._emit_request)  # type: ignore[attr-defined]
        self.clear_btn.clicked.connect(self._clear_form)  # type: ignore[attr-defined]

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

    def _clear_form(self) -> None:
        self.result_name_edit.clear()
        self.value_column_combo.setCurrentText("")
        self.expression_edit.clear()
        self.use_error_chk.setChecked(False)
        self.error_column_name_edit.clear()
        self.clear_requested.emit()
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_ID_ROLE = 256   # Qt.UserRole
_TEXT_ROLE = 257 # custom

class CurvesPanel(QWidget):
    """UI panel to manage plotted curves.

    - Check/uncheck to show/hide
    - Double click to rename

    Emits signals for MainWindow to update AppState.curves.
    """

    visibility_changed = pyqtSignal(str, bool)  # curve_id, visible
    label_changed = pyqtSignal(str, str)        # curve_id, new_label
    remove_requested = pyqtSignal(str)          # curve_id
    clear_all_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        root.addWidget(self.list, 1)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.remove_btn = QPushButton("Remove")
        self.clear_btn = QPushButton("Clear All")
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch(1)
        root.addWidget(btn_row)

        # Wiring
        self.list.itemChanged.connect(self._on_item_changed)  # type: ignore[attr-defined]
        self.remove_btn.clicked.connect(self._remove_selected)  # type: ignore[attr-defined]
        self.clear_btn.clicked.connect(self.clear_all_requested.emit)  # type: ignore[attr-defined]

    def set_curves(self, curves) -> None:
        self.list.blockSignals(True)
        try:
            self.list.clear()
            for c in curves or []:
                try:
                    cid = c.get("id")
                    label = c.get("label")
                    visible = bool(c.get("visible", True))
                except Exception:
                    cid = getattr(c, "id", "")
                    label = getattr(c, "label", "")
                    visible = bool(getattr(c, "visible", True))

                if not cid:
                    continue

                text = str(label) if label else str(cid)
                item = QListWidgetItem(text)
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEditable
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                item.setCheckState(Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked)
                item.setData(_ID_ROLE, str(cid))
                item.setData(_TEXT_ROLE, text)
                self.list.addItem(item)
        finally:
            self.list.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        cid = item.data(_ID_ROLE)
        if not cid:
            return
        cid = str(cid)

        # Emit visibility change
        visible = item.checkState() == Qt.CheckState.Checked
        self.visibility_changed.emit(cid, visible)

        # Emit label change if text was edited
        prev_text = item.data(_TEXT_ROLE)
        cur_text = item.text()
        if prev_text != cur_text:
            item.setData(_TEXT_ROLE, cur_text)
            self.label_changed.emit(cid, cur_text)

    def _remove_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        cid = item.data(_ID_ROLE)
        if not cid:
            return
        self.remove_requested.emit(str(cid))
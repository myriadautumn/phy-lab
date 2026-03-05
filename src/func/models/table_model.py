from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

if TYPE_CHECKING:
    import pandas as pd


class PandasTableModel(QAbstractTableModel):
    """Read-only Qt table model backed by a pandas DataFrame.

    Intended for previews; callers can pass df.head(N) for performance.
    """

    def __init__(self, df: "pd.DataFrame") -> None:
        super().__init__()
        self._df = df

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return int(self._df.shape[0])

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return int(self._df.shape[1])

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        value = self._df.iat[index.row(), index.column()]
        if value is None:
            return ""
        try:
            return str(value)
        except Exception:
            return ""

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):  # type: ignore[override]
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            try:
                return str(self._df.columns[section])
            except Exception:
                return str(section)

        # Row numbers (1-based)
        return str(section + 1)
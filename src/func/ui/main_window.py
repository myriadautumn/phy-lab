from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from func.io.csv_importer import load_csv
from func.models.app_state import AppState
from func.models.dataset import Dataset
from func.models.table_model import PandasTableModel
from func.plotting.plot_service import export_plot_png, plot_xy
from func.ui.controls_panel import ControlsPanel, PlotSelection


class MainWindow(QMainWindow):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state

        self.setWindowTitle("phy-lab")
        self.statusBar().showMessage("Ready")

        # Plot
        self.plot = pg.PlotWidget()
        self.plot.setBackground(None)
        self.plot.setLabel("bottom", "x")
        self.plot.setLabel("left", "y")
        self.plot.showGrid(x=True, y=True, alpha=0.3)

        # Data preview (table)
        self.table = QTableView()
        self.table.setSortingEnabled(False)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(True)
        self.table.hide()  # hidden until import

        # Splitter: left = table preview, right = plot
        self.splitter = QSplitter()
        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.plot)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

        # Controls panel (X/Y selection + plot type)
        self.controls = ControlsPanel()
        self.controls.selection_changed.connect(self._on_selection_changed)  # type: ignore[attr-defined]

        # Container layout: controls on top, splitter below
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        container_layout.addWidget(self.controls)
        container_layout.addWidget(self.splitter, 1)
        self.setCentralWidget(container)

        self._build_menu()

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")

        import_action = QAction("Import CSV…", self)
        import_action.triggered.connect(self.import_csv)  # type: ignore[attr-defined]
        file_menu.addAction(import_action)

        export_action = QAction("Export Plot…", self)
        export_action.triggered.connect(self.export_plot)  # type: ignore[attr-defined]
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)  # type: ignore[attr-defined]
        file_menu.addAction(quit_action)

    def _on_selection_changed(self, sel: PlotSelection) -> None:
        # Persist selection even if a dataset isn't loaded yet.
        self.state.selection = sel

        ds = self.state.current_dataset
        if ds is None:
            return
        if not sel.x_col or not sel.y_col:
            return

        result = plot_xy(self.plot, ds.df, sel.x_col, sel.y_col, sel.mode, clear=True)
        if not result.ok:
            QMessageBox.warning(self, "Plot failed", result.message)
            return

        self.statusBar().showMessage(f"Loaded {ds.name} | plotted {sel.x_col} vs {sel.y_col}")

    def export_plot(self) -> None:
        # Require something to export.
        if self.state.current_dataset is None or self.state.selection is None:
            QMessageBox.information(
                self,
                "Nothing to export",
                "Import data and plot it before exporting.",
            )
            return

        default_name = Path(self.state.current_dataset.name).stem + ".png"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Plot",
            default_name,
            "PNG Image (*.png)",
        )
        if not path_str:
            return

        out_path = Path(path_str)
        if out_path.suffix.lower() != ".png":
            out_path = out_path.with_suffix(".png")

        result = export_plot_png(self.plot, out_path)
        if not result.ok:
            QMessageBox.warning(self, "Export failed", result.message)
            return

        self.statusBar().showMessage(f"Exported plot to {out_path.name}")

    def import_csv(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import CSV",
            "",
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)",
        )
        if not path_str:
            return

        path = Path(path_str)
        try:
            df = load_csv(path)
        except ValueError as e:
            QMessageBox.warning(self, "Empty dataset", str(e))
            return
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import failed",
                f"Could not read the file as CSV:\n\n{path}\n\nError:\n{e}",
            )
            return

        # Store in central state
        self.state.current_dataset = Dataset(name=path.name, path=path, df=df)

        # Update preview table (first N rows for responsiveness)
        preview_rows = 2000
        preview_df = df.head(preview_rows)
        self.table.setModel(PandasTableModel(preview_df))
        self.table.resizeColumnsToContents()

        # Reveal the preview panel after a successful import.
        if not self.table.isVisible():
            self.table.show()
            self.splitter.setSizes([350, 650])

        self.statusBar().showMessage(
            f"Loaded {self.state.current_dataset.name} | {df.shape[0]} rows × {df.shape[1]} cols (preview {min(df.shape[0], preview_rows)} rows)"
        )

        # Populate controls (prefer numeric columns for defaults)
        all_cols = [str(c) for c in df.columns]
        numeric_cols = [str(c) for c in df.select_dtypes(include='number').columns]
        sel = self.controls.set_columns(all_cols, numeric_cols)

        # Persist selection and plot using the returned selection
        self.state.selection = sel
        ds = self.state.current_dataset
        if ds is not None and sel.x_col and sel.y_col:
            result = plot_xy(self.plot, ds.df, sel.x_col, sel.y_col, sel.mode, clear=True)
            if not result.ok:
                QMessageBox.warning(self, "Plot failed", result.message)
            else:
                self.statusBar().showMessage(
                    f"Loaded {ds.name} | plotted {sel.x_col} vs {sel.y_col}"
                )
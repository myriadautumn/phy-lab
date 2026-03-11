from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PyQt6.QtWidgets import QLabel

import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from func.analysis.expression_engine import (
    ExpressionEngineError,
    build_derived_dataset,
)
from func.analysis.curve_fitter import perform_fit
from func.analysis.peak_analyzer import detect_peaks
from func.io.csv_importer import load_csv
from func.models.app_state import AppState
from func.models.dataset import Dataset
from func.models.table_model import PandasTableModel
from func.plotting.plot_service import export_plot_png, render_curves, render_plot
from func.ui.analysis_panel import (
    AnalysisPanel,
    AnalysisRequest,
    FitRequest,
    PeakAnalysisRequest,
)
from func.ui.controls_panel import ControlsPanel, PlotSelection
from func.ui.curves_panel import CurvesPanel
from func.ui.format_panel import FormatPanel


class MainWindow(QMainWindow):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state

        self.setWindowTitle("phy-lab")
        self.statusBar().showMessage("Ready")

        self._df_cache: dict[str, object] = {}
        self._peak_scatter_item = None  # pyqtgraph item for peak markers
        self._peak_data: dict | None = None  # {"x": array, "y": array}
        self._fit_plot_item = None  # pyqtgraph item for curve fit line
        self._fit_data: dict | None = None  # {"x": array, "y": array}

        # Plot
        self.plot = pg.PlotWidget()
        self.plot.setBackground(None)
        self.plot.clear()  # Ensure plot starts empty
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

        # Dataset name label
        self.table_label = QLabel("", self)
        self.table_label.setStyleSheet("font-weight: bold; margin: 4px;")

        # Splitter: left = table preview, right = plot
        self.splitter = QSplitter()
        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.plot)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

        # Controls panel (X/Y selection + optional Y error)
        self.controls = ControlsPanel()
        self.controls.selection_changed.connect(self._on_selection_changed)  # type: ignore[attr-defined]

        # Format panel dock (hidden by default)
        self.format_panel = FormatPanel()
        self.format_panel.set_format(self.state.format)
        self.format_panel.format_changed.connect(self._on_format_changed)  # type: ignore[attr-defined]
        self.format_panel.overlay_toggled.connect(self._on_overlay_toggled)  # type: ignore[attr-defined]
        self.format_panel.add_curve_requested.connect(self._on_add_curve_requested)  # type: ignore[attr-defined]

        self.format_dock = QDockWidget("Format", self)
        self.format_dock.setObjectName("format_dock")
        self.format_dock.setWidget(self.format_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.format_dock)
        self.format_dock.hide()
        self.format_dock.visibilityChanged.connect(self._on_format_dock_visibility_changed)  # type: ignore[attr-defined]

        # Curves panel dock (hidden by default)
        self.curves_panel = CurvesPanel()
        self.curves_panel.set_curves(getattr(self.state, "curves", []))
        self.curves_panel.visibility_changed.connect(self._on_curve_visibility_changed)
        self.curves_panel.label_changed.connect(self._on_curve_label_changed)
        self.curves_panel.remove_requested.connect(self._on_curve_remove_requested)
        self.curves_panel.clear_all_requested.connect(self._on_curve_clear_all)

        self.curves_dock = QDockWidget("Curves", self)
        self.curves_dock.setObjectName("curves_dock")
        self.curves_dock.setWidget(self.curves_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.curves_dock)
        self.curves_dock.hide()
        self.curves_dock.visibilityChanged.connect(self._on_curves_dock_visibility_changed)

        # Analysis panel dock (hidden by default)
        self.analysis_panel = AnalysisPanel()
        self.analysis_panel.analysis_requested.connect(self._on_analysis_requested)
        self.analysis_panel.peak_analysis_requested.connect(self._on_peak_analysis_requested)
        self.analysis_panel.fit_requested.connect(self._on_fit_requested)
        self.analysis_panel.clear_fit_requested.connect(self._on_clear_fit_requested)
        self.analysis_panel.clear_requested.connect(self._on_analysis_cleared)

        self.analysis_dock = QDockWidget("Analysis", self)
        self.analysis_dock.setObjectName("analysis_dock")
        self.analysis_dock.setWidget(self.analysis_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.analysis_dock)
        self.analysis_dock.hide()
        self.analysis_dock.visibilityChanged.connect(self._on_analysis_dock_visibility_changed)

        # Container layout: controls on top, dataset label, splitter below
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        container_layout.addWidget(self.controls)
        container_layout.addWidget(self.table_label)
        container_layout.addWidget(self.splitter, 1)
        self.setCentralWidget(container)

        self._build_menu()
        self._refresh_recent_menu()
        QTimer.singleShot(0, self._restore_last_session)  # type: ignore[arg-type]

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")

        import_action = QAction("Import CSV…", self)
        import_action.triggered.connect(self.import_csv)  # type: ignore[attr-defined]
        file_menu.addAction(import_action)

        self.open_recent_menu = file_menu.addMenu("Open Recent")
        self.open_recent_menu.setEnabled(False)

        clear_recent_action = QAction("Clear Recent", self)
        clear_recent_action.triggered.connect(self._clear_recent_files)  # type: ignore[attr-defined]
        self.open_recent_menu.addSeparator()
        self.open_recent_menu.addAction(clear_recent_action)

        export_action = QAction("Export Plot…", self)
        export_action.triggered.connect(self.export_plot)  # type: ignore[attr-defined]
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)  # type: ignore[attr-defined]
        file_menu.addAction(quit_action)

        view_menu = menu.addMenu("View")

        self.toggle_format_action = QAction("Format Panel", self)
        self.toggle_format_action.setCheckable(True)
        self.toggle_format_action.setChecked(False)
        self.toggle_format_action.triggered.connect(self._toggle_format_dock)  # type: ignore[attr-defined]
        view_menu.addAction(self.toggle_format_action)

        self.toggle_curves_action = QAction("Curves Panel", self)
        self.toggle_curves_action.setCheckable(True)
        self.toggle_curves_action.setChecked(False)
        self.toggle_curves_action.triggered.connect(self._toggle_curves_dock)
        view_menu.addAction(self.toggle_curves_action)

        self.toggle_analysis_action = QAction("Analysis Panel", self)
        self.toggle_analysis_action.setCheckable(True)
        self.toggle_analysis_action.setChecked(False)
        self.toggle_analysis_action.triggered.connect(self._toggle_analysis_dock)
        view_menu.addAction(self.toggle_analysis_action)

    def _get_recent_files(self) -> list[str]:
        rf = getattr(self.state, "recent_files", None)
        if isinstance(rf, list):
            return [str(p) for p in rf if p]
        return []

    def _set_recent_files(self, files: list[str]) -> None:
        if hasattr(self.state, "recent_files"):
            setattr(self.state, "recent_files", files)

    def _update_recent_files(self, path: Path, max_items: int = 10) -> None:
        p = str(path)
        files = [f for f in self._get_recent_files() if f != p]
        files.insert(0, p)
        while len(files) > max_items:
            files.pop()
        self._set_recent_files(files)
        if hasattr(self.state, "last_file_path"):
            setattr(self.state, "last_file_path", p)

    def _refresh_recent_menu(self) -> None:
        if not hasattr(self, "open_recent_menu"):
            return

        menu = self.open_recent_menu
        menu.clear()

        files = self._get_recent_files()
        if not files:
            menu.setEnabled(False)
            placeholder = QAction("(No recent files)", self)
            placeholder.setEnabled(False)
            menu.addAction(placeholder)

            menu.addSeparator()
            clear_recent_action = QAction("Clear Recent", self)
            clear_recent_action.setEnabled(False)
            menu.addAction(clear_recent_action)
            return

        menu.setEnabled(True)

        for f in files:
            act = QAction(f, self)
            act.triggered.connect(lambda checked=False, fp=f: self._open_recent_file(fp))  # type: ignore[attr-defined]
            menu.addAction(act)

        menu.addSeparator()
        clear_recent_action = QAction("Clear Recent", self)
        clear_recent_action.triggered.connect(self._clear_recent_files)  # type: ignore[attr-defined]
        menu.addAction(clear_recent_action)

    def _clear_recent_files(self) -> None:
        self._set_recent_files([])
        if hasattr(self.state, "last_file_path"):
            setattr(self.state, "last_file_path", None)
        self._save_settings_best_effort()
        self._refresh_recent_menu()

    def _open_recent_file(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            QMessageBox.warning(
                self,
                "File not found",
                f"This file no longer exists:\n\n{file_path}",
            )
            files = [f for f in self._get_recent_files() if f != file_path]
            self._set_recent_files(files)
            self._save_settings_best_effort()
            self._refresh_recent_menu()
            return

        self._load_csv_path(path)

    def _save_settings_best_effort(self) -> None:
        try:
            from func.io.settings_store import save_settings  # type: ignore
            from func.models.settings import AppSettings  # type: ignore
        except Exception:
            return

        try:
            settings = AppSettings.from_app_state(self.state)
            save_settings(settings.to_dict())
        except Exception:
            return

    def _restore_last_session(self) -> None:
        last = getattr(self.state, "last_file_path", None)
        if not last:
            return

        path = Path(str(last))
        if not path.exists():
            return

        self._load_csv_path(path)

    def _toggle_format_dock(self, checked: bool) -> None:
        if checked:
            self.format_dock.show()
        else:
            self.format_dock.hide()

    def _on_format_dock_visibility_changed(self, visible: bool) -> None:
        if hasattr(self, "toggle_format_action"):
            self.toggle_format_action.blockSignals(True)
            try:
                self.toggle_format_action.setChecked(bool(visible))
            finally:
                self.toggle_format_action.blockSignals(False)

    def _df_provider(self, file_path: str):
        # For derived datasets (path missing), fall back to datasets kept in AppState.
        if file_path in self._df_cache:
            return self._df_cache[file_path]

        if not file_path:
            current = getattr(self.state, "current_dataset", None)
            if current is not None and getattr(current, "path", None) is None:
                return current.df
            for ds in getattr(self.state, "derived_datasets", []) or []:
                if getattr(ds, "path", None) is None:
                    return ds.df
            return None

        path = Path(file_path)
        if not path.exists():
            return None

        try:
            df = load_csv(path)
        except Exception:
            return None

        self._df_cache[file_path] = df
        return df

    def _draw_peak_overlay(self) -> None:
        """Draw stored peak markers on top of the current plot."""
        # Remove old peak scatter item if present
        if self._peak_scatter_item is not None:
            self.plot.removeItem(self._peak_scatter_item)
            self._peak_scatter_item = None

        if self._peak_data is None:
            return

        scatter = pg.ScatterPlotItem(
            x=self._peak_data["x"],
            y=self._peak_data["y"],
            symbol="x",
            size=14,
            pen=pg.mkPen("r", width=2),
            brush=pg.mkBrush("r"),
        )
        self.plot.addItem(scatter)
        self._peak_scatter_item = scatter

    def _draw_fit_overlay(self) -> None:
        """Draw fitted curve line on top of the current plot."""
        if self._fit_plot_item is not None:
            self.plot.removeItem(self._fit_plot_item)
            self._fit_plot_item = None

        if self._fit_data is None:
            return

        fit_line = pg.PlotDataItem(
            x=self._fit_data["x"],
            y=self._fit_data["y"],
            pen=pg.mkPen("cyan", width=3, style=Qt.PenStyle.DashLine)
        )
        self.plot.addItem(fit_line)
        self._fit_plot_item = fit_line

    def _replot_if_possible(self) -> None:
        curves = getattr(self.state, "curves", []) or []
        if curves:
            result = render_curves(
                self.plot,
                self._df_provider,
                curves,
                self.state.format,
                clear=not getattr(self.state, "overlay_enabled", True),
            )
            self.statusBar().showMessage(result.message)
            self._draw_fit_overlay()
            self._draw_peak_overlay()
            return

        ds = self.state.current_dataset
        sel = self.state.selection
        if ds is None or sel is None:
            return
        if not sel.x_col or not sel.y_col:
            return

        result = render_plot(self.plot, ds.df, sel, self.state.format, clear=True)
        if not result.ok:
            QMessageBox.warning(self, "Plot failed", result.message)
            return

        self.statusBar().showMessage(result.message)
        self._draw_fit_overlay()
        self._draw_peak_overlay()

    def _on_format_changed(self, fmt) -> None:
        self.state.format = fmt
        self._replot_if_possible()
        self._save_settings_best_effort()

    def _on_overlay_toggled(self, enabled: bool) -> None:
        self.state.overlay_enabled = bool(enabled)
        self._save_settings_best_effort()
        self.statusBar().showMessage(
            "Overlay enabled" if self.state.overlay_enabled else "Overlay disabled"
        )

    def _on_add_curve_requested(self) -> None:
        ds = self.state.current_dataset
        sel = self.state.selection
        if ds is None or sel is None or not sel.x_col or not sel.y_col:
            QMessageBox.information(
                self,
                "Nothing to add",
                "Import data and select X/Y before adding a curve.",
            )
            return

        # Initialize overlay and curves list
        if not hasattr(self.state, "overlay_enabled"):
            self.state.overlay_enabled = True
        if not hasattr(self.state, "curves") or self.state.curves is None:
            self.state.curves = []
        if not getattr(self.state, "overlay_enabled", True):
            self.state.curves = []

        # Prepare curve dictionary
        curve = {
            "id": str(uuid4()),
            "dataset": ds.name,
            "path": str(ds.path) if ds.path else "",
            "x_col": sel.x_col,
            "y_col": sel.y_col,
            "y_err_col": getattr(sel, "y_err_col", "") or "",
            "mode": getattr(self.state.format, "mode", "line"),
            "label": f"{sel.y_col} vs {sel.x_col} ({getattr(self.state.format, 'mode', 'line')})",
            "visible": True,
            "color": None,
            "symbol": None,
        }

        # Assign color and symbol from format panel if user selected, else auto
        color_combo = getattr(self.format_panel, 'color_combo', None)
        symbol_combo = getattr(self.format_panel, 'symbol_combo', None)
        if color_combo and color_combo.currentText() != 'Auto':
            curve['color'] = color_combo.currentText()
        if symbol_combo and symbol_combo.currentText() != 'Auto':
            curve['symbol'] = symbol_combo.currentText()

        # Append to curves and refresh UI
        self.state.curves.append(curve)
        self.curves_panel.set_curves(self.state.curves)
        self._replot_if_possible()
        self._save_settings_best_effort()

        # Update table label
        self.table_label.setText(f"Dataset: {self.state.current_dataset.name}")
        self.statusBar().showMessage(f"Added curve: {curve['label']} (total {len(self.state.curves)})")

    def _on_curve_visibility_changed(self, curve_id: str, visible: bool) -> None:
        for c in getattr(self.state, "curves", []):
            if isinstance(c, dict) and c.get("id") == curve_id:
                c["visible"] = bool(visible)
                break
        self._save_settings_best_effort()
        self._replot_if_possible()

    def _on_curve_label_changed(self, curve_id: str, label: str) -> None:
        for c in getattr(self.state, "curves", []):
            if isinstance(c, dict) and c.get("id") == curve_id:
                c["label"] = str(label)
                break
        self._save_settings_best_effort()
        self._replot_if_possible()

    def _on_curve_remove_requested(self, curve_id: str) -> None:
        curves = [
            c
            for c in getattr(self.state, "curves", [])
            if not (isinstance(c, dict) and c.get("id") == curve_id)
        ]
        self.state.curves = curves
        self.curves_panel.set_curves(curves)
        self._save_settings_best_effort()
        self._replot_if_possible()

    def _on_curve_clear_all(self) -> None:
        self.state.curves = []
        self.curves_panel.set_curves([])
        self._save_settings_best_effort()
        self._replot_if_possible()

    def _toggle_curves_dock(self, checked: bool) -> None:
        if checked:
            self.curves_dock.show()
        else:
            self.curves_dock.hide()

    def _on_curves_dock_visibility_changed(self, visible: bool) -> None:
        if hasattr(self, "toggle_curves_action"):
            self.toggle_curves_action.blockSignals(True)
            try:
                self.toggle_curves_action.setChecked(bool(visible))
            finally:
                self.toggle_curves_action.blockSignals(False)

    def _toggle_analysis_dock(self, checked: bool) -> None:
        if checked:
            self.analysis_dock.show()
        else:
            self.analysis_dock.hide()

    def _on_analysis_dock_visibility_changed(self, visible: bool) -> None:
        if hasattr(self, "toggle_analysis_action"):
            self.toggle_analysis_action.blockSignals(True)
            try:
                self.toggle_analysis_action.setChecked(bool(visible))
            finally:
                self.toggle_analysis_action.blockSignals(False)

    def _on_analysis_cleared(self) -> None:
        self.statusBar().showMessage("Analysis form cleared")

    def _on_analysis_requested(self, req: AnalysisRequest) -> None:
        ds = self.state.current_dataset
        if ds is None:
            QMessageBox.information(
                self,
                "No dataset",
                "Import a dataset before creating a derived dataset.",
            )
            return

        if not req.result_name.strip():
            QMessageBox.warning(self, "Missing result name", "Please enter a result dataset name.")
            return
        if not req.value_column.strip():
            QMessageBox.warning(self, "Missing value column", "Please enter an output value column name.")
            return
        if not req.expression.strip():
            QMessageBox.warning(self, "Missing expression", "Please enter an expression.")
            return

        error_map: dict[str, str] | None = None
        if req.use_error_propagation:
            error_map = dict(getattr(self.state, "error_column_map", {}) or {})
            sel = getattr(self.state, "selection", None)
            if sel is not None and getattr(sel, "y_col", "") and getattr(sel, "y_err_col", ""):
                error_map.setdefault(str(sel.y_col), str(sel.y_err_col))

            if not error_map:
                QMessageBox.warning(
                    self,
                    "Missing error mapping",
                    "No error-column mapping is available. Populate AppState.error_column_map first.",
                )
                return

        try:
            result = build_derived_dataset(
                source=ds,
                expr=req.expression,
                result_name=req.result_name,
                value_column=req.value_column,
                error_columns=error_map,
                error_column_name=req.error_column_name or None,
            )
        except ExpressionEngineError as e:
            QMessageBox.warning(self, "Analysis failed", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Analysis failed", str(e))
            return

        derived_ds = result.dataset

        if hasattr(self.state, "derived_datasets"):
            self.state.derived_datasets.append(derived_ds)
        if hasattr(self.state, "last_analysis_expression"):
            self.state.last_analysis_expression = req.expression

        self.state.current_dataset = derived_ds
        if hasattr(self.state, "error_column_map") and result.error_column:
            self.state.error_column_map[str(result.value_column)] = str(result.error_column)

        preview_rows = 2000
        preview_df = derived_ds.df.head(preview_rows)
        self.table.setModel(PandasTableModel(preview_df))
        self.table.resizeColumnsToContents()
        # Update table label to reflect the derived dataset
        self.table_label.setText(f"Dataset: {self.state.current_dataset.name}")
        if not self.table.isVisible():
            self.table.show()
            self.splitter.setSizes([350, 650])

        all_cols = [str(c) for c in derived_ds.df.columns]
        numeric_cols = [str(c) for c in derived_ds.df.select_dtypes(include="number").columns]
        sel = self.controls.set_columns(all_cols, numeric_cols)
        self.analysis_panel.set_available_columns(all_cols)
        self.analysis_panel.set_peak_columns(all_cols)
        self.analysis_panel.set_fit_columns(all_cols)

        # Optional: auto-select the new result as Y to plot it immediately.
        x_col = derived_ds.x_col or (sel.x_col if sel is not None else "")
        y_col = derived_ds.y_col or req.value_column
        y_err_col = result.error_column or ""

        try:
            sel = self.controls.set_selection(
                str(x_col or ""),
                str(y_col or ""),
                str(y_err_col or ""),
            )
        except Exception:
            pass

        self.state.selection = sel
        self._replot_if_possible()
        self._save_settings_best_effort()
        self.statusBar().showMessage(f"Created derived dataset: {derived_ds.name}")

    def _on_peak_analysis_requested(self, req: PeakAnalysisRequest) -> None:
        ds = self.state.current_dataset
        if ds is None:
            QMessageBox.information(
                self,
                "No dataset",
                "Import a dataset before peak analysis.",
            )
            return

        if not req.x_column or not req.y_column:
            QMessageBox.warning(self, "Missing columns", "Please select X and Y columns.")
            return

        try:
            peak_result = detect_peaks(
                dataset=ds,
                x_col=req.x_column,
                y_col=req.y_column,
                height=req.min_height if req.min_height else None,
                distance=int(req.min_distance) if req.min_distance else None,
                prominence=req.min_prominence if req.min_prominence else None,
                width=req.width if req.width else None
            )
        except Exception as e:
            QMessageBox.critical(self, "Peak Analysis failed", str(e))
            return

        if len(peak_result.x_positions) == 0:
            # Clear any existing peak markers
            self._peak_data = None
            self._draw_peak_overlay()
            QMessageBox.information(self, "No peaks", "No peaks found with the current parameters.")
            return

        # Store peak data for overlay drawing
        self._peak_data = {
            "x": np.asarray(peak_result.x_positions, dtype=float),
            "y": np.asarray(peak_result.y_values, dtype=float),
        }

        # Draw peak markers on top of the existing plot
        self._draw_peak_overlay()
        self.statusBar().showMessage(f"Found {len(peak_result.x_positions)} peaks.")

    def _on_fit_requested(self, req: FitRequest) -> None:
        ds = self.state.current_dataset
        if ds is None or req.x_column not in ds.df.columns or req.y_column not in ds.df.columns:
            QMessageBox.warning(self, "Fit Error", "Select valid X and Y columns.")
            return

        x = ds.df[req.x_column].to_numpy()
        y = ds.df[req.y_column].to_numpy()

        # Parse initial params if provided
        p0 = None
        if req.initial_params:
            try:
                p0 = [float(p.strip()) for p in req.initial_params.split(",") if p.strip()]
            except ValueError:
                QMessageBox.warning(self, "Fit Error", "Initial parameters must be comma-separated numbers.")
                return

        # Perform fit
        self.statusBar().showMessage(f"Fitting {req.model_name}...")
        try:
            res = perform_fit(x, y, req.model_name, p0=p0)
        except Exception as e:
            QMessageBox.warning(self, "Fit Error", str(e))
            self.statusBar().showMessage("Fit failed.")
            return

        if not res.success:
            QMessageBox.warning(self, "Fit Failed", res.message)
            self.statusBar().showMessage(res.message)
            return

        # Format results for text box
        lines = [
            f"Model: {res.model_name}",
            f"Equation: {res.expression_str}",
            f"R²: {res.r_squared:.4f}",
            f"χ²: {res.chi_squared:.4e}",
            "",
            "Parameters:"
        ]
        for name, val in res.params.items():
            err = res.param_errors.get(name, 0.0)
            lines.append(f"  {name} = {val:.4e} ± {err:.4e}")

        self.analysis_panel.set_fit_results("\n".join(lines))

        # Store smooth curve data
        self._fit_data = {
            "x": res.x_fit,
            "y": res.y_fit,
        }

        self._draw_fit_overlay()
        self.statusBar().showMessage(f"Fit completed: R² = {res.r_squared:.4f}")

    def _on_clear_fit_requested(self) -> None:
        if self._fit_plot_item is not None:
            self.plot.removeItem(self._fit_plot_item)
            self._fit_plot_item = None
        self._fit_data = None
        self.statusBar().showMessage("Fit overlay cleared.")

    def _on_selection_changed(self, sel: PlotSelection) -> None:
        self.state.selection = sel

        if getattr(sel, "y_col", "") and getattr(sel, "y_err_col", ""):
            if hasattr(self.state, "error_column_map"):
                self.state.error_column_map[str(sel.y_col)] = str(sel.y_err_col)

        self._replot_if_possible()
        self._save_settings_best_effort()

    def _load_csv_path(self, path: Path) -> None:
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

        self.state.current_dataset = Dataset(name=path.name, path=path, df=df)
        if hasattr(self.state, "error_column_map"):
            self.state.error_column_map = {}

        self._update_recent_files(path)
        self._refresh_recent_menu()

        preview_rows = 2000
        preview_df = df.head(preview_rows)
        self.table.setModel(PandasTableModel(preview_df))
        self.table.resizeColumnsToContents()
        self.table_label.setText(f"Dataset: {self.state.current_dataset.name}")

        if not self.table.isVisible():
            self.table.show()
            self.splitter.setSizes([350, 650])

        self.statusBar().showMessage(
            f"Loaded {self.state.current_dataset.name} | {df.shape[0]} rows × {df.shape[1]} cols "
            f"(preview {min(df.shape[0], preview_rows)} rows)"
        )

        all_cols = [str(c) for c in df.columns]
        numeric_cols = [str(c) for c in df.select_dtypes(include="number").columns]
        sel = self.controls.set_columns(all_cols, numeric_cols)
        self.analysis_panel.set_available_columns(all_cols)
        self.analysis_panel.set_peak_columns(all_cols)
        self.analysis_panel.set_fit_columns(all_cols)

        pre_sel = getattr(self.state, "selection", None)
        if (
            pre_sel is not None
            and getattr(pre_sel, "x_col", None) in df.columns
            and getattr(pre_sel, "y_col", None) in df.columns
        ):
            try:
                sel = self.controls.set_selection(
                    str(pre_sel.x_col),
                    str(pre_sel.y_col),
                    str(getattr(pre_sel, "y_err_col", "") or ""),
                )
            except Exception:
                pass

        self.state.selection = sel
        self._replot_if_possible()
        self._save_settings_best_effort()

    def export_plot(self) -> None:
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

        self._load_csv_path(Path(path_str))
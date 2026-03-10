from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import uuid4

import pyqtgraph as pg
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

from func.io.csv_importer import load_csv
from func.models.app_state import AppState
from func.models.dataset import Dataset
from func.models.table_model import PandasTableModel
from func.plotting.plot_service import export_plot_png, render_plot, render_curves
from func.ui.controls_panel import ControlsPanel, PlotSelection
from func.ui.format_panel import FormatPanel
from func.ui.curves_panel import CurvesPanel


class MainWindow(QMainWindow):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state

        self.setWindowTitle("phy-lab")
        self.statusBar().showMessage("Ready")

        self._df_cache: dict[str, object] = {}

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

        # Splitter: left = table preview, right = plot
        self.splitter = QSplitter()
        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.plot)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

        # Controls panel (X/Y selection + plot type)
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

        # Container layout: controls on top, splitter below
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        container_layout.addWidget(self.controls)
        container_layout.addWidget(self.splitter, 1)
        self.setCentralWidget(container)

        self._build_menu()
        self._refresh_recent_menu()
        # Auto-restore last session (best-effort)
        QTimer.singleShot(0, self._restore_last_session)  # type: ignore[arg-type]

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")

        import_action = QAction("Import CSV…", self)
        import_action.triggered.connect(self.import_csv)  # type: ignore[attr-defined]
        file_menu.addAction(import_action)

        # Open Recent
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

    def _get_recent_files(self) -> list[str]:
        rf = getattr(self.state, "recent_files", None)
        if isinstance(rf, list):
            # normalize to strings
            return [str(p) for p in rf if p]
        return []

    def _set_recent_files(self, files: list[str]) -> None:
        if hasattr(self.state, "recent_files"):
            setattr(self.state, "recent_files", files)

    def _update_recent_files(self, path: Path, max_items: int = 10) -> None:
        p = str(path)
        files = [f for f in self._get_recent_files() if f != p]
        files.insert(0, p)
        files = files[:max_items]
        self._set_recent_files(files)
        if hasattr(self.state, "last_file_path"):
            setattr(self.state, "last_file_path", p)

    def _refresh_recent_menu(self) -> None:
        # Populate Open Recent submenu from state.recent_files
        if not hasattr(self, "open_recent_menu"):
            return

        menu = self.open_recent_menu
        menu.clear()

        files = self._get_recent_files()
        if not files:
            menu.setEnabled(False)
            # Keep a placeholder item (disabled) for UX
            placeholder = QAction("(No recent files)", self)
            placeholder.setEnabled(False)
            menu.addAction(placeholder)

            menu.addSeparator()
            clear_recent_action = QAction("Clear Recent", self)
            clear_recent_action.setEnabled(False)
            menu.addAction(clear_recent_action)
            return

        menu.setEnabled(True)

        # Add file entries
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
            # Remove it from recents
            files = [f for f in self._get_recent_files() if f != file_path]
            self._set_recent_files(files)
            self._save_settings_best_effort()
            self._refresh_recent_menu()
            return

        self._load_csv_path(path)

    def _save_settings_best_effort(self) -> None:
        """Persist settings if the settings layer exists.

        Does nothing if func.models.settings / func.io.settings_store do not exist yet.
        """
        try:
            from func.io.settings_store import save_settings  # type: ignore
            from func.models.settings import AppSettings  # type: ignore
        except Exception:
            return

        try:
            settings = AppSettings.from_app_state(self.state)
            save_settings(settings.to_dict())
        except Exception:
            # Never break app flow due to persistence.
            return

    def _restore_last_session(self) -> None:
        """Best-effort: open the last file from settings if it still exists."""
        last = getattr(self.state, "last_file_path", None)
        if not last:
            return

        path = Path(str(last))
        if not path.exists():
            return

        # Load the dataset; _load_csv_path will also refresh menus and plot.
        self._load_csv_path(path)

    def _toggle_format_dock(self, checked: bool) -> None:
        if checked:
            self.format_dock.show()
        else:
            self.format_dock.hide()

    def _on_format_dock_visibility_changed(self, visible: bool) -> None:
        # Keep the View menu toggle in sync.
        if hasattr(self, "toggle_format_action"):
            self.toggle_format_action.blockSignals(True)
            try:
                self.toggle_format_action.setChecked(bool(visible))
            finally:
                self.toggle_format_action.blockSignals(False)

    def _df_provider(self, file_path: str):
        # Return the DataFrame for a given file path, using cache if possible.
        # Each curve's file_path is unique per file, so cache is keyed by file_path.
        if file_path in self._df_cache:
            return self._df_cache[file_path]
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            df = load_csv(path)
        except Exception:
            return None
        # Cache the DataFrame for this file path, but do NOT overwrite previous entries.
        self._df_cache[file_path] = df
        return df

    def _replot_if_possible(self) -> None:
        curves = getattr(self.state, "curves", []) or []
        if curves:
            result = render_curves(
                self.plot,
                self._df_provider,
                curves,
                self.state.format,
                clear=not getattr(self.state, "overlay_enabled", True)
            )
            self.statusBar().showMessage(result.message)
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

    def _on_format_changed(self, fmt) -> None:
        self.state.format = fmt
        self._replot_if_possible()
        self._save_settings_best_effort()

    def _on_overlay_toggled(self, enabled: bool) -> None:
        # Overlay state lives in AppState (not PlotFormat)
        self.state.overlay_enabled = bool(enabled)
        self._save_settings_best_effort()
        self.statusBar().showMessage(
            "Overlay enabled" if self.state.overlay_enabled else "Overlay disabled"
        )

    def _on_add_curve_requested(self) -> None:
        # Add the current selection as a curve (for multi-curve workflow)
        ds = self.state.current_dataset
        sel = self.state.selection
        if ds is None or sel is None or not sel.x_col or not sel.y_col:
            QMessageBox.information(
                self,
                "Nothing to add",
                "Import data and select X/Y before adding a curve.",
            )
            return

        # Maintain overlay logic
        if not hasattr(self.state, "overlay_enabled"):
            self.state.overlay_enabled = True
        if not hasattr(self.state, "curves") or self.state.curves is None:
            self.state.curves = []
        if not getattr(self.state, "overlay_enabled", True):
            self.state.curves = []  # Only clear if overlay disabled
        curve = {
            "id": str(uuid4()),
            "dataset": ds.name,
            "path": str(ds.path),
            "x_col": sel.x_col,
            "y_col": sel.y_col,
            "mode": getattr(self.state.format, "mode", "line"),
            "label": f"{sel.y_col} vs {sel.x_col}",
            "visible": True
        }
        self.state.curves.append(curve)
        self.curves_panel.set_curves(self.state.curves)
        self._replot_if_possible()
        self._save_settings_best_effort()
        self.statusBar().showMessage(
            f"Added curve: {curve['label']} (total {len(self.state.curves)})"
        )

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
        curves = [c for c in getattr(self.state, "curves", []) if not (isinstance(c, dict) and c.get("id") == curve_id)]
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
        # Keep the View menu toggle in sync.
        if hasattr(self, "toggle_curves_action"):
            self.toggle_curves_action.blockSignals(True)
            try:
                self.toggle_curves_action.setChecked(bool(visible))
            finally:
                self.toggle_curves_action.blockSignals(False)

    def _on_selection_changed(self, sel: PlotSelection) -> None:
        self.state.selection = sel
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

        # Store in central state
        self.state.current_dataset = Dataset(name=path.name, path=path, df=df)

        # Update recents
        self._update_recent_files(path)
        self._refresh_recent_menu()

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

        # If settings preloaded a selection, try to keep it (only if columns exist)
        pre_sel = getattr(self.state, "selection", None)
        if pre_sel is not None and getattr(pre_sel, "x_col", None) in df.columns and getattr(pre_sel, "y_col", None) in df.columns:
            try:
                sel = self.controls.set_selection(str(pre_sel.x_col), str(pre_sel.y_col))
            except Exception:
                pass

        # Persist selection and plot using current formatting
        self.state.selection = sel
        self._replot_if_possible()  # Display imported CSV immediately

        # Save settings snapshot
        self._save_settings_best_effort()

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

        self._load_csv_path(Path(path_str))
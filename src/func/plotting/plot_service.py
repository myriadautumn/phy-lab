

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class PlotResult:
    ok: bool
    message: str


def plot_xy(
    plot_widget,
    df,
    x_col: str,
    y_col: str,
    mode: str = "line",
    *,
    clear: bool = True,
):
    """Plot df[x_col] vs df[y_col] on a pyqtgraph PlotWidget.

    Parameters
    ----------
    plot_widget:
        A pyqtgraph PlotWidget (duck-typed). Must support .clear(), .plot(), .setLabel().
    df:
        A pandas DataFrame (duck-typed). Must support .columns and column indexing.
    x_col, y_col:
        Column names to use.
    mode:
        "line" or "scatter".
    clear:
        If True, clears the plot before drawing.

    Returns
    -------
    PlotResult
        ok=True on success; ok=False with a message on failure.
    """

    if df is None:
        return PlotResult(False, "No dataset loaded.")

    if not x_col or not y_col:
        return PlotResult(False, "X and Y columns must be selected.")

    if x_col not in df.columns or y_col not in df.columns:
        return PlotResult(False, "Selected columns were not found in the dataset.")

    try:
        # Coerce to numeric arrays; raise if not convertible.
        x = np.asarray(df[x_col], dtype=float)
        y = np.asarray(df[y_col], dtype=float)
    except Exception:
        return PlotResult(False, "Selected columns could not be converted to numeric values.")

    if clear:
        try:
            plot_widget.clear()
        except Exception:
            # If clearing fails, we still attempt to plot.
            pass

    # Axis labels
    try:
        plot_widget.setLabel("bottom", str(x_col))
        plot_widget.setLabel("left", str(y_col))
    except Exception:
        pass

    try:
        if mode == "scatter":
            plot_widget.plot(x, y, pen=None, symbol="o", symbolSize=5)
        else:
            plot_widget.plot(x, y)
    except Exception as e:
        return PlotResult(False, f"Plot failed: {e}")

    return PlotResult(True, f"Plotted {x_col} vs {y_col} ({mode}).")


def export_plot_png(plot_widget, out_path: Path) -> PlotResult:
    """Export the current pyqtgraph PlotWidget to a PNG image."""

    try:
        import pyqtgraph.exporters as exporters
    except Exception as e:
        return PlotResult(False, f"pyqtgraph exporter not available: {e}")

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return PlotResult(False, f"Could not create output folder: {e}")

    try:
        exporter = exporters.ImageExporter(plot_widget.plotItem)
        # Higher-resolution output than default.
        exporter.parameters()["width"] = 1600
        exporter.export(str(out_path))
    except Exception as e:
        return PlotResult(False, f"Export failed: {e}")

    return PlotResult(True, f"Exported to {out_path}")
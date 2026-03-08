from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from func.models.plot_format import PlotFormat
    from func.ui.controls_panel import PlotSelection


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
    sort_by_x: bool = True,
    line_width: int | None = None,
    marker_size: int = 5,
    curve_name: str | None = None,
    set_labels: bool = True,
) -> PlotResult:
    """Plot df[x_col] vs df[y_col] on a pyqtgraph PlotWidget."""

    if df is None:
        return PlotResult(False, "No dataset loaded.")

    if not x_col or not y_col:
        return PlotResult(False, "X and Y columns must be selected.")

    if x_col not in df.columns or y_col not in df.columns:
        return PlotResult(False, "Selected columns were not found in the dataset.")

    try:
        x = np.asarray(df[x_col], dtype=float)
        y = np.asarray(df[y_col], dtype=float)
    except Exception:
        return PlotResult(False, "Selected columns could not be converted to numeric values.")

    mask = np.isfinite(x) & np.isfinite(y)
    if mask.ndim != 1:
        mask = np.ravel(mask)
    x = x[mask]
    y = y[mask]

    if x.size == 0:
        return PlotResult(False, "No plottable numeric data after filtering NaN/inf values.")

    if sort_by_x and mode != "scatter":
        order = np.argsort(x)
        x = x[order]
        y = y[order]

    if clear:
        try:
            plot_widget.clear()
        except Exception:
            pass

    if set_labels:
        # Default axis labels (render_plot may override)
        try:
            plot_widget.setLabel("bottom", str(x_col))
            plot_widget.setLabel("left", str(y_col))
        except Exception:
            pass

    try:
        if mode == "scatter":
            if curve_name:
                plot_widget.plot(x, y, pen=None, symbol="o", symbolSize=int(marker_size), name=curve_name)
            else:
                plot_widget.plot(x, y, pen=None, symbol="o", symbolSize=int(marker_size))
        else:
            if line_width is None:
                if curve_name:
                    plot_widget.plot(x, y, name=curve_name)
                else:
                    plot_widget.plot(x, y)
            else:
                try:
                    import pyqtgraph as pg

                    pen = pg.mkPen(width=int(line_width))
                    if curve_name:
                        plot_widget.plot(x, y, pen=pen, name=curve_name)
                    else:
                        plot_widget.plot(x, y, pen=pen)
                except Exception:
                    if curve_name:
                        plot_widget.plot(x, y, name=curve_name)
                    else:
                        plot_widget.plot(x, y)
    except Exception as e:
        return PlotResult(False, f"Plot failed: {e}")

    return PlotResult(True, f"Plotted {x_col} vs {y_col} ({mode}).")


def render_plot(
    plot_widget,
    df,
    selection: "PlotSelection",
    fmt: "PlotFormat",
    *,
    clear: bool = True,
) -> PlotResult:
    """Render the plot using PlotSelection (what) + PlotFormat (how)."""

    if df is None:
        return PlotResult(False, "No dataset loaded.")

    x_col = (selection.x_col or "").strip()
    y_col = (selection.y_col or "").strip()
    if not x_col or not y_col:
        return PlotResult(False, "X and Y columns must be selected.")

    if clear:
        try:
            plot_widget.clear()
        except Exception:
            pass

    # Grid
    try:
        plot_widget.showGrid(x=bool(fmt.grid), y=bool(fmt.grid), alpha=0.3)
    except Exception:
        pass

    # Scales
    try:
        plot_widget.setLogMode(x=(fmt.x_scale == "log"), y=(fmt.y_scale == "log"))
    except Exception:
        pass

    # Legend
    try:
        legend = getattr(plot_widget.plotItem, "legend", None)
        if bool(fmt.legend):
            if legend is None:
                plot_widget.addLegend()
        else:
            if legend is not None:
                plot_widget.plotItem.removeItem(legend)
                plot_widget.plotItem.legend = None
    except Exception:
        pass

    # Title
    try:
        if bool(fmt.title_enabled) and (fmt.title or "").strip():
            plot_widget.setTitle((fmt.title or "").strip())
        else:
            plot_widget.setTitle("")
    except Exception:
        pass

    # Axis labels
    xlabel = x_col
    ylabel = y_col
    if bool(fmt.x_label_enabled) and (fmt.x_label or "").strip():
        xlabel = (fmt.x_label or "").strip()
    if bool(fmt.y_label_enabled) and (fmt.y_label or "").strip():
        ylabel = (fmt.y_label or "").strip()

    try:
        plot_widget.setLabel("bottom", xlabel)
        plot_widget.setLabel("left", ylabel)
    except Exception:
        pass

    curve_name = None
    if bool(fmt.legend):
        curve_name = f"{y_col} vs {x_col}"

    res = plot_xy(
        plot_widget,
        df,
        x_col,
        y_col,
        fmt.mode,
        clear=False,
        sort_by_x=bool(fmt.sort_by_x),
        line_width=fmt.line_width,
        marker_size=int(fmt.marker_size),
        curve_name=curve_name,
        set_labels=False,
    )
    if not res.ok:
        return res

    # Limits
    try:
        if fmt.x_limits.auto:
            plot_widget.enableAutoRange(axis="x", enable=True)
        else:
            plot_widget.enableAutoRange(axis="x", enable=False)
            if fmt.x_limits.vmin is not None and fmt.x_limits.vmax is not None:
                plot_widget.setXRange(float(fmt.x_limits.vmin), float(fmt.x_limits.vmax), padding=0)
            elif fmt.x_limits.vmin is not None:
                xr = plot_widget.plotItem.vb.viewRange()[0]
                plot_widget.setXRange(float(fmt.x_limits.vmin), float(xr[1]), padding=0)
            elif fmt.x_limits.vmax is not None:
                xr = plot_widget.plotItem.vb.viewRange()[0]
                plot_widget.setXRange(float(xr[0]), float(fmt.x_limits.vmax), padding=0)

        if fmt.y_limits.auto:
            plot_widget.enableAutoRange(axis="y", enable=True)
        else:
            plot_widget.enableAutoRange(axis="y", enable=False)
            if fmt.y_limits.vmin is not None and fmt.y_limits.vmax is not None:
                plot_widget.setYRange(float(fmt.y_limits.vmin), float(fmt.y_limits.vmax), padding=0)
            elif fmt.y_limits.vmin is not None:
                yr = plot_widget.plotItem.vb.viewRange()[1]
                plot_widget.setYRange(float(fmt.y_limits.vmin), float(yr[1]), padding=0)
            elif fmt.y_limits.vmax is not None:
                yr = plot_widget.plotItem.vb.viewRange()[1]
                plot_widget.setYRange(float(yr[0]), float(fmt.y_limits.vmax), padding=0)
    except Exception:
        pass

    return PlotResult(True, f"Rendered {y_col} vs {x_col}")


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
        exporter.parameters()["width"] = 1600
        exporter.export(str(out_path))
    except Exception as e:
        return PlotResult(False, f"Export failed: {e}")

    return PlotResult(True, f"Exported to {out_path}")
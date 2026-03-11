from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg

if TYPE_CHECKING:
    from func.models.plot_format import PlotFormat
    from func.ui.controls_panel import PlotSelection


DEFAULT_COLOR_CYCLE = ['b', 'r', 'g', 'm', 'c', 'y', 'k']
DEFAULT_SYMBOL_CYCLE = ['o', 's', 't', 'd', '+', 'x']


@dataclass(frozen=True)
class PlotResult:
    ok: bool
    message: str


def _normalize_xy_error(df, x_col: str, y_col: str, y_err_col: str | None = None):
    """Extract numeric x/y and optional symmetric y-error arrays.

    Returns
    -------
    tuple[np.ndarray, np.ndarray, np.ndarray | None]
        x, y, y_err arrays after numeric coercion and NaN/inf filtering.
    """
    if df is None:
        raise ValueError("No dataset loaded.")
    if not x_col or not y_col:
        raise ValueError("X and Y columns must be selected.")
    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError("Selected X/Y columns were not found in the dataset.")

    x = np.asarray(df[x_col], dtype=float)
    y = np.asarray(df[y_col], dtype=float)

    y_err = None
    if y_err_col:
        if y_err_col not in df.columns:
            raise ValueError("Selected Y error column was not found in the dataset.")
        y_err = np.asarray(df[y_err_col], dtype=float)

    mask = np.isfinite(x) & np.isfinite(y)
    if y_err is not None:
        mask = mask & np.isfinite(y_err)

    if mask.ndim != 1:
        mask = np.ravel(mask)

    x = x[mask]
    y = y[mask]
    if y_err is not None:
        y_err = np.abs(y_err[mask])

    if x.size == 0:
        raise ValueError("No plottable numeric data after filtering NaN/inf values.")

    return x, y, y_err


def _plot_error_bars(plot_widget, x: np.ndarray, y: np.ndarray, y_err: np.ndarray | None) -> None:
    """Plot symmetric Y error bars on the current plot.

    pyqtgraph ErrorBarItem uses `top` and `bottom` lengths, so we pass the same
    symmetric error to both.
    """
    if y_err is None or len(y_err) == 0:
        return

    # Ensure y_err is a numeric array and non-empty
    y_err = np.asarray(y_err, dtype=float)
    if y_err.size == 0:
        return

    err_item = pg.ErrorBarItem(x=x, y=y, top=y_err, bottom=y_err, beam=0.15)
    plot_widget.addItem(err_item)


def plot_xy(
    plot_widget,
    df,
    x_col: str,
    y_col: str,
    mode: str = "line",
    *,
    y_err_col: str | None = None,
    color: str | None = None,
    symbol: str | None = None,
    clear: bool = False,
    sort_by_x: bool = True,
    line_width: int | None = None,
    marker_size: int = 5,
    curve_name: str | None = None,
    set_labels: bool = True,
) -> PlotResult:
    """Plot df[x_col] vs df[y_col] on a pyqtgraph PlotWidget."""

    try:
        x, y, y_err = _normalize_xy_error(df, x_col, y_col, y_err_col)
    except ValueError as e:
        return PlotResult(False, str(e))
    except Exception:
        return PlotResult(False, "Selected columns could not be converted to numeric values.")

    if sort_by_x and mode != "scatter":
        order = np.argsort(x)
        x = x[order]
        y = y[order]
        if y_err is not None:
            y_err = y_err[order]

    if clear:
        plot_widget.clear()

    if set_labels:
        # Default axis labels (render_plot may override)
        plot_widget.setLabel("bottom", str(x_col))
        plot_widget.setLabel("left", str(y_col))

    mode = str(mode) if mode else "line"
    if mode == "scatter":
        # In pyqtgraph, pen=None draws a default line. pen=pg.mkPen(None) hides the line.
        plot_widget.plot(x, y, pen=pg.mkPen(None),
                         symbol=symbol or 'o', symbolSize=int(marker_size), name=curve_name,
                         symbolBrush=color or 'b')
    else:
        pen = pg.mkPen(color=color, width=int(line_width)) if color else (pg.mkPen(width=int(line_width)) if line_width else None)
        plot_widget.plot(x, y, pen=pen, name=curve_name)

    _plot_error_bars(plot_widget, x, y, y_err)

    return PlotResult(True, f"Plotted {x_col} vs {y_col} ({mode}).")

def _apply_format(plot_widget, fmt: "PlotFormat") -> None:
    """Apply shared formatting (grid, scales, legend, title) to a plot widget."""
    plot_widget.showGrid(x=bool(fmt.grid), y=bool(fmt.grid), alpha=0.3)
    plot_widget.setLogMode(x=(fmt.x_scale == "log"), y=(fmt.y_scale == "log"))

    # Legend
    legend = getattr(plot_widget.plotItem, "legend", None)
    if bool(fmt.legend):
        if legend is None:
            plot_widget.addLegend()
    else:
        if legend is not None:
            plot_widget.plotItem.removeItem(legend)
            plot_widget.plotItem.legend = None

    # Title
    if bool(fmt.title_enabled) and (fmt.title or "").strip():
        plot_widget.setTitle((fmt.title or "").strip())
    else:
        plot_widget.setTitle("")


def _apply_limits(plot_widget, fmt: "PlotFormat") -> None:
    """Apply axis limits from PlotFormat to a plot widget."""
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
        plot_widget.clear()

    _apply_format(plot_widget, fmt)

    # Axis labels
    xlabel = x_col
    ylabel = y_col
    if bool(fmt.x_label_enabled) and (fmt.x_label or "").strip():
        xlabel = (fmt.x_label or "").strip()
    if bool(fmt.y_label_enabled) and (fmt.y_label or "").strip():
        ylabel = (fmt.y_label or "").strip()

    plot_widget.setLabel("bottom", xlabel)
    plot_widget.setLabel("left", ylabel)

    curve_name = None
    if bool(fmt.legend):
        curve_name = f"{y_col} vs {x_col}"

    res = plot_xy(
        plot_widget,
        df,
        x_col,
        y_col,
        fmt.mode,
        y_err_col=(selection.y_err_col or "").strip() or None,
        clear=False,
        sort_by_x=bool(fmt.sort_by_x),
        line_width=fmt.line_width,
        marker_size=int(fmt.marker_size),
        curve_name=curve_name,
        set_labels=False,
    )
    if not res.ok:
        return res

    _apply_limits(plot_widget, fmt)

    return PlotResult(True, f"Rendered {y_col} vs {x_col}")


def render_curves(
    plot_widget,
    df_provider,
    curves,
    fmt: "PlotFormat",
    *,
    clear: bool = True,
) -> PlotResult:
    """Render multiple curves on the same plot.

    Parameters
    ----------
    plot_widget:
        pyqtgraph PlotWidget (duck-typed).
    df_provider:
        Callable that takes a curve path (str) and returns a pandas DataFrame.
        Signature: df_provider(path: str) -> DataFrame | None
    curves:
        Iterable of curve specs (duck-typed). Expected keys/attrs:
        - path (str)
        - x_col (str)
        - y_col (str)
        - mode ("line"|"scatter")
        - label (str)
        - visible (bool)
    fmt:
        Global PlotFormat applied once (grid/title/legend/scales/limits/style).
    clear:
        Clear the plot before drawing.

    Returns
    -------
    PlotResult
    """

    if curves is None or len(curves) == 0:
        if clear:
            plot_widget.clear()
        return PlotResult(False, "No curves to render.")

    # Collect visible curves
    visible = []
    for c in curves:
        try:
            v = bool(c.get("visible", True))
        except Exception:
            v = bool(getattr(c, "visible", True))
        if v:
            visible.append(c)

    if not visible:
        if clear:
            plot_widget.clear()
        return PlotResult(False, "No visible curves to render.")

    # Clear plot only if clear is True
    if clear:
        plot_widget.clear()

    _apply_format(plot_widget, fmt)

    # Draw each curve independently without clearing the plot
    rendered = 0
    for idx, c in enumerate(visible):
        path = None
        x_col = None
        y_col = None
        y_err_col = None
        mode = None
        label = None

        try:
            path = c.get("path")
            x_col = c.get("x_col")
            y_col = c.get("y_col")
            y_err_col = c.get("y_err_col")
            mode = c.get("mode", fmt.mode)
            label = c.get("label")
        except Exception:
            path = getattr(c, "path", None)
            x_col = getattr(c, "x_col", None)
            y_col = getattr(c, "y_col", None)
            y_err_col = getattr(c, "y_err_col", None)
            mode = getattr(c, "mode", fmt.mode)
            label = getattr(c, "label", None)

        if not path or not x_col or not y_col:
            continue

        df = df_provider(str(path))
        if df is None:
            continue

        # Auto-assign color and symbol if not specified
        try:
            color = c.get('color')
        except Exception:
            color = getattr(c, 'color', None)
        if not color:
            color = DEFAULT_COLOR_CYCLE[idx % len(DEFAULT_COLOR_CYCLE)]

        try:
            symbol = c.get('symbol')
        except Exception:
            symbol = getattr(c, 'symbol', None)
        if not symbol:
            symbol = DEFAULT_SYMBOL_CYCLE[idx % len(DEFAULT_SYMBOL_CYCLE)]

        curve_name = str(label) if label else f"{y_col} vs {x_col}"
        mode_str = str(mode) if mode else fmt.mode
        res = plot_xy(
            plot_widget,
            df,
            str(x_col),
            str(y_col),
            mode_str,
            y_err_col=str(y_err_col).strip() or None if y_err_col is not None else None,
            clear=False,
            sort_by_x=bool(fmt.sort_by_x),
            line_width=fmt.line_width,
            marker_size=int(fmt.marker_size),
            curve_name=curve_name if bool(fmt.legend) else None,
            set_labels=False,
            color=color,
            symbol=symbol
        )
        if res.ok:
            rendered += 1

    if rendered == 0:
        return PlotResult(False, "No curves could be rendered (missing files/columns).")

    # Apply axis labels after all curves are drawn
    first = visible[0]
    try:
        x_col0 = str(first.get("x_col", ""))
        y_col0 = str(first.get("y_col", ""))
    except Exception:
        x_col0 = str(getattr(first, "x_col", ""))
        y_col0 = str(getattr(first, "y_col", ""))

    xlabel = (fmt.x_label or "").strip() if bool(fmt.x_label_enabled) else (x_col0 or "x")
    ylabel = (fmt.y_label or "").strip() if bool(fmt.y_label_enabled) else (y_col0 or "y")

    plot_widget.setLabel("bottom", xlabel)
    plot_widget.setLabel("left", ylabel)

    _apply_limits(plot_widget, fmt)

    return PlotResult(True, f"Rendered {rendered} curve(s)")

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
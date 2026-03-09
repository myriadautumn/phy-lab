

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from func.models.plot_format import AxisLimits, PlotFormat
from func.ui.controls_panel import PlotSelection


def _get_str(d: Dict[str, Any], key: str, default: str = "") -> str:
    v = d.get(key, default)
    return default if v is None else str(v)


def _get_bool(d: Dict[str, Any], key: str, default: bool = False) -> bool:
    v = d.get(key, default)
    return bool(v) if v is not None else default


def _get_int(d: Dict[str, Any], key: str, default: int = 0) -> int:
    v = d.get(key, default)
    try:
        return int(v)
    except Exception:
        return default


def _get_float_or_none(d: Dict[str, Any], key: str) -> Optional[float]:
    if key not in d:
        return None
    v = d.get(key)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


@dataclass
class AppSettings:
    """Persisted application settings (JSON-serializable)."""

    version: int = 1

    # Paths
    last_file_path: Optional[str] = None
    recent_files: List[str] = field(default_factory=list)

    # Plot selection
    selection: Optional[PlotSelection] = None

    # Plot formatting
    plot_format: PlotFormat = field(default_factory=PlotFormat)

    @staticmethod
    def from_app_state(state) -> "AppSettings":
        """Create persisted settings from a live AppState (duck-typed)."""
        last_file_path = getattr(state, "last_file_path", None)
        recent_files = getattr(state, "recent_files", [])
        selection = getattr(state, "selection", None)
        plot_format = getattr(state, "format", PlotFormat())

        # Normalize
        if recent_files is None:
            recent_files = []
        recent_files = [str(p) for p in recent_files if p]

        if last_file_path is not None:
            last_file_path = str(last_file_path)

        return AppSettings(
            last_file_path=last_file_path,
            recent_files=recent_files,
            selection=selection,
            plot_format=plot_format,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-safe dictionary."""
        d: Dict[str, Any] = {
            "version": self.version,
            "last_file_path": self.last_file_path,
            "recent_files": list(self.recent_files),
            "selection": None,
            "plot_format": None,
        }

        if self.selection is not None:
            d["selection"] = {"x_col": self.selection.x_col, "y_col": self.selection.y_col}

        # PlotFormat is nested; convert to dict manually for stability
        pf = self.plot_format
        d["plot_format"] = {
            "mode": pf.mode,
            "title_enabled": pf.title_enabled,
            "title": pf.title,
            "x_label_enabled": pf.x_label_enabled,
            "x_label": pf.x_label,
            "y_label_enabled": pf.y_label_enabled,
            "y_label": pf.y_label,
            "grid": pf.grid,
            "legend": pf.legend,
            "x_scale": pf.x_scale,
            "y_scale": pf.y_scale,
            "x_limits": {
                "auto": pf.x_limits.auto,
                "vmin": pf.x_limits.vmin,
                "vmax": pf.x_limits.vmax,
            },
            "y_limits": {
                "auto": pf.y_limits.auto,
                "vmin": pf.y_limits.vmin,
                "vmax": pf.y_limits.vmax,
            },
            "line_width": pf.line_width,
            "marker_size": pf.marker_size,
            "sort_by_x": pf.sort_by_x,
        }

        return d

    @staticmethod
    def from_dict(raw: Dict[str, Any]) -> "AppSettings":
        """Parse settings from a dictionary (defensive)."""
        if raw is None:
            return AppSettings()

        version = _get_int(raw, "version", 1)

        last_file_path = raw.get("last_file_path")
        if last_file_path is not None:
            last_file_path = str(last_file_path)

        recent_files_raw = raw.get("recent_files", [])
        recent_files: List[str] = []
        if isinstance(recent_files_raw, list):
            recent_files = [str(p) for p in recent_files_raw if p]

        # Selection
        selection = None
        sel_raw = raw.get("selection")
        if isinstance(sel_raw, dict):
            x_col = _get_str(sel_raw, "x_col", "")
            y_col = _get_str(sel_raw, "y_col", "")
            if x_col and y_col:
                selection = PlotSelection(x_col=x_col, y_col=y_col)

        # Plot format
        pf_raw = raw.get("plot_format")
        pf = PlotFormat()
        if isinstance(pf_raw, dict):
            pf.mode = _get_str(pf_raw, "mode", pf.mode) or pf.mode

            pf.title_enabled = _get_bool(pf_raw, "title_enabled", pf.title_enabled)
            pf.title = _get_str(pf_raw, "title", pf.title)

            pf.x_label_enabled = _get_bool(pf_raw, "x_label_enabled", pf.x_label_enabled)
            pf.x_label = _get_str(pf_raw, "x_label", pf.x_label)

            pf.y_label_enabled = _get_bool(pf_raw, "y_label_enabled", pf.y_label_enabled)
            pf.y_label = _get_str(pf_raw, "y_label", pf.y_label)

            pf.grid = _get_bool(pf_raw, "grid", pf.grid)
            pf.legend = _get_bool(pf_raw, "legend", pf.legend)

            pf.x_scale = _get_str(pf_raw, "x_scale", pf.x_scale) or pf.x_scale
            pf.y_scale = _get_str(pf_raw, "y_scale", pf.y_scale) or pf.y_scale

            # Limits
            xlim_raw = pf_raw.get("x_limits")
            if isinstance(xlim_raw, dict):
                pf.x_limits = AxisLimits(
                    auto=_get_bool(xlim_raw, "auto", True),
                    vmin=_get_float_or_none(xlim_raw, "vmin"),
                    vmax=_get_float_or_none(xlim_raw, "vmax"),
                )
            ylim_raw = pf_raw.get("y_limits")
            if isinstance(ylim_raw, dict):
                pf.y_limits = AxisLimits(
                    auto=_get_bool(ylim_raw, "auto", True),
                    vmin=_get_float_or_none(ylim_raw, "vmin"),
                    vmax=_get_float_or_none(ylim_raw, "vmax"),
                )

            lw = pf_raw.get("line_width")
            try:
                pf.line_width = None if lw in (None, "") else int(lw)
            except Exception:
                pf.line_width = None

            pf.marker_size = _get_int(pf_raw, "marker_size", pf.marker_size) or pf.marker_size
            pf.sort_by_x = _get_bool(pf_raw, "sort_by_x", pf.sort_by_x)

        return AppSettings(
            version=version,
            last_file_path=last_file_path,
            recent_files=recent_files,
            selection=selection,
            plot_format=pf,
        )
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AxisLimits:
    auto: bool = True
    vmin: Optional[float] = None
    vmax: Optional[float] = None


@dataclass
class PlotFormat:
    # Plot mode: "line" or "scatter"
    mode: str = "line"

    # Text
    title_enabled: bool = False
    title: str = ""

    x_label_enabled: bool = False
    x_label: str = ""

    y_label_enabled: bool = False
    y_label: str = ""

    # Display
    grid: bool = True
    legend: bool = False

    # Scales
    x_scale: str = "linear"  # "linear" or "log"
    y_scale: str = "linear"  # "linear" or "log"

    # Limits
    x_limits: AxisLimits = field(default_factory=AxisLimits)
    y_limits: AxisLimits = field(default_factory=AxisLimits)

    # Style
    line_width: Optional[int] = None
    marker_size: int = 5
    sort_by_x: bool = True
    color: Optional[str] = None
    symbol: Optional[str] = None
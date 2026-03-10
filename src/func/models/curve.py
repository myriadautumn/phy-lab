

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CurveSpec:
    """Specification for a single curve in a multi-curve plot."""

    id: str

    # Data source
    dataset: str  # e.g., filename
    path: str  # full path to the source file

    # Columns
    x_col: str
    y_col: str

    # Plotting
    mode: str = "line"  # "line" or "scatter"
    label: str = ""
    visible: bool = True
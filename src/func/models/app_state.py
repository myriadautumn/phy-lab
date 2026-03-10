from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from func.models.plot_format import PlotFormat
from func.ui.controls_panel import PlotSelection

if TYPE_CHECKING:
    from func.models.dataset import Dataset
    from func.models.curve import CurveSpec

@dataclass
class AppState:
    """Centralized application state.

    Keep UI components loosely coupled by storing shared state here.
    """

    current_dataset: Optional[Dataset] = None

    # Analysis / transformation workflow
    derived_datasets: list[Dataset] = field(default_factory=list)
    last_analysis_expression: Optional[str] = None
    error_column_map: dict[str, str] = field(default_factory=dict)

    # Persistence / navigation
    last_file_path: Optional[str] = None
    recent_files: list[str] = field(default_factory=list)
    selection: Optional[PlotSelection] = None
    format: PlotFormat = field(default_factory=PlotFormat)

    # Multi-curve plotting
    overlay_enabled: bool = True  # enable overlay by default
    curves: list[CurveSpec] = field(default_factory=list)
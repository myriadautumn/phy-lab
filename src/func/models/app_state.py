from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from func.models.plot_format import PlotFormat
from func.ui.controls_panel import PlotSelection

if TYPE_CHECKING:
    from func.models.dataset import Dataset


@dataclass
class AppState:
    """Centralized application state.

    Keep UI components loosely coupled by storing shared state here.
    """

    current_dataset: Optional["Dataset"] = None
    # Persistence / navigation
    last_file_path: Optional[str] = None
    recent_files: list[str] = field(default_factory=list)
    selection: Optional[PlotSelection] = None
    format: PlotFormat = field(default_factory=PlotFormat)
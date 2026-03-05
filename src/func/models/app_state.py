from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from func.models.dataset import Dataset
from func.ui.controls_panel import PlotSelection


@dataclass
class AppState:
    """Centralized application state.

    Keep UI components loosely coupled by storing shared state here.
    """
    current_dataset: Optional[Dataset] = None
    selection: Optional[PlotSelection] = None
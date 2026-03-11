

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional

from func.models.peak_table_model import PeakTableModel

class PeakResult:
    def __init__(
        self,
        dataset_name: str,
        x_positions: np.ndarray,
        y_values: np.ndarray,
        widths: Optional[np.ndarray] = None,
        prominences: Optional[np.ndarray] = None,
    ):
        self.dataset_name = dataset_name
        self.x_positions = x_positions
        self.y_values = y_values
        self.widths = widths
        self.prominences = prominences

    def to_table_model(self) -> PeakTableModel:
        """Convert the PeakResult to a Qt Table Model for UI display"""
        data = {
            'Peak #': np.arange(1, len(self.x_positions) + 1),
            'X': self.x_positions,
            'Y': self.y_values,
        }
        if self.widths is not None:
            data['Width'] = self.widths
        if self.prominences is not None:
            data['Prominence'] = self.prominences
        df = pd.DataFrame(data)
        return PeakTableModel(df)
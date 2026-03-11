

from typing import Optional, List
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, peak_widths

# Import Dataset and PeakTableModel from your project structure
from func.models.dataset import Dataset
from func.models.peak_table_model import PeakTableModel


class PeakResult:
    def __init__(
        self,
        dataset_name: str,
        x_positions: np.ndarray,
        y_values: np.ndarray,
        widths: Optional[np.ndarray] = None,
        prominences: Optional[np.ndarray] = None
    ):
        self.dataset_name = dataset_name
        self.x_positions = x_positions
        self.y_values = y_values
        self.widths = widths
        self.prominences = prominences


def detect_peaks(
    dataset: Dataset,
    x_col: str,
    y_col: str,
    height: Optional[float] = None,
    distance: Optional[int] = None,
    prominence: Optional[float] = None,
    width: Optional[float] = None
) -> PeakResult:
    """Detect peaks in the dataset using SciPy's find_peaks"""
    df = dataset.df
    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError(f"Columns {x_col} or {y_col} not found in dataset.")

    x = df[x_col].to_numpy()
    y = df[y_col].to_numpy()

    # Detect peaks
    peaks, properties = find_peaks(y, height=height, distance=distance, prominence=prominence)

    # Compute widths if requested or if properties contain widths
    widths_arr = None
    if width is not None or 'widths' in properties:
        results_half = peak_widths(y, peaks, rel_height=0.5)
        widths_arr = results_half[0]

    peak_vals = y[peaks]
    peak_x = x[peaks]
    prominences = properties.get('prominences')

    return PeakResult(dataset.name, peak_x, peak_vals, widths_arr, prominences)


def build_peak_table_model(peak_result: PeakResult) -> PeakTableModel:
    """Build a Qt Table Model for displaying peaks"""
    data = {
        'Peak #': np.arange(1, len(peak_result.x_positions) + 1),
        'X': peak_result.x_positions,
        'Y': peak_result.y_values,
    }
    if peak_result.widths is not None:
        data['Width'] = peak_result.widths
    if peak_result.prominences is not None:
        data['Prominence'] = peak_result.prominences

    df = pd.DataFrame(data)
    return PeakTableModel(df)
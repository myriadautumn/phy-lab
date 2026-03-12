"""Simple statistics engine for bounded Regions of Interest (ROI)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class RoiStats:
    """Statistics calculated for data points inside a Region of Interest."""
    
    count: int
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    y_mean: float
    y_std: float
    area: float
    

def get_roi_mask(x: np.ndarray, x_range: Optional[tuple[float, float]]) -> np.ndarray:
    """Return a boolean mask for the x array based on x_range."""
    if x_range is None:
        return np.ones_like(x, dtype=bool)
    
    x_min, x_max = x_range
    # Ensure min <= max (LinearRegionItem can sometimes swap them if user drags weirdly)
    if x_min > x_max:
        x_min, x_max = x_max, x_min
        
    return (x >= x_min) & (x <= x_max)


def compute_roi_stats(x: np.ndarray, y: np.ndarray, x_range: Optional[tuple[float, float]] = None) -> Optional[RoiStats]:
    """Calculate statistics for the subset of data falling inside the x_range.
    
    Parameters
    ----------
    x, y : Array-like data.
    x_range : (min_val, max_val) bounding the Region of Interest on the X axis.
              If None, computes stats for the whole array.
              
    Returns
    -------
    RoiStats object, or None if the region contains no data points.
    """
    if len(x) == 0 or len(y) == 0 or len(x) != len(y):
        return None
        
    mask = get_roi_mask(x, x_range)
    x_bounded = x[mask]
    y_bounded = y[mask]
    
    count = len(x_bounded)
    if count == 0:
        return None
        
    # Sort by X before integrating to avoid negative areas from unordered data
    sort_idx = np.argsort(x_bounded)
    x_sorted = x_bounded[sort_idx]
    y_sorted = y_bounded[sort_idx]
        
    area = float(np.trapz(y_sorted, x_sorted))
    
    return RoiStats(
        count=count,
        x_min=float(x_bounded.min()),
        x_max=float(x_bounded.max()),
        y_min=float(y_bounded.min()),
        y_max=float(y_bounded.max()),
        y_mean=float(y_bounded.mean()),
        y_std=float(y_bounded.std(ddof=1) if count > 1 else 0.0),
        area=area,
    )

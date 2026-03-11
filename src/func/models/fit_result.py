from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FitResult:
    """Result of a curve fit operation."""

    model_name: str
    expression_str: str
    params: dict[str, float] = field(default_factory=dict)
    param_errors: dict[str, float] = field(default_factory=dict)
    r_squared: float = 0.0
    chi_squared: float = 0.0
    x_fit: Optional[object] = None  # numpy array
    y_fit: Optional[object] = None  # numpy array
    success: bool = False
    message: str = ""

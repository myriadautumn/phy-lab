from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


@dataclass
class Dataset:
    """Represents one dataset loaded into the application.

    This stays focused on a single dataset only. App-wide runtime state
    belongs in AppState.
    """

    name: str                 # usually the filename or derived dataset name
    path: Optional[Path]      # full path to the source file; None for derived datasets
    df: "pd.DataFrame"       # the loaded or generated data

    # Dataset-level metadata for plotting / analysis
    source_name: Optional[str] = None
    derived: bool = False

    # Optional column metadata for uncertainty / error-bar workflows
    x_col: Optional[str] = None
    y_col: Optional[str] = None
    y_err_col: Optional[str] = None          # symmetric Y error
    y_err_plus_col: Optional[str] = None     # asymmetric +Y error
    y_err_minus_col: Optional[str] = None    # asymmetric -Y error

    # Keep room for future dataset-specific metadata without polluting AppState
    metadata: dict[str, object] = field(default_factory=dict)
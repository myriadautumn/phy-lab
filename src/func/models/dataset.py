from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


@dataclass
class Dataset:
    name: str          # usually the filename
    path: Path         # full path to the file
    df: "pd.DataFrame" # the loaded data
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file into a DataFrame.

    MVP assumptions:
    - First row is the header.
    - Standard CSV formatting.

    Raises:
        ValueError: if the parsed dataset is empty.
        Exception: bubbles up pandas parsing errors.
    """
    df = pd.read_csv(path)

    if df.shape[0] == 0 or df.shape[1] == 0:
        raise ValueError("The file was read, but it contains no rows or columns.")

    return df
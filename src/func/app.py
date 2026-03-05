from __future__ import annotations

import sys


def _missing(dep: str, install_hint: str) -> None:
    print(
        f"Missing dependency: {dep}.\n"
        "Install the required packages in your active venv, e.g.:\n"
        f"  {install_hint}\n",
        file=sys.stderr,
    )


def main() -> int:
    try:
        from PyQt6.QtWidgets import QApplication
    except Exception:
        _missing("PyQt6", "python -m pip install PyQt6")
        return 1

    # Keep these imports here so missing deps show a clear message.
    try:
        import pyqtgraph  # noqa: F401
    except Exception:
        _missing("pyqtgraph", "python -m pip install pyqtgraph")
        return 1

    try:
        import numpy  # noqa: F401
    except Exception:
        _missing("numpy", "python -m pip install numpy")
        return 1

    try:
        import pandas  # noqa: F401
    except Exception:
        _missing("pandas", "python -m pip install pandas")
        return 1

    from func.models.app_state import AppState
    from func.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    state = AppState()
    win = MainWindow(state)
    win.resize(900, 600)
    win.show()
    return app.exec()
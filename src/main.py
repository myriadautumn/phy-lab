"""phy-lab entry point.

Run:
  python src/main.py

This starts a minimal GUI (PyQt6 + pyqtgraph) if installed.
"""

from __future__ import annotations

import sys


def _missing(dep: str) -> None:
    print(
        f"Missing dependency: {dep}.\n"
        "Install the required packages in your active venv, e.g.:\n"
        "  python -m pip install PyQt6 pyqtgraph numpy\n",
        file=sys.stderr,
    )


def main() -> int:
    # Import GUI deps lazily so we can show a helpful message if not installed.
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow
    except Exception:
        _missing("PyQt6")
        return 1

    try:
        import pyqtgraph as pg
    except Exception:
        _missing("pyqtgraph")
        return 1

    try:
        import numpy as np
    except Exception:
        _missing("numpy")
        return 1

    app = QApplication(sys.argv)

    win = QMainWindow()
    win.setWindowTitle("phy-lab")

    plot = pg.PlotWidget()
    plot.setBackground(None)
    plot.setLabel("bottom", "x")
    plot.setLabel("left", "y")
    plot.showGrid(x=True, y=True, alpha=0.3)

    # Demo dataset: damped sine wave
    x = np.linspace(0, 10, 1000)
    y = np.exp(-0.15 * x) * np.sin(2 * np.pi * 1.2 * x)
    plot.plot(x, y)

    win.setCentralWidget(plot)
    win.resize(900, 600)
    win.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
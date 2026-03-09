from __future__ import annotations

import sys


def _missing(dep: str, install_hint: str) -> None:
    print(
        f"Missing dependency: {dep}.\n"
        "Install the required packages in your active venv, e.g.:\n"
        f"  {install_hint}\n",
        file=sys.stderr,
    )


def _load_app_state_from_settings(state) -> None:
    """Best-effort settings hydration.

    This function is intentionally defensive:
    - If the settings modules are not present yet, it does nothing.
    - If the settings file is missing/corrupt, it does nothing.

    Expected (when implemented):
    - func.io.settings_store.load_settings() -> dict
    - func.models.settings.AppSettings.from_dict(d)
    """

    try:
        from func.io.settings_store import load_settings  # type: ignore
        from func.models.settings import AppSettings  # type: ignore
    except Exception:
        # Settings layer not added yet.
        return

    try:
        raw = load_settings()
        if not raw:
            return
        settings = AppSettings.from_dict(raw)
    except Exception:
        # Corrupt/invalid settings should never prevent app start.
        return

    # Hydrate known fields on AppState (only if they exist)
    try:
        # selection
        if getattr(settings, "selection", None) is not None:
            state.selection = settings.selection

        # format
        if getattr(settings, "plot_format", None) is not None:
            state.format = settings.plot_format

        # optional: last file + recent files (depends on your AppState schema)
        if hasattr(state, "last_file_path"):
            setattr(state, "last_file_path", getattr(settings, "last_file_path", None))
        if hasattr(state, "recent_files"):
            setattr(state, "recent_files", list(getattr(settings, "recent_files", []) or []))
    except Exception:
        # Never block startup.
        return


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
    _load_app_state_from_settings(state)

    win = MainWindow(state)
    win.resize(900, 600)
    win.show()
    return app.exec()
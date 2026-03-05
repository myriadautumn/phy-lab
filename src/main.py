from __future__ import annotations

import sys
from pathlib import Path

# Ensure `src/` is on sys.path so `import func...` works when running:
#   python src/main.py
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from func.app import main


if __name__ == "__main__":
    raise SystemExit(main())
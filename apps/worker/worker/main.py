from __future__ import annotations

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[2] / 'api'
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from app.worker.main import main  # noqa: E402

if __name__ == '__main__':
    main()

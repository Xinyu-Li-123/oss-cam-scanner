from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from oss_cam_scanner.app import ScannerWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = ScannerWindow(startup_paths=[Path(arg) for arg in sys.argv[1:]])
    window.resize(1200, 820)
    window.show()
    return app.exec()

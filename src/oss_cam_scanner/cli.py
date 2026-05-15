from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from oss_cam_scanner.app import ScannerWindow
from oss_cam_scanner.i18n import (
    APP_NAME,
    APP_ORGANIZATION,
    install_translations,
    language_preference_from_settings,
)


def main() -> int:
    app = QApplication(sys.argv)
    settings = QSettings(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        APP_ORGANIZATION,
        APP_NAME,
    )
    install_translations(
        app,
        language_preference=language_preference_from_settings(settings),
    )
    window = ScannerWindow(startup_paths=[Path(arg) for arg in sys.argv[1:]])
    window.resize(1200, 820)
    window.show()
    return app.exec()

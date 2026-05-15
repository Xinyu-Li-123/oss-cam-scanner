from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class EmptyPage(QWidget):
    open_images_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        label = QLabel(self.tr("Open one or more images to start scanning."))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        open_button = QPushButton(self.tr("Open Images"))
        open_button.clicked.connect(
            lambda _checked=False: self.open_images_requested.emit()
        )
        layout.addStretch()
        layout.addWidget(label)
        layout.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

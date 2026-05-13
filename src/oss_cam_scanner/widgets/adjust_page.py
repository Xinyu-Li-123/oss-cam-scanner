from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from oss_cam_scanner.models import ImageArray, PointArray
from oss_cam_scanner.widgets.document_canvas import DocumentCanvas


class AdjustPage(QWidget):
    polygon_changed = Signal(object)
    reset_requested = Signal()
    preview_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        self._canvas = DocumentCanvas()
        self._canvas.polygon_changed.connect(self.polygon_changed.emit)
        layout.addWidget(self._canvas, 1)

        controls = QHBoxLayout()
        reset_button = QPushButton("Reset Corners")
        reset_button.clicked.connect(lambda _checked=False: self.reset_requested.emit())
        preview_button = QPushButton("Preview")
        preview_button.clicked.connect(
            lambda _checked=False: self.preview_requested.emit()
        )
        controls.addWidget(reset_button)
        controls.addStretch()
        controls.addWidget(preview_button)
        layout.addLayout(controls)

    def set_image(self, image_rgb: ImageArray) -> None:
        self._canvas.set_image(image_rgb)

    def set_polygon(self, polygon: PointArray) -> None:
        self._canvas.set_polygon(polygon)

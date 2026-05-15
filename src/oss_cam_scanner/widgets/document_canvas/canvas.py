from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from oss_cam_scanner.core.io import image_to_qimage
from oss_cam_scanner.models import ImageArray, PointArray
from .magnifier import _MagnifierWidget


class DocumentCanvas(QWidget):
    polygon_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self.setMouseTracking(True)
        self._image: ImageArray | None = None
        self._qimage: QImage | None = None
        self._polygon: PointArray | None = None
        self._drag_index: int | None = None
        self._image_rect = QRectF()
        self._magnifier = _MagnifierWidget(self)
        self._magnifier.hide()

    def sizeHint(self) -> QSize:
        return QSize(900, 650)

    def set_image(self, image_rgb: ImageArray) -> None:
        if image_rgb is self._image:
            return
        self._image = image_rgb
        self._qimage = image_to_qimage(image_rgb)
        self._drag_index = None
        self._magnifier.set_image(self._qimage)
        self._magnifier.hide()
        self.update()

    def set_polygon(self, polygon: PointArray) -> None:
        new_polygon = np.asarray(polygon, dtype=np.float32).reshape(4, 2).copy()
        if (
            self._drag_index is not None
            and self._polygon is not None
            and np.array_equal(new_polygon, self._polygon)
        ):
            self._polygon = new_polygon
            self.update()
            return
        self._polygon = new_polygon
        self._drag_index = None
        self._magnifier.hide()
        self.update()

    def polygon(self) -> PointArray | None:
        if self._polygon is None:
            return None
        return self._polygon.copy()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1f2328"))
        if self._qimage is None or self._image is None:
            painter.end()
            return

        self._image_rect = self._scaled_image_rect()
        painter.drawImage(self._image_rect, self._qimage)
        if self._polygon is not None:
            self._draw_polygon(painter)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._polygon is None:
            return
        index = self._nearest_handle(event.position())
        if index is not None:
            self._drag_index = index
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._update_magnifier(self._polygon[index])
            self._magnifier.raise_()
            self._magnifier.show()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._polygon is None:
            return
        if self._drag_index is None:
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self._nearest_handle(event.position()) is not None
                else Qt.CursorShape.ArrowCursor
            )
            return
        point = self._widget_to_image(event.position())
        if point is None or self._image is None:
            return
        height, width = self._image.shape[:2]
        point[0] = np.clip(point[0], 0, width - 1)
        point[1] = np.clip(point[1], 0, height - 1)
        self._polygon[self._drag_index] = point
        self._update_magnifier(point)
        self.polygon_changed.emit(self._polygon.copy())
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_index = None
            self._magnifier.hide()
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _draw_polygon(self, painter: QPainter) -> None:
        assert self._polygon is not None
        points = [self._image_to_widget(point) for point in self._polygon]
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#00d084"), 3))
        for start, end in zip(points, points[1:] + points[:1], strict=True):
            painter.drawLine(start, end)
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QColor("#ffcc00"))
        for point in points:
            painter.drawEllipse(point, 8, 8)

    def _scaled_image_rect(self) -> QRectF:
        assert self._image is not None
        image_height, image_width = self._image.shape[:2]
        available = self.rect().adjusted(12, 12, -12, -12)
        scale = min(available.width() / image_width, available.height() / image_height)
        width = image_width * scale
        height = image_height * scale
        left = available.left() + (available.width() - width) / 2
        top = available.top() + (available.height() - height) / 2
        return QRectF(left, top, width, height)

    def _image_to_widget(self, point: np.ndarray) -> QPointF:
        assert self._image is not None
        image_height, image_width = self._image.shape[:2]
        x = self._image_rect.left() + (float(point[0]) / image_width) * self._image_rect.width()
        y = self._image_rect.top() + (float(point[1]) / image_height) * self._image_rect.height()
        return QPointF(x, y)

    def _widget_to_image(self, point: QPointF) -> np.ndarray | None:
        if self._image is None or not self._image_rect.contains(point):
            return None
        image_height, image_width = self._image.shape[:2]
        x = ((point.x() - self._image_rect.left()) / self._image_rect.width()) * image_width
        y = ((point.y() - self._image_rect.top()) / self._image_rect.height()) * image_height
        return np.array([x, y], dtype=np.float32)

    def _nearest_handle(self, point: QPointF) -> int | None:
        if self._polygon is None:
            return None
        for index, handle in enumerate(self._polygon):
            widget_point = self._image_to_widget(handle)
            if (widget_point - point).manhattanLength() <= 18:
                return index
        return None

    def _update_magnifier(self, image_point: np.ndarray) -> None:
        self._magnifier.set_center(QPointF(float(image_point[0]), float(image_point[1])))
        widget_point = self._image_to_widget(image_point)
        self._move_magnifier_near(widget_point)

    def _move_magnifier_near(self, point: QPointF) -> None:
        offset = 24
        width = self._magnifier.width()
        height = self._magnifier.height()
        x = int(point.x()) + offset
        y = int(point.y()) + offset
        if x + width > self.width():
            x = int(point.x()) - width - offset
        if y + height > self.height():
            y = int(point.y()) - height - offset
        x = max(0, min(x, self.width() - width))
        y = max(0, min(y, self.height() - height))
        self._magnifier.move(x, y)

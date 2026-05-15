from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget


class _MagnifierWidget(QWidget):
    _source_size = QSize(80, 80)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(160, 160)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._image: QImage | None = None
        self._center = QPointF()

    def set_image(self, image: QImage | None) -> None:
        self._image = image
        self.update()

    def set_center(self, center: QPointF) -> None:
        self._center = center
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111418"))
        if self._image is not None and not self._image.isNull():
            source_rect = self._source_rect()
            painter.drawImage(QRectF(self.rect()), self._image, source_rect)
            crosshair = self._crosshair_position(source_rect)
            self._draw_crosshair(painter, crosshair)
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 6, 6)
        painter.end()

    def _source_rect(self) -> QRectF:
        assert self._image is not None
        width = min(self._source_size.width(), self._image.width())
        height = min(self._source_size.height(), self._image.height())
        left = self._center.x() - width / 2
        top = self._center.y() - height / 2
        left = max(0.0, min(left, self._image.width() - width))
        top = max(0.0, min(top, self._image.height() - height))
        return QRectF(left, top, width, height)

    def _crosshair_position(self, source_rect: QRectF) -> QPointF:
        x = ((self._center.x() - source_rect.left()) / source_rect.width()) * self.width()
        y = ((self._center.y() - source_rect.top()) / source_rect.height()) * self.height()
        return QPointF(x, y)

    def _draw_crosshair(self, painter: QPainter, center: QPointF) -> None:
        painter.setPen(QPen(QColor("#00d084"), 1))
        painter.drawLine(QPointF(center.x(), 0), QPointF(center.x(), self.height()))
        painter.drawLine(QPointF(0, center.y()), QPointF(self.width(), center.y()))
        painter.setPen(QPen(QColor("#ffcc00"), 2))
        painter.drawEllipse(center, 4, 4)

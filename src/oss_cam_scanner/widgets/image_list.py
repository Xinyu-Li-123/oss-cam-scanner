from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

from oss_cam_scanner.core.io import image_to_pixmap
from oss_cam_scanner.models import ImageItem, item_status_label


class ImageListView(QListWidget):
    current_index_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setIconSize(QSize(72, 96))
        self.currentRowChanged.connect(self.current_index_selected.emit)

    def set_items(self, items: list[ImageItem]) -> None:
        current_row = self.currentRow()
        self.blockSignals(True)
        self.clear()
        for item in items:
            self.addItem(self._format_list_item(item))
        if 0 <= current_row < self.count():
            self.setCurrentRow(current_row)
        self.blockSignals(False)

    def refresh_item(self, index: int, item: ImageItem) -> None:
        if index < 0 or index >= self.count():
            return
        list_item = self.item(index)
        list_item.setText(f"{item.display_name} [{item_status_label(item.status)}]")
        list_item.setToolTip(str(item.path))
        self._set_item_icon(list_item, item)

    def set_current_index(self, index: int) -> None:
        if index == self.currentRow():
            return
        self.blockSignals(True)
        self.setCurrentRow(index)
        self.blockSignals(False)

    def _format_list_item(self, item: ImageItem) -> QListWidgetItem:
        list_item = QListWidgetItem(
            f"{item.display_name} [{item_status_label(item.status)}]"
        )
        list_item.setToolTip(str(item.path))
        self._set_item_icon(list_item, item)
        return list_item

    def _set_item_icon(self, list_item: QListWidgetItem, item: ImageItem) -> None:
        if item.saved_rgb is None:
            list_item.setIcon(QIcon())
            return
        list_item.setIcon(QIcon(image_to_pixmap(item.saved_rgb)))

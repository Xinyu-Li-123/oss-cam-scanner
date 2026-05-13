from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from oss_cam_scanner.core.io import (
    PdfPageSizeOption,
    image_to_pixmap,
    resolve_pdf_page_layout,
)
from oss_cam_scanner.models import ImageItem


class ExportPage(QWidget):
    back_requested = Signal()
    export_images_requested = Signal()
    export_pdfs_requested = Signal()
    export_combined_pdf_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[ImageItem] = []
        self._pdf_page_size_option = PdfPageSizeOption.AUTO

        layout = QVBoxLayout(self)
        header = QLabel("Saved Pages")
        header.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(header)

        self._export_list = QListWidget()
        self._export_list.setIconSize(QSize(96, 128))
        layout.addWidget(self._export_list, 1)

        pdf_options = QGroupBox("PDF Page Size")
        pdf_options_layout = QHBoxLayout(pdf_options)
        self._pdf_page_size_combo = QComboBox()
        for option in PdfPageSizeOption:
            self._pdf_page_size_combo.addItem(option.value, option)
        self._pdf_page_size_combo.currentIndexChanged.connect(
            self._pdf_page_size_changed
        )
        self._pdf_page_size_label = QLabel("Auto selected: no saved pages")
        pdf_options_layout.addWidget(self._pdf_page_size_combo)
        pdf_options_layout.addWidget(self._pdf_page_size_label)
        pdf_options_layout.addStretch()
        layout.addWidget(pdf_options)

        order_actions = QHBoxLayout()
        move_up_button = QPushButton("Move Up")
        move_up_button.clicked.connect(self._move_item_up)
        move_down_button = QPushButton("Move Down")
        move_down_button.clicked.connect(self._move_item_down)
        order_actions.addWidget(move_up_button)
        order_actions.addWidget(move_down_button)
        order_actions.addStretch()
        layout.addLayout(order_actions)

        export_actions = QHBoxLayout()
        back_button = QPushButton("Back To Editing")
        back_button.clicked.connect(lambda _checked=False: self.back_requested.emit())
        export_images_button = QPushButton("Export Separate Images")
        export_images_button.clicked.connect(
            lambda _checked=False: self.export_images_requested.emit()
        )
        export_pdfs_button = QPushButton("Export Separate PDFs")
        export_pdfs_button.clicked.connect(
            lambda _checked=False: self.export_pdfs_requested.emit()
        )
        export_combined_button = QPushButton("Export Combined PDF")
        export_combined_button.clicked.connect(
            lambda _checked=False: self.export_combined_pdf_requested.emit()
        )
        export_actions.addWidget(back_button)
        export_actions.addStretch()
        export_actions.addWidget(export_images_button)
        export_actions.addWidget(export_pdfs_button)
        export_actions.addWidget(export_combined_button)
        layout.addLayout(export_actions)

    @property
    def pdf_page_size_option(self) -> PdfPageSizeOption:
        return self._pdf_page_size_option

    def count(self) -> int:
        return self._export_list.count()

    def set_items(self, items: list[ImageItem]) -> None:
        self._items = items
        existing_order = self.ordered_indices()
        saved_indices = [
            index
            for index, item in enumerate(self._items)
            if item.saved_rgb is not None
        ]
        ordered_indices = [index for index in existing_order if index in saved_indices]
        ordered_indices.extend(
            index for index in saved_indices if index not in ordered_indices
        )

        self._export_list.clear()
        for index in ordered_indices:
            item = self._items[index]
            if item.saved_rgb is None:
                continue
            list_item = QListWidgetItem(f"{index + 1}. {item.display_name}")
            list_item.setData(Qt.ItemDataRole.UserRole, index)
            list_item.setToolTip(str(item.path))
            list_item.setIcon(QIcon(image_to_pixmap(item.saved_rgb)))
            self._export_list.addItem(list_item)
        self._update_pdf_page_size_label()

    def ordered_indices(self) -> list[int]:
        indices: list[int] = []
        for row in range(self._export_list.count()):
            index = self._export_list.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(index, int):
                indices.append(index)
        return indices

    def ordered_items(self, items: list[ImageItem]) -> list[ImageItem]:
        ordered: list[ImageItem] = []
        for index in self.ordered_indices():
            if 0 <= index < len(items):
                item = items[index]
                if item.saved_rgb is not None:
                    ordered.append(item)
        return ordered

    def _move_item_up(self) -> None:
        row = self._export_list.currentRow()
        if row <= 0:
            return
        item = self._export_list.takeItem(row)
        self._export_list.insertItem(row - 1, item)
        self._export_list.setCurrentRow(row - 1)
        self._update_pdf_page_size_label()

    def _move_item_down(self) -> None:
        row = self._export_list.currentRow()
        if row < 0 or row >= self._export_list.count() - 1:
            return
        item = self._export_list.takeItem(row)
        self._export_list.insertItem(row + 1, item)
        self._export_list.setCurrentRow(row + 1)
        self._update_pdf_page_size_label()

    def _pdf_page_size_changed(self, index: int) -> None:
        option = self._pdf_page_size_combo.itemData(index)
        self._pdf_page_size_option = (
            option
            if isinstance(option, PdfPageSizeOption)
            else PdfPageSizeOption(str(option))
        )
        self._update_pdf_page_size_label()

    def _update_pdf_page_size_label(self) -> None:
        items = self.ordered_items(self._items)
        if not items:
            if self._pdf_page_size_option == PdfPageSizeOption.AUTO:
                self._pdf_page_size_label.setText("Auto selected: no saved pages")
            else:
                self._pdf_page_size_label.setText("PDF page size: no saved pages")
            return

        first_saved = items[0].saved_rgb
        if first_saved is None:
            return
        layout = resolve_pdf_page_layout(self._pdf_page_size_option, first_saved)
        if self._pdf_page_size_option == PdfPageSizeOption.AUTO:
            self._pdf_page_size_label.setText(f"Auto selected: {layout.name}")
        else:
            self._pdf_page_size_label.setText(f"PDF page size: {layout.name}")

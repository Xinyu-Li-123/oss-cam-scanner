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
    pdf_page_size_option_label,
)
from oss_cam_scanner.models import ImageItem


class ExportPage(QWidget):
    back_requested = Signal()
    move_up_requested = Signal(int)
    move_down_requested = Signal(int)
    pdf_page_size_changed = Signal(object)
    export_images_requested = Signal()
    export_pdfs_requested = Signal()
    export_combined_pdf_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        header = QLabel(self.tr("Saved Pages"))
        header.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(header)

        self._export_list = QListWidget()
        self._export_list.setIconSize(QSize(96, 128))
        layout.addWidget(self._export_list, 1)

        pdf_options = QGroupBox(self.tr("PDF Page Size"))
        pdf_options_layout = QHBoxLayout(pdf_options)
        self._pdf_page_size_combo = QComboBox()
        for option in PdfPageSizeOption:
            self._pdf_page_size_combo.addItem(
                pdf_page_size_option_label(option),
                option,
            )
        self._pdf_page_size_combo.currentIndexChanged.connect(self._emit_pdf_page_size)
        self._pdf_page_size_label = QLabel(self.tr("Auto selected: no saved pages"))
        pdf_options_layout.addWidget(self._pdf_page_size_combo)
        pdf_options_layout.addWidget(self._pdf_page_size_label)
        pdf_options_layout.addStretch()
        layout.addWidget(pdf_options)

        order_actions = QHBoxLayout()
        move_up_button = QPushButton(self.tr("Move Up"))
        move_up_button.clicked.connect(
            lambda _checked=False: self.move_up_requested.emit(self.current_row())
        )
        move_down_button = QPushButton(self.tr("Move Down"))
        move_down_button.clicked.connect(
            lambda _checked=False: self.move_down_requested.emit(self.current_row())
        )
        order_actions.addWidget(move_up_button)
        order_actions.addWidget(move_down_button)
        order_actions.addStretch()
        layout.addLayout(order_actions)

        export_actions = QHBoxLayout()
        back_button = QPushButton(self.tr("Back To Editing"))
        back_button.clicked.connect(lambda _checked=False: self.back_requested.emit())
        export_images_button = QPushButton(self.tr("Export Separate Images"))
        export_images_button.clicked.connect(
            lambda _checked=False: self.export_images_requested.emit()
        )
        export_pdfs_button = QPushButton(self.tr("Export Separate PDFs"))
        export_pdfs_button.clicked.connect(
            lambda _checked=False: self.export_pdfs_requested.emit()
        )
        export_combined_button = QPushButton(self.tr("Export Combined PDF"))
        export_combined_button.clicked.connect(
            lambda _checked=False: self.export_combined_pdf_requested.emit()
        )
        export_actions.addWidget(back_button)
        export_actions.addStretch()
        export_actions.addWidget(export_images_button)
        export_actions.addWidget(export_pdfs_button)
        export_actions.addWidget(export_combined_button)
        layout.addLayout(export_actions)

    def count(self) -> int:
        return self._export_list.count()

    def current_row(self) -> int:
        return self._export_list.currentRow()

    def set_saved_items(
        self,
        items: list[tuple[int, ImageItem]],
        ordered_indices: list[int],
    ) -> None:
        items_by_index = dict(items)
        current_row = self._export_list.currentRow()
        self._export_list.clear()
        for index in ordered_indices:
            item = items_by_index.get(index)
            if item is None:
                continue
            if item.saved_rgb is None:
                continue
            list_item = QListWidgetItem(f"{index + 1}. {item.display_name}")
            list_item.setData(Qt.ItemDataRole.UserRole, index)
            list_item.setToolTip(str(item.path))
            list_item.setIcon(QIcon(image_to_pixmap(item.saved_rgb)))
            self._export_list.addItem(list_item)
        if 0 <= current_row < self._export_list.count():
            self._export_list.setCurrentRow(current_row)

    def set_pdf_page_size_option(self, option: PdfPageSizeOption) -> None:
        combo_index = self._pdf_page_size_combo.findData(option)
        if combo_index < 0:
            return
        self._pdf_page_size_combo.blockSignals(True)
        self._pdf_page_size_combo.setCurrentIndex(combo_index)
        self._pdf_page_size_combo.blockSignals(False)

    def set_pdf_page_size_label(self, text: str) -> None:
        self._pdf_page_size_label.setText(text)

    def _emit_pdf_page_size(self, index: int) -> None:
        option = self._pdf_page_size_combo.itemData(index)
        page_size_option = (
            option
            if isinstance(option, PdfPageSizeOption)
            else PdfPageSizeOption(str(option))
        )
        self.pdf_page_size_changed.emit(page_size_option)

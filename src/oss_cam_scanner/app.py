from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from oss_cam_scanner.core.detection import detect_document
from oss_cam_scanner.core.filters import ScanFilter, apply_filters
from oss_cam_scanner.core.geometry import order_points, warp_perspective
from oss_cam_scanner.core.io import (
    image_to_pixmap,
    read_image_rgb,
    write_combined_pdf,
    write_image,
    write_pdf,
)
from oss_cam_scanner.models import ImageItem, ItemStatus, PointArray
from oss_cam_scanner.widgets.document_canvas import DocumentCanvas


class ScannerWindow(QMainWindow):
    def __init__(self, startup_paths: list[Path] | None = None) -> None:
        super().__init__()
        self.setWindowTitle("OSS Cam Scanner")
        self._items: list[ImageItem] = []
        self._current_index = -1
        self._selected_filters: set[ScanFilter] = set()
        self._filter_checkboxes: dict[ScanFilter, QCheckBox] = {}
        self._preview_image: np.ndarray | None = None

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._select_index)

        self._stack = QStackedWidget()
        self._empty_page = self._build_empty_page()
        self._adjust_page = self._build_adjust_page()
        self._preview_page = self._build_preview_page()
        self._export_page = self._build_export_page()
        self._stack.addWidget(self._empty_page)
        self._stack.addWidget(self._adjust_page)
        self._stack.addWidget(self._preview_page)
        self._stack.addWidget(self._export_page)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._stack, 4)
        self.setCentralWidget(root)

        self._build_toolbar()

        if startup_paths:
            self.add_images(startup_paths)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open Images", self)
        open_action.triggered.connect(self._choose_images)
        toolbar.addAction(open_action)

        reset_action = QAction("Reset Corners", self)
        reset_action.triggered.connect(self._reset_corners)
        toolbar.addAction(reset_action)

        save_action = QAction("Save For Export", self)
        save_action.triggered.connect(self._save_current)
        toolbar.addAction(save_action)

        export_action = QAction("Export", self)
        export_action.triggered.connect(self._show_export_page)
        toolbar.addAction(export_action)

    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel("Open one or more images to start scanning.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        open_button = QPushButton("Open Images")
        open_button.clicked.connect(self._choose_images)
        layout.addStretch()
        layout.addWidget(label)
        layout.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        return page

    def _build_adjust_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._canvas = DocumentCanvas()
        self._canvas.polygon_changed.connect(self._set_current_polygon)
        layout.addWidget(self._canvas, 1)

        controls = QHBoxLayout()
        reset_button = QPushButton("Reset Corners")
        reset_button.clicked.connect(self._reset_corners)
        preview_button = QPushButton("Preview")
        preview_button.clicked.connect(self._show_preview)
        controls.addWidget(reset_button)
        controls.addStretch()
        controls.addWidget(preview_button)
        layout.addLayout(controls)
        return page

    def _build_preview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(480, 360)
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_label.setStyleSheet("background: #1f2328;")
        layout.addWidget(self._preview_label, 1)

        filter_group = QGroupBox("Filters")
        filter_group.setStyleSheet("QGroupBox { font-weight: 600; }")
        filter_panel = QHBoxLayout(filter_group)
        for scan_filter, label in (
            (ScanFilter.NO_SHADOW, "No shadow"),
            (ScanFilter.LIGHTEN, "Lighten"),
            (ScanFilter.ENHANCE, "Enhance"),
        ):
            checkbox = QCheckBox(label)
            checkbox.setStyleSheet("QCheckBox { font-size: 15px; padding: 6px 10px; }")
            checkbox.stateChanged.connect(self._filters_changed)
            self._filter_checkboxes[scan_filter] = checkbox
            filter_panel.addWidget(checkbox)
        filter_panel.addStretch()

        actions = QHBoxLayout()
        back_button = QPushButton("Back")
        back_button.clicked.connect(self._show_adjustment)
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._save_current)
        self._save_next_button = QPushButton("Save And Next")
        self._save_next_button.clicked.connect(self._save_and_next)
        self._export_button = QPushButton("Saven And Export")
        self._export_button.clicked.connect(self._save_and_show_export)

        actions.addStretch()
        actions.addWidget(back_button)
        actions.addWidget(self._save_button)
        actions.addWidget(self._save_next_button)
        actions.addWidget(self._export_button)
        layout.addWidget(filter_group)
        layout.addLayout(actions)
        return page

    def _build_export_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QLabel("Saved Pages")
        header.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(header)

        self._export_list = QListWidget()
        self._export_list.setIconSize(QSize(96, 128))
        layout.addWidget(self._export_list, 1)

        order_actions = QHBoxLayout()
        move_up_button = QPushButton("Move Up")
        move_up_button.clicked.connect(self._move_export_item_up)
        move_down_button = QPushButton("Move Down")
        move_down_button.clicked.connect(self._move_export_item_down)
        order_actions.addWidget(move_up_button)
        order_actions.addWidget(move_down_button)
        order_actions.addStretch()
        layout.addLayout(order_actions)

        export_actions = QHBoxLayout()
        back_button = QPushButton("Back To Editing")
        back_button.clicked.connect(self._show_current_or_first_image)
        export_images_button = QPushButton("Export Separate Images")
        export_images_button.clicked.connect(self._export_images)
        export_pdfs_button = QPushButton("Export Separate PDFs")
        export_pdfs_button.clicked.connect(self._export_pdfs)
        export_combined_button = QPushButton("Export Combined PDF")
        export_combined_button.clicked.connect(self._export_combined_pdf)
        export_actions.addWidget(back_button)
        export_actions.addStretch()
        export_actions.addWidget(export_images_button)
        export_actions.addWidget(export_pdfs_button)
        export_actions.addWidget(export_combined_button)
        layout.addLayout(export_actions)
        return page

    def add_images(self, paths: list[Path]) -> None:
        for path in paths:
            try:
                image = read_image_rgb(path)
                detection = detect_document(image)
                item = ImageItem(
                    path=path,
                    original_rgb=image,
                    detected_corners=detection.corners.copy(),
                    corners=detection.corners.copy(),
                )
                self._items.append(item)
                self._list.addItem(self._format_list_item(item))
            except Exception as exc:
                QMessageBox.warning(self, "Open Image Failed", f"{path}\n\n{exc}")

        if self._items and self._current_index < 0:
            self._list.setCurrentRow(0)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        if self._stack.currentWidget() == self._preview_page:
            self._update_preview_label()

    def _choose_images(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;All Files (*)",
        )
        self.add_images([Path(filename) for filename in filenames])

    def _select_index(self, index: int) -> None:
        if index < 0 or index >= len(self._items):
            self._current_index = -1
            self._stack.setCurrentWidget(self._empty_page)
            return
        self._current_index = index
        item = self._items[index]
        self._canvas.set_image(item.original_rgb)
        self._canvas.set_polygon(item.corners)
        self._sync_filter_checkboxes()
        self._preview_image = None
        self._stack.setCurrentWidget(self._adjust_page)

    def _current_item(self) -> ImageItem | None:
        if self._current_index < 0 or self._current_index >= len(self._items):
            return None
        return self._items[self._current_index]

    def _set_current_polygon(self, polygon: PointArray) -> None:
        item = self._current_item()
        if item is None:
            return
        item.corners = polygon.copy()
        item.warped_rgb = None

    def _reset_corners(self) -> None:
        item = self._current_item()
        if item is None:
            return
        item.corners = item.detected_corners.copy()
        item.warped_rgb = None
        self._canvas.set_polygon(item.corners)

    def _show_adjustment(self) -> None:
        item = self._current_item()
        if item is None:
            return
        self._canvas.set_image(item.original_rgb)
        self._canvas.set_polygon(item.corners)
        self._stack.setCurrentWidget(self._adjust_page)

    def _show_preview(self) -> None:
        item = self._current_item()
        if item is None:
            return
        try:
            item.corners = order_points(item.corners)
            item.warped_rgb = warp_perspective(item.original_rgb, item.corners)
        except Exception as exc:
            item.status = ItemStatus.FAILED
            item.error = str(exc)
            self._refresh_list_item(self._current_index)
            QMessageBox.warning(
                self, "Preview Failed", f"Could not warp document region.\n\n{exc}"
            )
            return
        item.status = ItemStatus.PREVIEWED
        self._refresh_list_item(self._current_index)
        self._stack.setCurrentWidget(self._preview_page)
        self._update_preview_actions()
        self._apply_current_filter()

    def _filters_changed(self, *_args: object) -> None:
        self._selected_filters = {
            scan_filter
            for scan_filter, checkbox in self._filter_checkboxes.items()
            if checkbox.isChecked()
        }
        if self._stack.currentWidget() == self._preview_page:
            self._apply_current_filter()

    def _apply_current_filter(self) -> None:
        item = self._current_item()
        if item is None:
            return
        try:
            if item.warped_rgb is None:
                item.warped_rgb = warp_perspective(item.original_rgb, item.corners)
            self._preview_image = apply_filters(item.warped_rgb, self._selected_filters)
        except Exception as exc:
            item.status = ItemStatus.FAILED
            item.error = str(exc)
            self._refresh_list_item(self._current_index)
            QMessageBox.warning(self, "Filter Failed", str(exc))
            return
        self._update_preview_label()

    def _update_preview_label(self) -> None:
        if self._preview_image is None:
            self._preview_label.clear()
            return
        pixmap = image_to_pixmap(self._preview_image)
        scaled = pixmap.scaled(
            self._preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    def _save_current(self) -> bool:
        if self._preview_image is None:
            self._show_preview()
        if self._preview_image is None:
            return False
        item = self._current_item()
        if item is None:
            return False
        item.saved_rgb = self._preview_image.copy()
        item.status = ItemStatus.SAVED
        self._refresh_list_item(self._current_index)
        return True

    def _save_and_next(self) -> None:
        if self._save_current():
            self._select_next_pending()

    def _save_and_show_export(self) -> None:
        if self._save_current():
            self._show_export_page()

    def _select_next_pending(self) -> None:
        for index in range(self._current_index + 1, len(self._items)):
            if self._items[index].status != ItemStatus.SAVED:
                self._list.setCurrentRow(index)
                return
        if self._current_index + 1 < len(self._items):
            self._list.setCurrentRow(self._current_index + 1)

    def _show_current_or_first_image(self) -> None:
        if self._current_index >= 0:
            self._show_adjustment()
        elif self._items:
            self._list.setCurrentRow(0)
        else:
            self._stack.setCurrentWidget(self._empty_page)

    def _show_export_page(self) -> None:
        self._refresh_export_list()
        if self._export_list.count() == 0:
            QMessageBox.information(
                self, "Nothing To Export", "Save at least one page before exporting."
            )
            return
        self._stack.setCurrentWidget(self._export_page)

    def _refresh_export_list(self) -> None:
        existing_order = [
            self._export_list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self._export_list.count())
        ]
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

    def _saved_export_items_in_order(self) -> list[ImageItem]:
        items: list[ImageItem] = []
        for row in range(self._export_list.count()):
            index = self._export_list.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(index, int) and 0 <= index < len(self._items):
                item = self._items[index]
                if item.saved_rgb is not None:
                    items.append(item)
        return items

    def _move_export_item_up(self) -> None:
        row = self._export_list.currentRow()
        if row <= 0:
            return
        item = self._export_list.takeItem(row)
        self._export_list.insertItem(row - 1, item)
        self._export_list.setCurrentRow(row - 1)

    def _move_export_item_down(self) -> None:
        row = self._export_list.currentRow()
        if row < 0 or row >= self._export_list.count() - 1:
            return
        item = self._export_list.takeItem(row)
        self._export_list.insertItem(row + 1, item)
        self._export_list.setCurrentRow(row + 1)

    def _export_images(self) -> None:
        items = self._saved_export_items_in_order()
        if not items:
            QMessageBox.information(
                self, "Nothing To Export", "Save at least one page before exporting."
            )
            return
        directory = QFileDialog.getExistingDirectory(self, "Export Images")
        if not directory:
            return
        try:
            for item in items:
                assert item.saved_rgb is not None
                write_image(
                    Path(directory) / f"{item.path.stem}-scan.png", item.saved_rgb
                )
            QMessageBox.information(
                self, "Export Complete", f"Exported {len(items)} image file(s)."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))

    def _export_pdfs(self) -> None:
        items = self._saved_export_items_in_order()
        if not items:
            QMessageBox.information(
                self, "Nothing To Export", "Save at least one page before exporting."
            )
            return
        directory = QFileDialog.getExistingDirectory(self, "Export PDFs")
        if not directory:
            return
        try:
            for item in items:
                assert item.saved_rgb is not None
                write_pdf(
                    Path(directory) / f"{item.path.stem}-scan.pdf", item.saved_rgb
                )
            QMessageBox.information(
                self, "Export Complete", f"Exported {len(items)} PDF file(s)."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))

    def _export_combined_pdf(self) -> None:
        items = self._saved_export_items_in_order()
        if not items:
            QMessageBox.information(
                self, "Nothing To Export", "Save at least one page before exporting."
            )
            return
        first_path = items[0].path.with_name(f"{items[0].path.stem}-combined-scan.pdf")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Combined PDF",
            str(first_path),
            "PDF File (*.pdf)",
        )
        if not filename:
            return
        try:
            images: list[np.ndarray] = []
            for item in items:
                if item.saved_rgb is not None:
                    images.append(item.saved_rgb)
            write_combined_pdf(Path(filename), images)
            QMessageBox.information(
                self, "Export Complete", f"Exported {len(images)} page PDF."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))

    def _format_list_item(self, item: ImageItem) -> QListWidgetItem:
        widget_item = QListWidgetItem(f"{item.display_name} [{item.status}]")
        widget_item.setToolTip(str(item.path))
        return widget_item

    def _refresh_list_item(self, index: int) -> None:
        if index < 0 or index >= len(self._items):
            return
        list_item = self._list.item(index)
        item = self._items[index]
        list_item.setText(f"{item.display_name} [{item.status}]")
        list_item.setToolTip(str(item.path))

    def _sync_filter_checkboxes(self) -> None:
        for scan_filter, checkbox in self._filter_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(scan_filter in self._selected_filters)
            checkbox.blockSignals(False)

    def _update_preview_actions(self) -> None:
        is_last = self._current_index == len(self._items) - 1
        self._save_button.setVisible(not is_last)
        self._save_next_button.setVisible(not is_last)
        self._export_button.setVisible(is_last)

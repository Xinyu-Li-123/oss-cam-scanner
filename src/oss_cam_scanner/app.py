from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
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
from oss_cam_scanner.core.io import image_to_pixmap, read_image_rgb, write_image
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
        self._stack.addWidget(self._empty_page)
        self._stack.addWidget(self._adjust_page)
        self._stack.addWidget(self._preview_page)

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

        save_action = QAction("Save", self)
        save_action.triggered.connect(self._save_current)
        toolbar.addAction(save_action)

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
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save_current)
        save_next_button = QPushButton("Save And Next")
        save_next_button.clicked.connect(self._save_and_next)

        actions.addStretch()
        actions.addWidget(back_button)
        actions.addWidget(save_button)
        actions.addWidget(save_next_button)
        layout.addWidget(filter_group)
        layout.addLayout(actions)
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
            QMessageBox.warning(self, "Preview Failed", f"Could not warp document region.\n\n{exc}")
            return
        item.status = ItemStatus.PREVIEWED
        self._refresh_list_item(self._current_index)
        self._stack.setCurrentWidget(self._preview_page)
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
        suggested = item.path.with_name(f"{item.path.stem}-scan.png")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scan",
            str(suggested),
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)",
        )
        if not filename:
            return False
        try:
            write_image(Path(filename), self._preview_image)
            item.status = ItemStatus.SAVED
            self._refresh_list_item(self._current_index)
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", str(exc))
            return False

    def _save_and_next(self) -> None:
        if self._save_current():
            self._select_next_pending()

    def _select_next_pending(self) -> None:
        for index in range(self._current_index + 1, len(self._items)):
            if self._items[index].status != ItemStatus.SAVED:
                self._list.setCurrentRow(index)
                return
        if self._current_index + 1 < len(self._items):
            self._list.setCurrentRow(self._current_index + 1)

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

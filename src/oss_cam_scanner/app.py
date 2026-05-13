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
from oss_cam_scanner.core.io import (
    PdfPageLayout,
    image_to_pixmap,
    read_image_rgb,
    resolve_pdf_page_layout,
    write_combined_pdf,
    write_image,
    write_pdf,
)
from oss_cam_scanner.models import ImageArray, ImageItem, ItemStatus, PointArray
from oss_cam_scanner.widgets.document_canvas import DocumentCanvas
from oss_cam_scanner.widgets.export_page import ExportPage


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
        rotate_left_button = QPushButton("Rotate Left")
        rotate_left_button.clicked.connect(self._rotate_current_left)
        rotate_right_button = QPushButton("Rotate Right")
        rotate_right_button.clicked.connect(self._rotate_current_right)
        filter_panel.addWidget(rotate_left_button)
        filter_panel.addWidget(rotate_right_button)
        filter_panel.addStretch()

        actions = QHBoxLayout()
        back_button = QPushButton("Back")
        back_button.clicked.connect(self._show_adjustment)
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._save_current)
        self._save_next_button = QPushButton("Save And Next")
        self._save_next_button.clicked.connect(self._save_and_next)
        self._export_button = QPushButton("Save And Export")
        self._export_button.clicked.connect(self._save_and_show_export)

        actions.addStretch()
        actions.addWidget(back_button)
        actions.addWidget(self._save_button)
        actions.addWidget(self._save_next_button)
        actions.addWidget(self._export_button)
        layout.addWidget(filter_group)
        layout.addLayout(actions)
        return page

    def _build_export_page(self) -> ExportPage:
        page = ExportPage()
        page.back_requested.connect(self._show_current_or_first_image)
        page.export_images_requested.connect(self._export_images)
        page.export_pdfs_requested.connect(self._export_pdfs)
        page.export_combined_pdf_requested.connect(self._export_combined_pdf)
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
            filtered_rgb = apply_filters(item.warped_rgb, self._selected_filters)
            self._preview_image = self._rotate_image(filtered_rgb, item.rotation_turns)
        except Exception as exc:
            item.status = ItemStatus.FAILED
            item.error = str(exc)
            self._refresh_list_item(self._current_index)
            QMessageBox.warning(self, "Filter Failed", str(exc))
            return
        self._update_preview_label()

    def _rotate_current_left(self) -> None:
        self._rotate_current(-1)

    def _rotate_current_right(self) -> None:
        self._rotate_current(1)

    def _rotate_current(self, turns_delta: int) -> None:
        item = self._current_item()
        if item is None:
            return
        item.rotation_turns = (item.rotation_turns + turns_delta) % 4
        self._preview_image = None
        self._apply_current_filter()

    def _rotate_image(self, image_rgb: ImageArray, clockwise_turns: int) -> ImageArray:
        turns = clockwise_turns % 4
        if turns == 0:
            return image_rgb
        return np.ascontiguousarray(np.rot90(image_rgb, k=-turns))

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
        self._export_page.set_items(self._items)
        if self._export_page.count() == 0:
            QMessageBox.information(
                self, "Nothing To Export", "Save at least one page before exporting."
            )
            return
        self._stack.setCurrentWidget(self._export_page)

    def _export_images(self) -> None:
        items = self._export_page.ordered_items(self._items)
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
        items = self._export_page.ordered_items(self._items)
        if not items:
            QMessageBox.information(
                self, "Nothing To Export", "Save at least one page before exporting."
            )
            return
        directory = QFileDialog.getExistingDirectory(self, "Export PDFs")
        if not directory:
            return
        try:
            layout = self._resolve_current_pdf_layout(items)
            for item in items:
                assert item.saved_rgb is not None
                write_pdf(
                    Path(directory) / f"{item.path.stem}-scan.pdf",
                    item.saved_rgb,
                    layout,
                )
            QMessageBox.information(
                self, "Export Complete", f"Exported {len(items)} PDF file(s)."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))

    def _export_combined_pdf(self) -> None:
        items = self._export_page.ordered_items(self._items)
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
            images: list[ImageArray] = []
            for item in items:
                if item.saved_rgb is not None:
                    images.append(item.saved_rgb)
            layout = self._resolve_current_pdf_layout(items)
            write_combined_pdf(Path(filename), images, layout)
            QMessageBox.information(
                self, "Export Complete", f"Exported {len(images)} page PDF."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))

    def _resolve_current_pdf_layout(self, items: list[ImageItem]) -> PdfPageLayout:
        first_saved = next(
            (item.saved_rgb for item in items if item.saved_rgb is not None),
            None,
        )
        if first_saved is None:
            raise ValueError("Cannot export a PDF without saved pages.")
        return resolve_pdf_page_layout(
            self._export_page.pdf_page_size_option,
            first_saved,
        )

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

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from oss_cam_scanner.core.filters import ScanFilter
from oss_cam_scanner.core.io import image_to_pixmap
from oss_cam_scanner.models import ImageArray


class PreviewPage(QWidget):
    adjust_region_requested = Signal()
    filters_changed = Signal(object)
    rotate_requested = Signal(int)
    save_requested = Signal()
    save_next_requested = Signal()
    save_export_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_image: ImageArray | None = None
        self._filter_checkboxes: dict[ScanFilter, QCheckBox] = {}

        layout = QVBoxLayout(self)
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
            checkbox.stateChanged.connect(self._emit_filters_changed)
            self._filter_checkboxes[scan_filter] = checkbox
            filter_panel.addWidget(checkbox)
        rotate_left_button = QPushButton("Rotate Left")
        rotate_left_button.clicked.connect(
            lambda _checked=False: self.rotate_requested.emit(-1)
        )
        rotate_right_button = QPushButton("Rotate Right")
        rotate_right_button.clicked.connect(
            lambda _checked=False: self.rotate_requested.emit(1)
        )
        filter_panel.addWidget(rotate_left_button)
        filter_panel.addWidget(rotate_right_button)
        filter_panel.addStretch()

        actions = QHBoxLayout()
        adjust_region_button = QPushButton("Adjust Region")
        adjust_region_button.clicked.connect(
            lambda _checked=False: self.adjust_region_requested.emit()
        )
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(
            lambda _checked=False: self.save_requested.emit()
        )
        self._save_next_button = QPushButton("Save And Next")
        self._save_next_button.clicked.connect(
            lambda _checked=False: self.save_next_requested.emit()
        )
        self._export_button = QPushButton("Save And Export")
        self._export_button.clicked.connect(
            lambda _checked=False: self.save_export_requested.emit()
        )

        actions.addStretch()
        actions.addWidget(adjust_region_button)
        actions.addWidget(self._save_button)
        actions.addWidget(self._save_next_button)
        actions.addWidget(self._export_button)
        layout.addWidget(filter_group)
        layout.addLayout(actions)

    def selected_filters(self) -> set[ScanFilter]:
        return {
            scan_filter
            for scan_filter, checkbox in self._filter_checkboxes.items()
            if checkbox.isChecked()
        }

    def set_selected_filters(self, filters: set[ScanFilter]) -> None:
        for scan_filter, checkbox in self._filter_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(scan_filter in filters)
            checkbox.blockSignals(False)

    def set_preview_image(self, image_rgb: ImageArray | None) -> None:
        self._preview_image = image_rgb
        self.refresh_preview()

    def refresh_preview(self) -> None:
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

    def set_save_actions_for_last_item(self, is_last: bool) -> None:
        self._save_next_button.setVisible(not is_last)
        self._export_button.setVisible(is_last)

    def _emit_filters_changed(self, *_args: object) -> None:
        self.filters_changed.emit(self.selected_filters())

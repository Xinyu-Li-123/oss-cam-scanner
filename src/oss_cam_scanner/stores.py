from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal

from oss_cam_scanner.core.filters import ScanFilter
from oss_cam_scanner.core.io import PdfPageSizeOption
from oss_cam_scanner.models import ImageArray, ImageItem, ItemStatus, PointArray


class DocumentStore(QObject):
    items_changed = Signal()
    current_index_changed = Signal(int)
    current_item_changed = Signal(object)
    item_changed = Signal(int)
    item_status_changed = Signal(int)
    saved_items_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[ImageItem] = []
        self._current_index = -1

    def items(self) -> list[ImageItem]:
        return list(self._items)

    def item(self, index: int) -> ImageItem | None:
        if index < 0 or index >= len(self._items):
            return None
        return self._items[index]

    def current_index(self) -> int:
        return self._current_index

    def current_item(self) -> ImageItem | None:
        return self.item(self._current_index)

    def set_current_index(self, index: int) -> None:
        if index < 0 or index >= len(self._items):
            index = -1
        if index == self._current_index:
            return
        self._current_index = index
        self.current_index_changed.emit(index)
        self.current_item_changed.emit(self.current_item())

    def add_item(self, item: ImageItem) -> int:
        self._items.append(item)
        index = len(self._items) - 1
        self.items_changed.emit()
        return index

    def add_items(self, items: list[ImageItem]) -> list[int]:
        start = len(self._items)
        self._items.extend(items)
        indices = list(range(start, len(self._items)))
        if indices:
            self.items_changed.emit()
        return indices

    def set_item_corners(self, index: int, corners: PointArray) -> None:
        item = self.item(index)
        if item is None:
            return
        item.corners = corners.copy()
        item.warped_rgb = None
        item.error = None
        self._emit_item_changed(index)

    def reset_item_corners(self, index: int) -> None:
        item = self.item(index)
        if item is None:
            return
        item.corners = item.detected_corners.copy()
        item.warped_rgb = None
        item.error = None
        self._emit_item_changed(index)

    def set_item_warped_image(self, index: int, image: ImageArray | None) -> None:
        item = self.item(index)
        if item is None:
            return
        item.warped_rgb = image
        self._emit_item_changed(index)

    def set_item_saved_image(self, index: int, image: ImageArray | None) -> None:
        item = self.item(index)
        if item is None:
            return
        had_saved = item.saved_rgb is not None
        item.saved_rgb = image
        self._emit_item_changed(index)
        if had_saved != (image is not None):
            self.saved_items_changed.emit()

    def set_item_filters(self, index: int, filters: set[ScanFilter]) -> None:
        item = self.item(index)
        if item is None:
            return
        item.selected_filters = set(filters)
        self._emit_item_changed(index)

    def set_all_item_filters(self, filters: set[ScanFilter]) -> None:
        selected_filters = set(filters)
        for index, item in enumerate(self._items):
            item.selected_filters = set(selected_filters)
            self._emit_item_changed(index)

    def set_item_rotation(self, index: int, turns: int) -> None:
        item = self.item(index)
        if item is None:
            return
        item.rotation_turns = turns % 4
        self._emit_item_changed(index)

    def set_item_status(
        self,
        index: int,
        status: ItemStatus,
        error: str | None = None,
    ) -> None:
        item = self.item(index)
        if item is None:
            return
        item.status = status
        item.error = error
        self.item_status_changed.emit(index)
        self._emit_item_changed(index)
        if status == ItemStatus.SAVED:
            self.saved_items_changed.emit()

    def saved_items(self) -> list[tuple[int, ImageItem]]:
        return [
            (index, item)
            for index, item in enumerate(self._items)
            if item.saved_rgb is not None
        ]

    def next_not_saved_index(self, after: int) -> int | None:
        for index in range(after + 1, len(self._items)):
            if self._items[index].status != ItemStatus.SAVED:
                return index
        if after + 1 < len(self._items):
            return after + 1
        return None

    def _emit_item_changed(self, index: int) -> None:
        self.item_changed.emit(index)
        if index == self._current_index:
            self.current_item_changed.emit(self.current_item())


class PreviewState(QObject):
    preview_image_changed = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._preview_image: ImageArray | None = None
        self._first_saved_filters_applied = False

    def first_saved_filters_applied(self) -> bool:
        return self._first_saved_filters_applied

    def set_first_saved_filters_applied(self, applied: bool) -> None:
        self._first_saved_filters_applied = applied

    def preview_image(self) -> ImageArray | None:
        return self._preview_image

    def set_preview_image(self, image: ImageArray | None) -> None:
        self._preview_image = image
        self.preview_image_changed.emit(image)

    def clear_preview_image(self) -> None:
        self.set_preview_image(None)


class PreferenceState(QObject):
    apply_first_saved_filters_to_all_pages_changed = Signal(bool)

    def __init__(self, settings: QSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._apply_first_saved_filters_to_all_pages = settings.value(
            "preview/apply_first_saved_filters_to_all_pages",
            True,
            type=bool,
        )

    def apply_first_saved_filters_to_all_pages(self) -> bool:
        return self._apply_first_saved_filters_to_all_pages

    def set_apply_first_saved_filters_to_all_pages(self, enabled: bool) -> None:
        if enabled == self._apply_first_saved_filters_to_all_pages:
            return
        self._apply_first_saved_filters_to_all_pages = enabled
        self._settings.setValue(
            "preview/apply_first_saved_filters_to_all_pages",
            enabled,
        )
        self.apply_first_saved_filters_to_all_pages_changed.emit(enabled)


class ExportState(QObject):
    order_changed = Signal()
    pdf_page_size_option_changed = Signal(object)
    export_state_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ordered_indices: list[int] = []
        self._pdf_page_size_option = PdfPageSizeOption.AUTO

    def ordered_indices(self) -> list[int]:
        return list(self._ordered_indices)

    def set_ordered_indices(self, indices: list[int]) -> None:
        self._ordered_indices = list(indices)
        self.order_changed.emit()
        self.export_state_changed.emit()

    def sync_with_saved_indices(self, saved_indices: list[int]) -> None:
        ordered = [index for index in self._ordered_indices if index in saved_indices]
        ordered.extend(index for index in saved_indices if index not in ordered)
        if ordered == self._ordered_indices:
            return
        self._ordered_indices = ordered
        self.order_changed.emit()
        self.export_state_changed.emit()

    def move_index_up(self, row: int) -> None:
        if row <= 0 or row >= len(self._ordered_indices):
            return
        self._ordered_indices[row - 1], self._ordered_indices[row] = (
            self._ordered_indices[row],
            self._ordered_indices[row - 1],
        )
        self.order_changed.emit()
        self.export_state_changed.emit()

    def move_index_down(self, row: int) -> None:
        if row < 0 or row >= len(self._ordered_indices) - 1:
            return
        self._ordered_indices[row + 1], self._ordered_indices[row] = (
            self._ordered_indices[row],
            self._ordered_indices[row + 1],
        )
        self.order_changed.emit()
        self.export_state_changed.emit()

    def pdf_page_size_option(self) -> PdfPageSizeOption:
        return self._pdf_page_size_option

    def set_pdf_page_size_option(self, option: PdfPageSizeOption) -> None:
        if option == self._pdf_page_size_option:
            return
        self._pdf_page_size_option = option
        self.pdf_page_size_option_changed.emit(option)
        self.export_state_changed.emit()

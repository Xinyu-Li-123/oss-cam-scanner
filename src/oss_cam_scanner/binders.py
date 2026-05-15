from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from oss_cam_scanner.controllers import (
    EditController,
    ExportController,
    PreviewController,
)
from oss_cam_scanner.core.io import PdfPageSizeOption
from oss_cam_scanner.models import ImageItem
from oss_cam_scanner.stores import DocumentStore, ExportState, PreviewState
from oss_cam_scanner.widgets.adjust_page import AdjustPage
from oss_cam_scanner.widgets.export_page import ExportPage
from oss_cam_scanner.widgets.image_list import ImageListView
from oss_cam_scanner.widgets.preview_page import PreviewPage


class ImageListBinder(QObject):
    def __init__(
        self,
        view: ImageListView,
        store: DocumentStore,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._store = store

        self._view.current_index_selected.connect(self._store.set_current_index)
        self._store.items_changed.connect(self._refresh_items)
        self._store.item_changed.connect(self._refresh_item)
        self._store.current_index_changed.connect(self._view.set_current_index)
        self._refresh_items()

    def _refresh_items(self) -> None:
        self._view.set_items(self._store.items())

    def _refresh_item(self, index: int) -> None:
        item = self._store.item(index)
        if item is not None:
            self._view.refresh_item(index, item)


class AdjustPageBinder(QObject):
    preview_ready = Signal()
    preview_failed = Signal(str)

    def __init__(
        self,
        page: AdjustPage,
        store: DocumentStore,
        edit_controller: EditController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._page = page
        self._store = store
        self._edit_controller = edit_controller

        self._page.polygon_changed.connect(self._edit_controller.set_current_polygon)
        self._page.reset_requested.connect(self._reset_current_corners)
        self._page.preview_requested.connect(self._prepare_preview)
        self._store.current_item_changed.connect(self._show_current_item)
        self._store.item_changed.connect(self._refresh_changed_item)

    def refresh_from_current_item(self) -> None:
        self._show_current_item(self._store.current_item())

    def _show_current_item(self, item: ImageItem | None) -> None:
        if item is None:
            return
        self._page.set_image(item.original_rgb)
        self._page.set_polygon(item.corners)

    def _refresh_changed_item(self, index: int) -> None:
        if index == self._store.current_index():
            self._show_current_item(self._store.current_item())

    def _reset_current_corners(self) -> None:
        self._edit_controller.reset_current_corners()
        self.refresh_from_current_item()

    def _prepare_preview(self) -> None:
        result = self._edit_controller.prepare_current_preview()
        if result.ok:
            self.preview_ready.emit()
            return
        self.preview_failed.emit(result.error or "Could not warp document region.")


class PreviewPageBinder(QObject):
    adjust_region_requested = Signal()
    preview_failed = Signal(str)
    save_failed = Signal(str)
    saved = Signal()
    next_requested = Signal(int)
    export_requested = Signal()

    def __init__(
        self,
        page: PreviewPage,
        store: DocumentStore,
        preview_state: PreviewState,
        preview_controller: PreviewController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._page = page
        self._store = store
        self._preview_controller = preview_controller

        self._page.adjust_region_requested.connect(self.adjust_region_requested.emit)
        self._page.filters_changed.connect(self._set_filters)
        self._page.rotate_requested.connect(self._rotate_current)
        self._page.save_requested.connect(self._save_current)
        self._page.save_next_requested.connect(self._save_and_next)
        self._page.save_export_requested.connect(self._save_and_export)

        preview_state.preview_image_changed.connect(self._page.set_preview_image)
        self._store.current_index_changed.connect(self.refresh_action_visibility)
        self._store.current_item_changed.connect(self._show_current_filters)
        self.refresh_action_visibility()

    def refresh_preview(self) -> None:
        self._show_current_filters(self._store.current_item())
        result = self._preview_controller.refresh_preview()
        if not result.ok:
            self.preview_failed.emit(result.error or "Could not refresh preview.")

    def show_saved_preview(self) -> None:
        result = self._preview_controller.show_saved_preview()
        if not result.ok:
            self.preview_failed.emit(result.error or "Could not show saved preview.")
            return
        self._show_current_filters(self._store.current_item())

    def refresh_action_visibility(self, *_args: object) -> None:
        current_index = self._store.current_index()
        self._page.set_save_actions_for_last_item(
            current_index >= 0 and current_index == len(self._store.items()) - 1
        )

    def save_current(self) -> None:
        self._save_current()

    def _set_filters(self, filters: object) -> None:
        result = self._preview_controller.set_current_filters(set(filters))
        if not result.ok:
            self.preview_failed.emit(result.error or "Could not apply filters.")

    def _show_current_filters(self, item: ImageItem | None) -> None:
        if item is None:
            self._page.set_selected_filters(set())
            return
        self._page.set_selected_filters(item.selected_filters)

    def _rotate_current(self, turns_delta: int) -> None:
        result = self._preview_controller.rotate_current(turns_delta)
        if not result.ok:
            self.preview_failed.emit(result.error or "Could not rotate preview.")

    def _save_current(self) -> None:
        result = self._preview_controller.save_current()
        if result.ok:
            self.saved.emit()
            return
        self.save_failed.emit(result.error or "Could not save current page.")

    def _save_and_next(self) -> None:
        result = self._preview_controller.save_current_and_select_next()
        if not result.ok:
            self.save_failed.emit(result.error or "Could not save current page.")
            return
        if result.next_index is not None:
            self.next_requested.emit(result.next_index)
        else:
            self.saved.emit()

    def _save_and_export(self) -> None:
        result = self._preview_controller.save_current_and_request_export()
        if result.ok:
            self.export_requested.emit()
            return
        self.save_failed.emit(result.error or "Could not save current page.")


class ExportPageBinder(QObject):
    back_requested = Signal()
    export_images_path_requested = Signal()
    export_pdfs_path_requested = Signal()
    export_combined_pdf_path_requested = Signal()
    export_failed = Signal(str)
    export_complete = Signal(str)

    def __init__(
        self,
        page: ExportPage,
        store: DocumentStore,
        export_state: ExportState,
        export_controller: ExportController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._page = page
        self._store = store
        self._export_state = export_state
        self._export_controller = export_controller

        self._page.back_requested.connect(self.back_requested.emit)
        self._page.move_up_requested.connect(self._export_state.move_index_up)
        self._page.move_down_requested.connect(self._export_state.move_index_down)
        self._page.pdf_page_size_changed.connect(self._set_pdf_page_size_option)
        self._page.export_images_requested.connect(
            self.export_images_path_requested.emit
        )
        self._page.export_pdfs_requested.connect(self.export_pdfs_path_requested.emit)
        self._page.export_combined_pdf_requested.connect(
            self.export_combined_pdf_path_requested.emit
        )

        self._store.saved_items_changed.connect(self.sync_saved_items)
        self._export_state.export_state_changed.connect(self.refresh_saved_items)
        self._export_state.pdf_page_size_option_changed.connect(
            self._page.set_pdf_page_size_option
        )
        self.sync_saved_items()

    def sync_saved_items(self) -> None:
        self._export_state.sync_with_saved_indices(
            [index for index, _item in self._store.saved_items()]
        )
        self.refresh_saved_items()

    def refresh_saved_items(self) -> None:
        self._page.set_saved_items(
            self._store.saved_items(),
            self._export_state.ordered_indices(),
        )
        self._update_pdf_page_size_label()

    def has_saved_items(self) -> bool:
        return bool(self._export_controller.ordered_saved_items())

    def first_output_stem(self) -> str:
        items = self._export_controller.ordered_saved_items()
        if not items:
            return "scan"
        return items[0].path.stem

    def first_output_directory(self) -> Path:
        items = self._export_controller.ordered_saved_items()
        if not items:
            return Path()
        return items[0].path.parent

    def export_images_to(self, directory: Path) -> None:
        result = self._export_controller.export_images(directory)
        if result.ok:
            self.export_complete.emit(f"Exported {result.count} image file(s).")
            return
        self.export_failed.emit(result.error or "Export failed.")

    def export_pdfs_to(self, directory: Path) -> None:
        result = self._export_controller.export_pdfs(directory)
        if result.ok:
            self.export_complete.emit(f"Exported {result.count} PDF file(s).")
            return
        self.export_failed.emit(result.error or "Export failed.")

    def export_combined_pdf_to(self, path: Path) -> None:
        result = self._export_controller.export_combined_pdf(path)
        if result.ok:
            self.export_complete.emit(f"Exported {result.count} page PDF.")
            return
        self.export_failed.emit(result.error or "Export failed.")

    def _set_pdf_page_size_option(self, option: object) -> None:
        if isinstance(option, PdfPageSizeOption):
            self._export_state.set_pdf_page_size_option(option)

    def _update_pdf_page_size_label(self) -> None:
        if not self._export_controller.ordered_saved_items():
            if self._export_state.pdf_page_size_option() == PdfPageSizeOption.AUTO:
                self._page.set_pdf_page_size_label("Auto selected: no saved pages")
            else:
                self._page.set_pdf_page_size_label("PDF page size: no saved pages")
            return
        try:
            layout = self._export_controller.resolve_current_pdf_layout()
        except Exception as exc:
            self._page.set_pdf_page_size_label(str(exc))
            return
        if self._export_state.pdf_page_size_option() == PdfPageSizeOption.AUTO:
            self._page.set_pdf_page_size_label(f"Auto selected: {layout.name}")
        else:
            self._page.set_pdf_page_size_label(f"PDF page size: {layout.name}")

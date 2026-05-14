from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from oss_cam_scanner.core.detection import detect_document
from oss_cam_scanner.core.filters import ScanFilter, apply_filters
from oss_cam_scanner.core.geometry import order_points, warp_perspective
from oss_cam_scanner.core.io import (
    PdfPageLayout,
    read_image_rgb,
    resolve_pdf_page_layout,
    write_combined_pdf,
    write_image,
    write_pdf,
)
from oss_cam_scanner.models import ImageArray, ImageItem, ItemStatus, PointArray
from oss_cam_scanner.stores import DocumentStore, ExportState, PreviewState


@dataclass(slots=True)
class ImportFailure:
    path: Path
    error: str


@dataclass(slots=True)
class ImportResult:
    imported_indices: list[int]
    failures: list[ImportFailure]


@dataclass(slots=True)
class EditPreviewResult:
    ok: bool
    index: int | None = None
    error: str | None = None


@dataclass(slots=True)
class PreviewResult:
    ok: bool
    image: ImageArray | None = None
    error: str | None = None


@dataclass(slots=True)
class SaveResult:
    ok: bool
    index: int | None = None
    error: str | None = None


@dataclass(slots=True)
class SaveNextResult:
    ok: bool
    saved_index: int | None = None
    next_index: int | None = None
    error: str | None = None


@dataclass(slots=True)
class ExportResult:
    ok: bool
    count: int = 0
    error: str | None = None


class ImportController:
    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    def add_images(self, paths: list[Path]) -> ImportResult:
        items: list[ImageItem] = []
        failures: list[ImportFailure] = []
        for path in paths:
            try:
                image = read_image_rgb(path)
                detection = detect_document(image)
                items.append(
                    ImageItem(
                        path=path,
                        original_rgb=image,
                        detected_corners=detection.corners.copy(),
                        corners=detection.corners.copy(),
                    )
                )
            except Exception as exc:
                failures.append(ImportFailure(path=path, error=str(exc)))
        return ImportResult(
            imported_indices=self._store.add_items(items),
            failures=failures,
        )


class EditController:
    def __init__(self, store: DocumentStore, preview_state: PreviewState) -> None:
        self._store = store
        self._preview_state = preview_state

    def set_current_polygon(self, polygon: PointArray) -> None:
        index = self._store.current_index()
        if index >= 0:
            self._store.set_item_corners(index, polygon)
            self._preview_state.clear_preview_image()

    def reset_current_corners(self) -> None:
        index = self._store.current_index()
        if index >= 0:
            self._store.reset_item_corners(index)
            self._preview_state.clear_preview_image()

    def prepare_current_preview(self) -> EditPreviewResult:
        index = self._store.current_index()
        item = self._store.current_item()
        if item is None:
            return EditPreviewResult(ok=False, error="No image is selected.")
        try:
            corners = order_points(item.corners)
            warped_rgb = warp_perspective(item.original_rgb, corners)
        except Exception as exc:
            self._store.set_item_status(index, ItemStatus.FAILED, str(exc))
            self._preview_state.clear_preview_image()
            return EditPreviewResult(ok=False, index=index, error=str(exc))
        self._store.set_item_corners(index, corners)
        self._store.set_item_warped_image(index, warped_rgb)
        self._store.set_item_status(index, ItemStatus.PREVIEWED)
        self._preview_state.clear_preview_image()
        return EditPreviewResult(ok=True, index=index)


class PreviewController:
    def __init__(self, store: DocumentStore, preview_state: PreviewState) -> None:
        self._store = store
        self._preview_state = preview_state

    def set_filters(self, filters: set[ScanFilter]) -> PreviewResult:
        self._preview_state.set_selected_filters(filters)
        return self.refresh_preview()

    def refresh_preview(self) -> PreviewResult:
        index = self._store.current_index()
        item = self._store.current_item()
        if item is None:
            return PreviewResult(ok=False, error="No image is selected.")
        try:
            warped_rgb = item.warped_rgb
            if warped_rgb is None:
                warped_rgb = warp_perspective(item.original_rgb, item.corners)
                self._store.set_item_warped_image(index, warped_rgb)
            filtered_rgb = apply_filters(
                warped_rgb,
                self._preview_state.selected_filters(),
            )
            image = self._rotate_image(filtered_rgb, item.rotation_turns)
        except Exception as exc:
            self._store.set_item_status(index, ItemStatus.FAILED, str(exc))
            self._preview_state.clear_preview_image()
            return PreviewResult(ok=False, error=str(exc))
        self._preview_state.set_preview_image(image)
        return PreviewResult(ok=True, image=image)

    def rotate_current(self, turns_delta: int) -> PreviewResult:
        index = self._store.current_index()
        item = self._store.current_item()
        if item is None:
            return PreviewResult(ok=False, error="No image is selected.")
        self._store.set_item_rotation(index, item.rotation_turns + turns_delta)
        self._preview_state.clear_preview_image()
        return self.refresh_preview()

    def save_current(self) -> SaveResult:
        index = self._store.current_index()
        if self._store.current_item() is None:
            return SaveResult(ok=False, error="No image is selected.")
        preview_image = self._preview_state.preview_image()
        if preview_image is None:
            result = self.refresh_preview()
            if not result.ok:
                return SaveResult(ok=False, index=index, error=result.error)
            preview_image = result.image
        if preview_image is None:
            return SaveResult(ok=False, index=index, error="No preview image exists.")
        self._store.set_item_saved_image(index, preview_image.copy())
        self._store.set_item_status(index, ItemStatus.SAVED)
        return SaveResult(ok=True, index=index)

    def save_current_and_select_next(self) -> SaveNextResult:
        result = self.save_current()
        if not result.ok:
            return SaveNextResult(
                ok=False,
                saved_index=result.index,
                error=result.error,
            )
        assert result.index is not None
        return SaveNextResult(
            ok=True,
            saved_index=result.index,
            next_index=self._store.next_not_saved_index(result.index),
        )

    def save_current_and_request_export(self) -> SaveResult:
        return self.save_current()

    def _rotate_image(self, image_rgb: ImageArray, clockwise_turns: int) -> ImageArray:
        turns = clockwise_turns % 4
        if turns == 0:
            return image_rgb
        return np.ascontiguousarray(np.rot90(image_rgb, k=-turns))


class ExportController:
    def __init__(self, store: DocumentStore, export_state: ExportState) -> None:
        self._store = store
        self._export_state = export_state

    def ordered_saved_items(self) -> list[ImageItem]:
        items = self._store.items()
        ordered: list[ImageItem] = []
        for index in self._export_state.ordered_indices():
            if 0 <= index < len(items):
                item = items[index]
                if item.saved_rgb is not None:
                    ordered.append(item)
        return ordered

    def resolve_current_pdf_layout(self) -> PdfPageLayout:
        first_saved = next(
            (
                item.saved_rgb
                for item in self.ordered_saved_items()
                if item.saved_rgb is not None
            ),
            None,
        )
        if first_saved is None:
            raise ValueError("Cannot export a PDF without saved pages.")
        return resolve_pdf_page_layout(
            self._export_state.pdf_page_size_option(),
            first_saved,
        )

    def export_images(self, directory: Path) -> ExportResult:
        items = self.ordered_saved_items()
        if not items:
            return ExportResult(
                ok=False,
                error="Save at least one page before exporting.",
            )
        try:
            for item in items:
                assert item.saved_rgb is not None
                write_image(directory / f"{item.path.stem}-scan.png", item.saved_rgb)
        except Exception as exc:
            return ExportResult(ok=False, error=str(exc))
        return ExportResult(ok=True, count=len(items))

    def export_pdfs(self, directory: Path) -> ExportResult:
        items = self.ordered_saved_items()
        if not items:
            return ExportResult(
                ok=False,
                error="Save at least one page before exporting.",
            )
        try:
            layout = self.resolve_current_pdf_layout()
            for item in items:
                assert item.saved_rgb is not None
                write_pdf(
                    directory / f"{item.path.stem}-scan.pdf",
                    item.saved_rgb,
                    layout,
                )
        except Exception as exc:
            return ExportResult(ok=False, error=str(exc))
        return ExportResult(ok=True, count=len(items))

    def export_combined_pdf(self, path: Path) -> ExportResult:
        items = self.ordered_saved_items()
        if not items:
            return ExportResult(
                ok=False,
                error="Save at least one page before exporting.",
            )
        try:
            images = [item.saved_rgb for item in items if item.saved_rgb is not None]
            layout = self.resolve_current_pdf_layout()
            write_combined_pdf(path, images, layout)
        except Exception as exc:
            return ExportResult(ok=False, error=str(exc))
        return ExportResult(ok=True, count=len(items))

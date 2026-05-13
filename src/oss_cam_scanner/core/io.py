from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from oss_cam_scanner.models import ImageArray

PDF_DPI = 300.0


class PdfPageSizeOption(StrEnum):
    AUTO = "Auto"
    A4 = "A4"
    LETTER = "Letter"
    FIT_TO_IMAGE = "Fit to image"


@dataclass(frozen=True, slots=True)
class PdfPageLayout:
    name: str
    page_size_px: tuple[int, int] | None


def read_image_rgb(path: Path) -> ImageArray:
    data = np.fromfile(path, dtype=np.uint8)
    bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Could not read image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def write_image(path: Path, image_rgb: ImageArray) -> None:
    suffix = path.suffix.lower()
    image = pillow_from_rgb(image_rgb)
    if suffix in {".jpg", ".jpeg"}:
        image.save(path, quality=95)
    else:
        if suffix != ".png":
            path = path.with_suffix(".png")
        image.save(path)


def resolve_pdf_page_layout(
    option: PdfPageSizeOption,
    first_image_rgb: ImageArray,
) -> PdfPageLayout:
    if option == PdfPageSizeOption.AUTO:
        return _auto_pdf_page_layout(first_image_rgb)
    if option == PdfPageSizeOption.A4:
        return _standard_pdf_page_layout("A4", (8.27, 11.69), first_image_rgb)
    if option == PdfPageSizeOption.LETTER:
        return _standard_pdf_page_layout("Letter", (8.5, 11.0), first_image_rgb)
    return PdfPageLayout(name=PdfPageSizeOption.FIT_TO_IMAGE.value, page_size_px=None)


def write_pdf(path: Path, image_rgb: ImageArray, layout: PdfPageLayout) -> None:
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    _pdf_page_from_rgb(image_rgb, layout).save(path, "PDF", resolution=PDF_DPI)


def write_combined_pdf(
    path: Path,
    images_rgb: list[ImageArray],
    layout: PdfPageLayout,
) -> None:
    if not images_rgb:
        raise ValueError("Cannot export a PDF without saved pages.")
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    pages = [_pdf_page_from_rgb(image, layout) for image in images_rgb]
    first, rest = pages[0], pages[1:]
    first.save(path, "PDF", resolution=PDF_DPI, save_all=True, append_images=rest)


def image_to_qimage(image_rgb: ImageArray) -> QImage:
    contiguous = np.ascontiguousarray(image_rgb)
    height, width, channels = contiguous.shape
    bytes_per_line = channels * width
    return QImage(contiguous.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).copy()


def image_to_pixmap(image_rgb: ImageArray) -> QPixmap:
    return QPixmap.fromImage(image_to_qimage(image_rgb))


def pillow_from_rgb(image_rgb: ImageArray) -> Image.Image:
    return Image.fromarray(image_rgb, mode="RGB")


def _auto_pdf_page_layout(first_image_rgb: ImageArray) -> PdfPageLayout:
    height, width = first_image_rgb.shape[:2]
    image_ratio = min(width, height) / max(width, height)
    standard_sizes = (
        ("A4", (8.27, 11.69)),
        ("Letter", (8.5, 11.0)),
    )
    best_name, best_size = min(
        standard_sizes,
        key=lambda size: abs(image_ratio - (min(size[1]) / max(size[1]))),
    )
    best_ratio = min(best_size) / max(best_size)
    if abs(image_ratio - best_ratio) > 0.08:
        return PdfPageLayout(name=PdfPageSizeOption.FIT_TO_IMAGE.value, page_size_px=None)
    return _standard_pdf_page_layout(best_name, best_size, first_image_rgb)


def _standard_pdf_page_layout(
    name: str,
    size_inches: tuple[float, float],
    first_image_rgb: ImageArray,
) -> PdfPageLayout:
    height, width = first_image_rgb.shape[:2]
    page_width, page_height = size_inches
    orientation = "landscape" if width > height else "portrait"
    if orientation == "landscape":
        page_width, page_height = page_height, page_width
    return PdfPageLayout(
        name=f"{name} {orientation}",
        page_size_px=(round(page_width * PDF_DPI), round(page_height * PDF_DPI)),
    )


def _pdf_page_from_rgb(image_rgb: ImageArray, layout: PdfPageLayout) -> Image.Image:
    image = pillow_from_rgb(image_rgb)
    if layout.page_size_px is None:
        return image

    page_width, page_height = layout.page_size_px
    scale = min(page_width / image.width, page_height / image.height)
    output_width = max(1, round(image.width * scale))
    output_height = max(1, round(image.height * scale))
    resized = image.resize((output_width, output_height), Image.Resampling.LANCZOS)
    page = Image.new("RGB", (page_width, page_height), "white")
    left = (page_width - output_width) // 2
    top = (page_height - output_height) // 2
    page.paste(resized, (left, top))
    return page

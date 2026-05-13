from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage, QPixmap

from oss_cam_scanner.models import ImageArray


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


def image_to_qimage(image_rgb: ImageArray) -> QImage:
    contiguous = np.ascontiguousarray(image_rgb)
    height, width, channels = contiguous.shape
    bytes_per_line = channels * width
    return QImage(contiguous.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).copy()


def image_to_pixmap(image_rgb: ImageArray) -> QPixmap:
    return QPixmap.fromImage(image_to_qimage(image_rgb))


def pillow_from_rgb(image_rgb: ImageArray) -> Image.Image:
    return Image.fromarray(image_rgb, mode="RGB")

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from oss_cam_scanner.core.filters import ScanFilter

ImageArray = NDArray[np.uint8]
PointArray = NDArray[np.float32]


class ItemStatus(StrEnum):
    PENDING = "pending"
    PREVIEWED = "previewed"
    SAVED = "saved for export"
    FAILED = "failed"


@dataclass(slots=True)
class DetectionResult:
    corners: PointArray
    confidence: float
    used_fallback: bool
    message: str


@dataclass(slots=True)
class ImageItem:
    path: Path
    original_rgb: ImageArray
    detected_corners: PointArray
    corners: PointArray
    status: ItemStatus = ItemStatus.PENDING
    warped_rgb: ImageArray | None = None
    saved_rgb: ImageArray | None = None
    selected_filters: set[ScanFilter] = field(default_factory=set)
    rotation_turns: int = 0
    error: str | None = None

    @property
    def display_name(self) -> str:
        return self.path.name

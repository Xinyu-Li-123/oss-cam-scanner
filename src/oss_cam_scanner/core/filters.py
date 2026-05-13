from __future__ import annotations

from enum import StrEnum

import cv2
import numpy as np

from oss_cam_scanner.models import ImageArray


class ScanFilter(StrEnum):
    NO_SHADOW = "no shadow"
    LIGHTEN = "lighten"
    ENHANCE = "enhance"


FILTER_ORDER: tuple[ScanFilter, ...] = (
    ScanFilter.NO_SHADOW,
    ScanFilter.LIGHTEN,
    ScanFilter.ENHANCE,
)


def apply_filters(image_rgb: ImageArray, selected_filters: set[ScanFilter]) -> ImageArray:
    result = image_rgb.copy()
    for scan_filter in FILTER_ORDER:
        if scan_filter in selected_filters:
            result = apply_filter(result, scan_filter)
    return result


def apply_filter(image_rgb: ImageArray, scan_filter: ScanFilter) -> ImageArray:
    if scan_filter == ScanFilter.NO_SHADOW:
        return remove_shadow(image_rgb)
    if scan_filter == ScanFilter.LIGHTEN:
        return lighten(image_rgb)
    if scan_filter == ScanFilter.ENHANCE:
        return enhance(image_rgb)
    raise ValueError(f"Unsupported filter: {scan_filter}")


def remove_shadow(image_rgb: ImageArray) -> ImageArray:
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    kernel_size = _large_odd_kernel(image_rgb)
    background = cv2.GaussianBlur(l_channel, (kernel_size, kernel_size), 0)
    normalized = cv2.divide(l_channel, background, scale=235)
    normalized = cv2.normalize(normalized, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    merged = cv2.merge((normalized.astype(np.uint8), a_channel, b_channel))
    result = cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)
    return _blend_preserving_darks(image_rgb, result, amount=0.78)


def lighten(image_rgb: ImageArray) -> ImageArray:
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    l_float = l_channel.astype(np.float32) / 255.0
    lifted = np.power(l_float, 0.78) * 255.0
    lifted = np.clip(lifted + 8.0, 0, 255).astype(np.uint8)
    merged = cv2.merge((lifted, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)


def enhance(image_rgb: ImageArray) -> ImageArray:
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(l_channel)
    sharpened = _unsharp_mask(contrast)
    merged = cv2.merge((sharpened, a_channel, b_channel))
    enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)
    return cv2.convertScaleAbs(enhanced, alpha=1.04, beta=2)


def _unsharp_mask(channel: ImageArray) -> ImageArray:
    blurred = cv2.GaussianBlur(channel, (0, 0), 1.2)
    return cv2.addWeighted(channel, 1.45, blurred, -0.45, 0)


def _large_odd_kernel(image_rgb: ImageArray) -> int:
    shortest = min(image_rgb.shape[:2])
    size = max(31, int(shortest * 0.08))
    return size + 1 if size % 2 == 0 else size


def _blend_preserving_darks(original_rgb: ImageArray, filtered_rgb: ImageArray, amount: float) -> ImageArray:
    gray = cv2.cvtColor(original_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    dark_protection = np.clip((gray - 25.0) / 95.0, 0.0, 1.0)
    weight = (dark_protection * amount)[..., np.newaxis]
    blended = original_rgb.astype(np.float32) * (1.0 - weight) + filtered_rgb.astype(np.float32) * weight
    return np.clip(blended, 0, 255).astype(np.uint8)

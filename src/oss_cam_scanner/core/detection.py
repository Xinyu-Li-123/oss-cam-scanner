from __future__ import annotations

import cv2
import numpy as np

from oss_cam_scanner.core.geometry import inset_rectangle, order_points
from oss_cam_scanner.models import DetectionResult, ImageArray, PointArray


def detect_document(image_rgb: ImageArray) -> DetectionResult:
    height, width = image_rgb.shape[:2]
    scale = 700.0 / max(height, width)
    if scale < 1.0:
        resized = cv2.resize(image_rgb, (int(width * scale), int(height * scale)))
    else:
        scale = 1.0
        resized = image_rgb

    gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(gray, 60, 180)
    edged = cv2.dilate(edged, np.ones((3, 3), dtype=np.uint8), iterations=1)

    contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(resized.shape[0] * resized.shape[1])
    best: tuple[float, PointArray] | None = None

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:20]:
        area = cv2.contourArea(contour)
        if area < image_area * 0.08:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        points = approx.reshape(4, 2).astype(np.float32)
        rectangularity = area / max(cv2.contourArea(cv2.boxPoints(cv2.minAreaRect(points))), 1.0)
        score = area * max(0.2, rectangularity)
        if best is None or score > best[0]:
            best = (score, points)

    if best is None:
        return DetectionResult(
            corners=inset_rectangle(width, height),
            confidence=0.0,
            used_fallback=True,
            message="No document contour found; using inset rectangle.",
        )

    corners = order_points(best[1] / scale)
    confidence = min(1.0, best[0] / image_area)
    return DetectionResult(
        corners=corners.astype(np.float32),
        confidence=float(confidence),
        used_fallback=False,
        message="Document contour detected.",
    )

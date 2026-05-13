from __future__ import annotations

import cv2
import numpy as np

from oss_cam_scanner.models import ImageArray, PointArray


def order_points(points: PointArray) -> PointArray:
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    rect = np.zeros((4, 2), dtype=np.float32)

    sums = pts.sum(axis=1)
    rect[0] = pts[np.argmin(sums)]
    rect[2] = pts[np.argmax(sums)]

    diffs = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diffs)]
    rect[3] = pts[np.argmax(diffs)]
    return rect


def target_size(points: PointArray) -> tuple[int, int]:
    tl, tr, br, bl = order_points(points)
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    width = max(1, int(round(max(width_a, width_b))))
    height = max(1, int(round(max(height_a, height_b))))
    return width, height


def warp_perspective(image_rgb: ImageArray, points: PointArray) -> ImageArray:
    rect = order_points(points)
    width, height = target_size(rect)
    destination = np.array(
        [
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(rect, destination)
    return cv2.warpPerspective(image_rgb, matrix, (width, height))


def inset_rectangle(width: int, height: int, margin_ratio: float = 0.06) -> PointArray:
    margin_x = max(0.0, width * margin_ratio)
    margin_y = max(0.0, height * margin_ratio)
    return np.array(
        [
            [margin_x, margin_y],
            [width - 1 - margin_x, margin_y],
            [width - 1 - margin_x, height - 1 - margin_y],
            [margin_x, height - 1 - margin_y],
        ],
        dtype=np.float32,
    )

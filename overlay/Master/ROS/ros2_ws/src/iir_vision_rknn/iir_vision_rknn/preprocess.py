"""Letterbox preprocessing for fixed-size YOLO RKNN inputs.
固定尺寸 YOLO RKNN 输入的等比填充预处理。
"""

from __future__ import annotations

import numpy as np


def letterbox(image, size: int = 640):
    """Resize a BGR image into a square canvas and return the inverse transform.
    将 BGR 图像等比缩放到方形画布，并返回逆变换参数。

    Args:
        image: Source BGR image with shape (H, W, 3).
            形状为 (H, W, 3) 的源 BGR 图像。
        size: Target square side length in pixels.
            目标方形边长，单位为像素。

    Returns:
        A tuple of (rgb_canvas, scale, pad_x, pad_y).
        返回 (RGB 画布, 缩放比例, 横向填充, 纵向填充) 元组。
    """
    # Import OpenCV lazily so pure post-processing tests stay dependency-free.
    # 延迟导入 OpenCV，使纯后处理测试无需该依赖。
    import cv2

    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('image must be a BGR array with shape (H, W, 3)')
    height, width = image.shape[:2]
    if height <= 0 or width <= 0:
        raise ValueError('image dimensions must be positive')

    scale = min(float(size) / float(width), float(size) / float(height))
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    pad_x = (int(size) - new_width) // 2
    pad_y = (int(size) - new_height) // 2

    canvas = np.zeros((int(size), int(size), 3), dtype=np.uint8)
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    canvas[pad_y:pad_y + new_height, pad_x:pad_x + new_width] = resized
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    return rgb, scale, pad_x, pad_y

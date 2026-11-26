"""OpenCV annotation and JPEG codec helpers for inspection captures.
巡检抓拍的 OpenCV 标注与 JPEG 编解码辅助函数。
"""

from __future__ import annotations

import numpy as np

from .postprocess import Detection


def decode_jpeg(data: bytes):
    """Decode one compressed camera frame into a BGR image.
    将一帧压缩相机图像解码为 BGR 图像。
    """
    # Import OpenCV lazily to keep pure logic modules importable on hosts
    # without the imaging stack.
    # 延迟导入 OpenCV，确保无图像栈的主机也能导入纯逻辑模块。
    import cv2

    if not data:
        raise ValueError('Compressed camera frame is empty')
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Cannot decode the compressed camera frame')
    return image


def encode_jpeg(image, quality: int = 90) -> bytes:
    """Encode a BGR image as JPEG bytes.
    将 BGR 图像编码为 JPEG 字节。
    """
    import cv2

    if image is None or getattr(image, 'ndim', 0) != 3:
        raise ValueError('image must be a BGR array')
    ok, encoded = cv2.imencode(
        '.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError('JPEG encoding failed')
    return encoded.tobytes()


def draw_detections(image, detections: list[Detection]):
    """Draw labelled bounding boxes onto a copy of the BGR image.
    在 BGR 图像副本上绘制带标签的检测框。
    """
    import cv2

    if image is None:
        raise ValueError('image must not be None')
    canvas = image.copy()
    for detection in detections:
        x1 = int(round(detection.x_min))
        y1 = int(round(detection.y_min))
        x2 = int(round(detection.x_max))
        y2 = int(round(detection.y_max))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 255), 2)
        caption = f'{detection.label} {detection.confidence:.2f}'
        baseline_y = max(12, y1 - 6)
        cv2.putText(canvas, caption, (x1, baseline_y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 0, 255), 1, cv2.LINE_AA)
    return canvas

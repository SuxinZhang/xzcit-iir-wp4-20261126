"""Unit tests for letterbox preprocessing; skipped without OpenCV.
等比填充预处理的单元测试；缺少 OpenCV 时跳过。
"""

import numpy as np
import pytest

pytest.importorskip('cv2')

from iir_vision_rknn.preprocess import letterbox


def test_letterbox_preserves_aspect_ratio_and_padding():
    """Pad a landscape frame into a square RGB canvas.
    将横向画面填充到方形 RGB 画布。
    """
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    canvas, scale, pad_x, pad_y = letterbox(image, 640)
    assert canvas.shape == (640, 640, 3)
    assert scale == 1.0
    assert pad_x == 0
    assert pad_y == 80


def test_letterbox_rejects_non_bgr_arrays():
    """Reject inputs that are not three-channel images.
    拒绝非三通道图像输入。
    """
    with pytest.raises(ValueError):
        letterbox(np.zeros((480, 640), dtype=np.uint8), 640)

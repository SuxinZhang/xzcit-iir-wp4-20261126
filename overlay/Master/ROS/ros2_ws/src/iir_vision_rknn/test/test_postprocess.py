"""Unit tests for YOLOv8 post-processing and NMS.
YOLOv8 后处理与 NMS 的单元测试。
"""

import numpy as np
import pytest

from iir_vision_rknn.postprocess import decode_yolov8, nms


def test_nms_suppresses_overlapping_lower_score_box():
    """Keep the highest-score box and drop its near-duplicate.
    保留最高分检测框并丢弃其近重复框。
    """
    boxes = np.array([
        [0.0, 0.0, 10.0, 10.0],
        [0.0, 0.0, 9.0, 9.0],
        [50.0, 50.0, 60.0, 60.0],
    ])
    scores = np.array([0.90, 0.80, 0.70])
    assert nms(boxes, scores, 0.5) == [0, 2]


def test_decode_yolov8_restores_letterbox_coordinates():
    """Undo letterbox padding and scaling for two detections.
    将两个检测结果从等比填充坐标还原到原图坐标。
    """
    # Shape (1, 4 + 2 classes, 2 anchors); pixel-space boxes on a 640 input.
    # 形状为 (1, 4 + 2 类, 2 个锚点)；640 输入上的像素坐标检测框。
    output = np.zeros((1, 6, 2), dtype=np.float32)
    output[0, :4, 0] = [320.0, 320.0, 100.0, 100.0]
    output[0, 4, 0] = 0.95
    output[0, :4, 1] = [200.0, 400.0, 40.0, 40.0]
    output[0, 5, 1] = 0.75

    detections = decode_yolov8(
        [output], ['insulator_defect', 'rust'],
        original_width=1280, original_height=720,
        scale=0.5, pad_x=0, pad_y=140,
        conf_threshold=0.3, nms_iou=0.5, input_size=640)

    assert len(detections) == 2
    assert detections[0].label == 'insulator_defect'
    assert detections[0].confidence == pytest.approx(0.95, abs=1e-6)
    assert detections[0].x_min == pytest.approx(540.0, abs=1e-6)
    assert detections[0].y_min == pytest.approx(260.0, abs=1e-6)
    assert detections[0].x_max == pytest.approx(740.0, abs=1e-6)
    assert detections[0].y_max == pytest.approx(460.0, abs=1e-6)
    assert detections[1].label == 'rust'


def test_decode_yolov8_accepts_normalised_boxes():
    """Scale normalised boxes by the model input size before restoration.
    在还原前将归一化检测框按模型输入尺寸缩放。
    """
    output = np.zeros((5, 1), dtype=np.float32)
    output[:4, 0] = [0.5, 0.5, 0.1, 0.1]
    output[4, 0] = 0.88

    detections = decode_yolov8(
        [output], ['rust'], original_width=640, original_height=640,
        scale=1.0, pad_x=0, pad_y=0,
        conf_threshold=0.25, nms_iou=0.45, input_size=640)

    assert len(detections) == 1
    assert detections[0].x_min == pytest.approx(288.0, abs=1e-6)
    assert detections[0].x_max == pytest.approx(352.0, abs=1e-6)


def test_decode_yolov8_returns_empty_below_threshold():
    """Return an empty list when every score is below the threshold.
    当所有分数低于阈值时返回空列表。
    """
    output = np.zeros((1, 5, 1), dtype=np.float32)
    output[0, 4, 0] = 0.10
    assert decode_yolov8([output], ['rust'], 640, 480, 1.0, 0, 0) == []

"""Pure NumPy post-processing for YOLOv8/v11 RKNN detection outputs.
纯 NumPy 实现的 YOLOv8/v11 RKNN 检测输出后处理。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Detection:
    """One detection expressed in original image pixel coordinates.
    以原图像素坐标表示的单个检测结果。
    """

    label: str
    confidence: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def as_dict(self) -> dict:
        """Return a JSON-serialisable dictionary.
        返回可序列化为 JSON 的字典。
        """
        return {
            'label': self.label,
            'confidence': round(float(self.confidence), 4),
            'bbox': [
                round(float(self.x_min), 2),
                round(float(self.y_min), 2),
                round(float(self.x_max), 2),
                round(float(self.y_max), 2),
            ],
            'center': [
                round(float((self.x_min + self.x_max) / 2.0), 2),
                round(float((self.y_min + self.y_max) / 2.0), 2),
            ],
        }


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Greedy non-maximum suppression over one class.
    对单一类别执行贪心非极大值抑制。

    Args:
        boxes: Array with shape (N, 4) in xyxy order.
            形状为 (N, 4)、按 xyxy 排列的检测框数组。
        scores: Array with shape (N,).
            形状为 (N,) 的置信度数组。
        iou_threshold: Maximum IoU allowed between kept boxes.
            保留框之间允许的最大 IoU。

    Returns:
        Indices of the kept boxes.
        被保留检测框的索引列表。
    """
    if boxes.size == 0:
        return []
    order = np.argsort(np.asarray(scores))[::-1]
    keep: list[int] = []
    areas = np.maximum(boxes[:, 2] - boxes[:, 0], 0.0) * np.maximum(
        boxes[:, 3] - boxes[:, 1], 0.0)
    while order.size > 0:
        current = int(order[0])
        keep.append(current)
        if order.size == 1:
            break
        rest = order[1:]
        inter_x1 = np.maximum(boxes[current, 0], boxes[rest, 0])
        inter_y1 = np.maximum(boxes[current, 1], boxes[rest, 1])
        inter_x2 = np.minimum(boxes[current, 2], boxes[rest, 2])
        inter_y2 = np.minimum(boxes[current, 3], boxes[rest, 3])
        inter = np.maximum(inter_x2 - inter_x1, 0.0) * np.maximum(inter_y2 - inter_y1, 0.0)
        union = areas[current] + areas[rest] - inter
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0.0)
        order = rest[iou <= float(iou_threshold)]
    return keep


def _normalise_output(outputs, expected_channels: int) -> np.ndarray:
    """Normalise an RKNN output tensor to shape (anchors, channels).
    将 RKNN 输出张量规范化为 (锚点数, 通道数) 形状。
    """
    if not outputs:
        raise ValueError('RKNN inference returned no outputs')
    array = np.asarray(outputs[0], dtype=np.float32)
    if array.ndim == 3:
        if array.shape[0] != 1:
            raise ValueError('Expected a single YOLO output batch')
        array = array[0]
    if array.ndim != 2:
        raise ValueError('YOLO output must be a 2-D tensor after batch removal')
    if array.shape[0] == expected_channels:
        array = array.T
    elif array.shape[1] != expected_channels:
        raise ValueError(
            f'YOLO output channels mismatch: got {array.shape}, expected {expected_channels}')
    if not np.isfinite(array).all():
        raise ValueError('YOLO output contains non-finite values')
    return array


def decode_yolov8(outputs, labels, original_width: int, original_height: int,
                  scale: float, pad_x: float, pad_y: float,
                  conf_threshold: float = 0.25, nms_iou: float = 0.45,
                  input_size: int = 640) -> list[Detection]:
    """Decode YOLOv8/v11 output tensors into original-image detections.
    将 YOLOv8/v11 输出张量解码为原图坐标系下的检测结果。

    Args:
        outputs: Raw RKNN output list; the first tensor carries the predictions.
            RKNN 原始输出列表，第一个张量承载预测结果。
        labels: Ordered class label keys matching model channel order.
            与模型通道顺序一致的类别标签键列表。
        original_width: Source image width in pixels.
            源图像宽度，单位为像素。
        original_height: Source image height in pixels.
            源图像高度，单位为像素。
        scale: Letterbox scale returned by preprocess.letterbox.
            preprocess.letterbox 返回的缩放比例。
        pad_x: Horizontal letterbox padding in pixels.
            横向等比填充像素数。
        pad_y: Vertical letterbox padding in pixels.
            纵向等比填充像素数。
        conf_threshold: Minimum confidence to accept a detection.
            接受检测的最小置信度。
        nms_iou: IoU threshold used by per-class NMS.
            按类别 NMS 使用的 IoU 阈值。
        input_size: Model input side length in pixels.
            模型输入边长，单位为像素。

    Returns:
        Detections sorted by descending confidence.
        按置信度降序排列的检测结果列表。
    """
    if not labels:
        raise ValueError('labels must not be empty')
    if scale <= 0.0:
        raise ValueError('letterbox scale must be positive')

    array = _normalise_output(outputs, 4 + len(labels))
    boxes = array[:, :4].astype(np.float64)
    class_scores = array[:, 4:4 + len(labels)].astype(np.float64)
    class_ids = np.argmax(class_scores, axis=1)
    scores = class_scores[np.arange(class_scores.shape[0]), class_ids]

    keep = scores >= float(conf_threshold)
    if not np.any(keep):
        return []
    boxes = boxes[keep]
    scores = scores[keep]
    class_ids = class_ids[keep]

    # Accept both normalised boxes (0..1) and model-input pixel boxes (0..640).
    # 同时兼容归一化坐标（0..1）与模型输入像素坐标（0..640）。
    if float(np.max(boxes)) <= 2.0:
        boxes = boxes * float(input_size)

    center_x = boxes[:, 0]
    center_y = boxes[:, 1]
    width = boxes[:, 2]
    height = boxes[:, 3]
    x1 = (center_x - width / 2.0 - float(pad_x)) / float(scale)
    y1 = (center_y - height / 2.0 - float(pad_y)) / float(scale)
    x2 = (center_x + width / 2.0 - float(pad_x)) / float(scale)
    y2 = (center_y + height / 2.0 - float(pad_y)) / float(scale)
    x1 = np.clip(x1, 0.0, max(float(original_width) - 1.0, 0.0))
    y1 = np.clip(y1, 0.0, max(float(original_height) - 1.0, 0.0))
    x2 = np.clip(x2, 0.0, max(float(original_width) - 1.0, 0.0))
    y2 = np.clip(y2, 0.0, max(float(original_height) - 1.0, 0.0))
    boxes = np.stack((x1, y1, x2, y2), axis=1)

    valid = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
    boxes = boxes[valid]
    scores = scores[valid]
    class_ids = class_ids[valid]
    if boxes.size == 0:
        return []

    detections: list[Detection] = []
    for class_id in np.unique(class_ids):
        indices = np.flatnonzero(class_ids == class_id)
        for kept in nms(boxes[indices], scores[indices], nms_iou):
            absolute = int(indices[kept])
            label = labels[int(class_id)] if int(class_id) < len(labels) else f'class_{int(class_id)}'
            detections.append(Detection(
                label=label,
                confidence=float(scores[absolute]),
                x_min=float(boxes[absolute, 0]),
                y_min=float(boxes[absolute, 1]),
                x_max=float(boxes[absolute, 2]),
                y_max=float(boxes[absolute, 3]),
            ))
    detections.sort(key=lambda item: item.confidence, reverse=True)
    return detections

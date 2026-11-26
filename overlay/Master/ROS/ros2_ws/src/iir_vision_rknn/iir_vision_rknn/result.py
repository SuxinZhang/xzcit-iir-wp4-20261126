"""Build structured JSON results shared by ROS, the gateway, and web clients.
构建由 ROS、网关与 Web 客户端共享的结构化 JSON 结果。
"""

from __future__ import annotations

from .postprocess import Detection


def severity_for(detections: list[Detection]) -> str:
    """Map the highest confidence to a coarse alert severity.
    将最高置信度映射为粗粒度告警级别。
    """
    if not detections:
        return 'none'
    highest = max(float(item.confidence) for item in detections)
    if highest >= 0.85:
        return 'high'
    if highest >= 0.60:
        return 'medium'
    return 'low'


def build_result(*, capture_id: str, created_at: str, inspection_point: str,
                 source: str, backend: str, inference_ms: float,
                 image_width: int, image_height: int,
                 detections: list[Detection],
                 display_names: dict[str, str] | None = None) -> dict:
    """Assemble the canonical inspection result dictionary.
    组装规范化的巡检结果字典。

    Args:
        capture_id: Unique capture identifier.
            唯一抓拍标识。
        created_at: ISO-8601 UTC creation timestamp.
            ISO-8601 UTC 创建时间戳。
        inspection_point: Patrol point identifier; may be empty.
            巡检点标识，可为空。
        source: Trigger source such as manual or patrol.
            触发来源，例如 manual 或 patrol。
        backend: Inference backend name such as rknn or mock.
            推理后端名称，例如 rknn 或 mock。
        inference_ms: End-to-end inference duration in milliseconds.
            端到端推理耗时，单位为毫秒。
        image_width: Source image width in pixels.
            源图像宽度，单位为像素。
        image_height: Source image height in pixels.
            源图像高度，单位为像素。
        detections: Accepted detections in original image coordinates.
            原图坐标系下通过筛选的检测结果。
        display_names: Optional label-to-Chinese-display-name map.
            可选的标签到中文显示名映射。

    Returns:
        A JSON-serialisable result dictionary.
        可序列化为 JSON 的结果字典。
    """
    names = display_names or {}
    defects = []
    for detection in detections:
        item = detection.as_dict()
        item['display_name'] = names.get(detection.label, detection.label)
        defects.append(item)
    highest = max((float(item.confidence) for item in detections), default=0.0)
    return {
        'capture_id': capture_id,
        'created_at': created_at,
        'inspection_point': inspection_point,
        'source': source,
        'backend': backend,
        'inference_ms': round(float(inference_ms), 2),
        'image': {'width': int(image_width), 'height': int(image_height)},
        'defects': defects,
        'summary': {
            'defect_count': len(defects),
            'severity': severity_for(detections),
            'highest_confidence': round(highest, 4),
        },
    }

"""Unit tests for structured result assembly and severity mapping.
结构化结果组装与严重程度映射的单元测试。
"""

from iir_vision_rknn.postprocess import Detection
from iir_vision_rknn.result import build_result, severity_for


def _detection(confidence: float, label: str = 'rust') -> Detection:
    """Create a compact detection fixture.
    创建紧凑的检测结果测试夹具。
    """
    return Detection(label=label, confidence=confidence,
                     x_min=10.0, y_min=20.0, x_max=30.0, y_max=40.0)


def test_severity_thresholds():
    """Map confidence bands to the documented severity values.
    将置信度区间映射为约定的严重程度值。
    """
    assert severity_for([]) == 'none'
    assert severity_for([_detection(0.50)]) == 'low'
    assert severity_for([_detection(0.70)]) == 'medium'
    assert severity_for([_detection(0.90)]) == 'high'


def test_build_result_carries_display_names_and_summary():
    """Include Chinese display names, boxes, and aggregate summary.
    包含中文显示名、检测框与聚合摘要。
    """
    result = build_result(
        capture_id='cap-001',
        created_at='2026-11-26T08:00:00.000Z',
        inspection_point='A-01',
        source='manual',
        backend='mock',
        inference_ms=12.345,
        image_width=640,
        image_height=480,
        detections=[_detection(0.91, 'insulator_defect')],
        display_names={'insulator_defect': '绝缘子破损'},
    )
    assert result['backend'] == 'mock'
    assert result['inference_ms'] == 12.35
    assert result['defects'][0]['display_name'] == '绝缘子破损'
    assert result['defects'][0]['bbox'] == [10.0, 20.0, 30.0, 40.0]
    assert result['summary'] == {
        'defect_count': 1,
        'severity': 'high',
        'highest_confidence': 0.91,
    }


def test_build_result_empty_detections_is_normal():
    """Represent a clean capture as severity none with zero defects.
    将无缺陷抓拍表示为 severity=none 且缺陷数为零。
    """
    result = build_result(
        capture_id='cap-002', created_at='2026-11-26T08:00:00.000Z',
        inspection_point='', source='patrol', backend='rknn', inference_ms=8.0,
        image_width=1280, image_height=720, detections=[],
    )
    assert result['summary']['severity'] == 'none'
    assert result['summary']['defect_count'] == 0

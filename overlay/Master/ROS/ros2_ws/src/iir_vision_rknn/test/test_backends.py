"""Unit tests for inference backend selection and mock behaviour.
推理后端选择与 mock 行为的单元测试。
"""

import numpy as np

from iir_vision_rknn.backends import MockBackend, build_backend, load_labels


def test_mock_backend_scales_detections_to_frame():
    """Scale deterministic mock boxes to the supplied frame size.
    将确定性 mock 检测框按给定画面尺寸缩放。
    """
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = MockBackend(['insulator_defect', 'rust']).infer(image)
    assert len(detections) == 2
    assert detections[0].label == 'insulator_defect'
    assert 0.0 < detections[0].x_min < detections[0].x_max < 640.0
    assert 0.0 < detections[0].y_min < detections[0].y_max < 480.0


def test_load_labels_skips_comments_and_blank_lines(tmp_path):
    """Parse bilingual label rows while ignoring comments.
    解析双语标签行并忽略注释。
    """
    path = tmp_path / 'labels.txt'
    path.write_text(
        '# comment\n\ninsulator_defect,绝缘子破损\nrust,金具锈蚀\n',
        encoding='utf-8')
    labels, display = load_labels(str(path))
    assert labels == ['insulator_defect', 'rust']
    assert display['rust'] == '金具锈蚀'


def test_auto_backend_without_model_falls_back_to_mock():
    """Use the mock backend when no RKNN model is configured.
    未配置 RKNN 模型时使用 mock 后端。
    """
    backend = build_backend(kind='auto', model_file='', labels=['rust'])
    assert backend.name == 'mock'


def test_unknown_backend_kind_is_rejected():
    """Reject unsupported backend names instead of guessing.
    拒绝不支持的 backend 名称而不是自行猜测。
    """
    try:
        build_backend(kind='magic', model_file='', labels=['rust'])
    except ValueError as exc:
        assert 'magic' in str(exc)
    else:
        raise AssertionError('expected ValueError')

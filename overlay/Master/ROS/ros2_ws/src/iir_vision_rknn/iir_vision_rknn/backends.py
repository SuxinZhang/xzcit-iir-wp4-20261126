"""Inference backend abstractions for the RKNN inspection node.
RKNN 巡检节点的推理后端抽象。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .postprocess import Detection, decode_yolov8

# Built-in fallback labels keep the mock backend usable without a label file.
# 内置回退标签确保无标签文件时 mock 后端仍可使用。
DEFAULT_LABELS = (
    'insulator_defect',
    'rust',
    'oil_leak',
    'broken_wire',
    'foreign_object',
)


def load_labels(path: str) -> tuple[list[str], dict[str, str]]:
    """Load the bilingual label table from a comma-separated text file.
    从逗号分隔的文本文件加载双语标签表。

    Args:
        path: Absolute or relative path of the label table.
            标签表的绝对或相对路径。

    Returns:
        A tuple of (label key list, key-to-Chinese-display-name map).
        (标签键列表, 键到中文显示名的映射) 元组。
    """
    labels: list[str] = []
    display_names: dict[str, str] = {}
    with Path(path).expanduser().open(encoding='utf-8') as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            key, _, display = line.partition(',')
            key = key.strip()
            if not key:
                continue
            labels.append(key)
            display_names[key] = display.strip() or key
    if not labels:
        raise ValueError(f'No labels found in {path!r}')
    return labels, display_names


class MockBackend:
    """Deterministic synthetic backend for end-to-end demos and offline tests.
    用于端到端演示与离线测试的确定性合成后端。
    """

    name = 'mock'

    def __init__(self, labels=None):
        self.labels = list(labels or DEFAULT_LABELS)

    def infer(self, image) -> list[Detection]:
        """Return two stable plausible detections scaled to the frame.
        返回两个随画面尺寸缩放的稳定合理检测框。
        """
        if image is None or getattr(image, 'ndim', 0) != 3:
            return []
        height, width = int(image.shape[0]), int(image.shape[1])
        if height <= 0 or width <= 0:
            return []
        primary = self.labels[0] if self.labels else 'test_defect'
        secondary = self.labels[1] if len(self.labels) > 1 else 'test_defect'
        return [
            Detection(
                label=primary,
                confidence=0.91,
                x_min=0.18 * width,
                y_min=0.22 * height,
                x_max=0.42 * width,
                y_max=0.58 * height,
            ),
            Detection(
                label=secondary,
                confidence=0.72,
                x_min=0.58 * width,
                y_min=0.30 * height,
                x_max=0.80 * width,
                y_max=0.52 * height,
            ),
        ]

    def release(self) -> None:
        """Release backend resources; the mock backend holds none.
        释放后端资源；mock 后端不持有资源。
        """


class RknnBackend:
    """RK3588S NPU backend backed by rknn-toolkit-lite2.
    基于 rknn-toolkit-lite2 的 RK3588S NPU 后端。
    """

    name = 'rknn'

    def __init__(self, model_file: str, labels, input_size: int = 640,
                 conf_threshold: float = 0.25, nms_iou: float = 0.45):
        # Import lazily so development hosts without the NPU runtime can still
        # exercise the mock backend and pure logic tests.
        # 延迟导入，使没有 NPU 运行时的开发主机仍可使用 mock 后端并运行纯逻辑测试。
        try:
            from rknnlite.api import RKNNLite
        except ImportError as exc:
            raise RuntimeError(
                'rknn-toolkit-lite2 is required for the RKNN backend') from exc

        self.labels = list(labels)
        self.input_size = int(input_size)
        self.conf_threshold = float(conf_threshold)
        self.nms_iou = float(nms_iou)
        self._runtime = RKNNLite()
        status = self._runtime.load_rknn(str(Path(model_file).expanduser()))
        if status != 0:
            self._runtime.release()
            raise RuntimeError(f'RKNN model load failed: {status}')
        status = self._runtime.init_runtime()
        if status != 0:
            self._runtime.release()
            raise RuntimeError(f'RKNN runtime initialization failed: {status}')

    def infer(self, image) -> list[Detection]:
        """Run NPU inference and decode boxes into original image coordinates.
        执行 NPU 推理并将检测框解码到原图坐标系。
        """
        from .preprocess import letterbox

        prepared, scale, pad_x, pad_y = letterbox(image, self.input_size)
        outputs = self._runtime.inference(inputs=[np.expand_dims(prepared, axis=0)])
        if outputs is None:
            raise RuntimeError('RKNN inference returned no outputs')
        height, width = image.shape[:2]
        return decode_yolov8(
            outputs,
            self.labels,
            original_width=int(width),
            original_height=int(height),
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
            conf_threshold=self.conf_threshold,
            nms_iou=self.nms_iou,
            input_size=self.input_size,
        )

    def release(self) -> None:
        """Release the RKNN runtime.
        释放 RKNN 运行时。
        """
        self._runtime.release()


def build_backend(kind: str = 'auto', model_file: str = '', labels=None,
                  input_size: int = 640, conf_threshold: float = 0.25,
                  nms_iou: float = 0.45, logger=None):
    """Build the requested backend with a safe mock fallback in auto mode.
    按请求构建后端；auto 模式下安全回退到 mock。
    """
    resolved = (kind or 'auto').strip().lower()
    label_list = list(labels or DEFAULT_LABELS)

    if resolved == 'mock':
        return MockBackend(label_list)
    if resolved == 'rknn':
        return RknnBackend(model_file, label_list, input_size, conf_threshold, nms_iou)
    if resolved != 'auto':
        raise ValueError(f'Unsupported backend kind: {kind!r}')

    candidate = Path(model_file).expanduser() if model_file else None
    if candidate is not None and candidate.is_file():
        try:
            return RknnBackend(str(candidate), label_list, input_size,
                               conf_threshold, nms_iou)
        except Exception as exc:  # Keep the inspection chain alive in demo setups.
            # 在演示环境中保持巡检链路可用。
            if logger is not None:
                logger.warning(f'RKNN backend unavailable ({exc}); falling back to mock')
    elif logger is not None:
        logger.warning('No RKNN model configured; falling back to the mock backend')
    return MockBackend(label_list)

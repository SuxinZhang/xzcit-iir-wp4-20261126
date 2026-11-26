"""Capture backends that bridge the gateway to ROS 2 or synthetic data.
将网关桥接到 ROS 2 或合成数据的抓拍后端。
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Protocol

from .history import CaptureHistory
from .models import CaptureRecord, CaptureRequest, DefectView
from .settings import Settings


class CaptureBackend(Protocol):
    """Minimal backend contract used by the FastAPI routes.
    FastAPI 路由使用的最小后端契约。
    """

    name: str

    def capture(self, request: CaptureRequest) -> CaptureRecord:
        """Execute one capture and return the archived record.
        执行一次抓拍并返回归档记录。
        """

    def health(self) -> dict:
        """Return a health dictionary for /healthz.
        返回供 /healthz 使用的健康信息字典。
        """

    def close(self) -> None:
        """Release backend resources.
        释放后端资源。
        """


def _utc_now_iso() -> str:
    """Return the current UTC time in ISO-8601 milliseconds.
    以 ISO-8601 毫秒精度返回当前 UTC 时间。
    """
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace(
        '+00:00', 'Z')


def _media_url(path_value: str) -> str:
    """Map an absolute capture path to the gateway media URL.
    将抓拍的绝对路径映射为网关媒体 URL。
    """
    if not path_value:
        return ''
    return f'/media/{Path(path_value).name}'


class FakeCaptureBackend:
    """Synthetic backend used for development, CI, and offline demonstrations.
    用于开发、CI 与离线演示的合成后端。
    """

    name = 'fake'

    def __init__(self, settings: Settings, history: CaptureHistory):
        self._settings = settings
        self._history = history

    def _write_svg(self, path: Path, annotated: bool, defects: list[DefectView]) -> None:
        """Write a deterministic SVG preview so no imaging dependency is required.
        写入确定性 SVG 预览，因此无需图像处理依赖。
        """
        rectangles = ''
        if annotated:
            for defect in defects:
                if len(defect.bbox) != 4:
                    continue
                x1, y1, x2, y2 = (float(value) for value in defect.bbox)
                rectangles += (
                    f'<rect x="{x1:.0f}" y="{y1:.0f}" width="{x2 - x1:.0f}" '
                    f'height="{y2 - y1:.0f}" fill="none" stroke="#ff3b30" stroke-width="3"/>'
                    f'<text x="{x1:.0f}" y="{max(14.0, y1 - 6):.0f}" fill="#ff3b30" '
                    f'font-size="14" font-family="sans-serif">'
                    f'{escape(defect.display_name or defect.label)} {defect.confidence:.2f}</text>')
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" '
            'viewBox="0 0 640 480">'
            '<rect width="640" height="480" fill="#101820"/>'
            '<rect x="20" y="20" width="600" height="440" fill="#1b2a3a" stroke="#3c5a78"/>'
            '<text x="30" y="48" fill="#e6edf3" font-size="18" font-family="sans-serif">'
            'XZCIT-IIR synthetic inspection frame</text>'
            '<text x="30" y="70" fill="#8fa8c0" font-size="13" font-family="sans-serif">'
            'XZCIT-IIR 合成巡检画面</text>'
            f'{rectangles}'
            '</svg>'
        )
        path.write_text(svg, encoding='utf-8')

    def capture(self, request: CaptureRequest) -> CaptureRecord:
        """Generate one synthetic capture and persist its metadata.
        生成一次合成抓拍并持久化其元数据。
        """
        capture_id = (
            'mock-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            + '-' + secrets.token_hex(2))
        defects = [
            DefectView(
                label='insulator_defect', display_name='绝缘子破损', confidence=0.91,
                bbox=[115.0, 106.0, 269.0, 278.0], center=[192.0, 192.0]),
            DefectView(
                label='rust', display_name='金具锈蚀', confidence=0.72,
                bbox=[371.0, 144.0, 512.0, 250.0], center=[441.5, 197.0]),
        ]
        image_path = self._settings.media_dir / f'{capture_id}.svg'
        annotated_path = self._settings.media_dir / f'{capture_id}.annotated.svg'
        self._settings.media_dir.mkdir(parents=True, exist_ok=True)
        self._write_svg(image_path, False, defects)
        self._write_svg(annotated_path, True, defects)
        record = CaptureRecord(
            capture_id=capture_id,
            created_at=_utc_now_iso(),
            inspection_point=request.inspection_point,
            source=request.source or 'manual',
            backend=self.name,
            image_url=_media_url(str(image_path)),
            annotated_url=_media_url(str(annotated_path)),
            defects=defects,
            defect_count=len(defects),
            severity='high',
            summary={
                'defect_count': len(defects),
                'severity': 'high',
                'highest_confidence': 0.91,
            },
            inference_ms=12.5,
            image_path=str(image_path.resolve()),
            annotated_path=str(annotated_path.resolve()),
        )
        self._history.append(record)
        return record

    def health(self) -> dict:
        """Report the synthetic backend as ready.
        报告合成后端已就绪。
        """
        return {
            'backend': self.name,
            'ready': True,
            'message': 'Synthetic capture backend active / 合成抓拍后端已启用',
        }

    def close(self) -> None:
        """Release nothing; the synthetic backend holds no resources.
        无需释放；合成后端不持有资源。
        """


class RosCaptureBackend:
    """ROS 2 service client backend for the real RKNN inspection node.
    面向真实 RKNN 巡检节点的 ROS 2 服务客户端后端。
    """

    name = 'ros'

    def __init__(self, settings: Settings, history: CaptureHistory):
        self._settings = settings
        self._history = history
        self._lock = threading.Lock()
        self._node = None
        self._client = None
        self._service_type = None
        self._rclpy = None
        self._owns_context = False
        self._initialise()

    def _initialise(self) -> None:
        """Create the ROS node and service client lazily.
        延迟创建 ROS 节点与服务客户端。
        """
        try:
            import rclpy
            from iir_interfaces.srv import InspectionCapture
        except ImportError as exc:
            raise RuntimeError(
                'ROS 2 and iir_interfaces are required for the ros capture backend') from exc

        self._rclpy = rclpy
        self._service_type = InspectionCapture
        if not rclpy.ok():
            rclpy.init(args=None)
            self._owns_context = True
        self._node = rclpy.create_node('iir_gateway_capture_client')
        self._client = self._node.create_client(
            InspectionCapture, self._settings.capture_service)

    def capture(self, request: CaptureRequest) -> CaptureRecord:
        """Call /inspection/capture and map the response into a record.
        调用 /inspection/capture 并将响应映射为记录。
        """
        with self._lock:
            if not self._client.wait_for_service(
                    timeout_sec=float(self._settings.capture_timeout_s)):
                raise TimeoutError(
                    f'ROS capture service unavailable: {self._settings.capture_service}')
            service_request = self._service_type.Request()
            service_request.inspection_point = request.inspection_point
            service_request.source = request.source or 'manual'
            service_request.archive = bool(request.archive)
            future = self._client.call_async(service_request)
            self._rclpy.spin_until_future_complete(
                self._node, future, timeout_sec=float(self._settings.capture_timeout_s))
            if not future.done():
                raise TimeoutError('ROS capture service timed out')
            response = future.result()
            if response is None:
                raise RuntimeError('ROS capture service returned no response')
            if not response.success:
                raise RuntimeError(response.message or 'ROS capture failed')

            result = {}
            try:
                result = json.loads(response.result_json or '{}')
            except json.JSONDecodeError:
                logging.getLogger(__name__).warning(
                    'Invalid result_json from inspection service; using typed fields')
            defects = [DefectView(**item) for item in result.get('defects', [])]
            summary = dict(result.get('summary', {}))
            record = CaptureRecord(
                capture_id=str(response.capture_id),
                created_at=str(result.get('created_at', _utc_now_iso())),
                inspection_point=str(result.get(
                    'inspection_point', request.inspection_point)),
                source=str(result.get('source', request.source or 'manual')),
                backend=str(result.get('backend', 'rknn')),
                image_url=_media_url(response.image_path),
                annotated_url=_media_url(response.annotated_path),
                defects=defects,
                defect_count=int(summary.get('defect_count', len(defects))),
                severity=str(summary.get('severity', 'none')),
                summary=summary,
                inference_ms=float(result.get('inference_ms', 0.0)),
                image_path=str(response.image_path),
                annotated_path=str(response.annotated_path),
            )
            self._history.append(record)
            return record

    def health(self) -> dict:
        """Report whether the ROS capture service is currently discoverable.
        报告 ROS 抓拍服务当前是否可发现。
        """
        ready = bool(self._client is not None and self._client.service_is_ready())
        return {
            'backend': self.name,
            'ready': ready,
            'service': self._settings.capture_service,
            'message': ('ROS capture service ready / ROS 抓拍服务就绪'
                        if ready else
                        'ROS capture service not ready / ROS 抓拍服务未就绪'),
        }

    def close(self) -> None:
        """Destroy the ROS node and optionally shut down the context.
        销毁 ROS 节点并按需关闭上下文。
        """
        if self._node is not None:
            self._node.destroy_node()
            self._node = None
        if self._owns_context and self._rclpy is not None and self._rclpy.ok():
            self._rclpy.shutdown()


def build_backend(settings: Settings, history: CaptureHistory) -> CaptureBackend:
    """Build the configured backend, falling back to synthetic data in auto mode.
    构建配置指定的后端；auto 模式下回退到合成数据。
    """
    kind = (settings.backend or 'auto').strip().lower()
    if kind == 'fake':
        return FakeCaptureBackend(settings, history)
    if kind == 'ros':
        return RosCaptureBackend(settings, history)
    if kind != 'auto':
        raise ValueError(f'Unsupported gateway backend: {settings.backend!r}')
    try:
        return RosCaptureBackend(settings, history)
    except Exception as exc:  # Keep the demo chain alive when ROS is absent.
        # ROS 缺失时保持演示链路可用。
        logging.getLogger(__name__).warning(
            'ROS capture backend unavailable (%s); using synthetic captures', exc)
        return FakeCaptureBackend(settings, history)

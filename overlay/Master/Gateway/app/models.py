"""Pydantic payloads shared by the gateway REST and WebSocket endpoints.
网关 REST 与 WebSocket 端点共享的 Pydantic 载荷。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DefectView(BaseModel):
    """One defect rendered in the management and student interfaces.
    管理端与学生端界面渲染的单个缺陷。
    """

    label: str = Field(description='Stable English label key. / 稳定英文标签键。')
    display_name: str | None = Field(
        default=None, description='Chinese display name. / 中文显示名。')
    confidence: float = Field(description='Confidence in [0, 1]. / 取值 [0, 1] 的置信度。')
    bbox: list[float] = Field(
        default_factory=list,
        description='Bounding box as [x1, y1, x2, y2] in pixels. / 像素坐标检测框 [x1, y1, x2, y2]。')
    center: list[float] | None = Field(
        default=None, description='Bounding box centre in pixels. / 检测框中心像素坐标。')


class CaptureRequest(BaseModel):
    """Request body for one inspection capture.
    单次巡检抓拍的请求体。
    """

    inspection_point: str = Field(
        default='', description='Patrol point identifier. / 巡检点标识。')
    source: str = Field(
        default='manual', description='Trigger source: manual or patrol. / 触发来源：manual 或 patrol。')
    archive: bool = Field(
        default=True, description='Persist images and JSON when true. / 为 true 时持久化图像与 JSON。')


class CaptureRecord(BaseModel):
    """One archived inspection capture returned to web clients.
    返回给 Web 客户端的一次已归档巡检抓拍。
    """

    capture_id: str
    created_at: str
    inspection_point: str = ''
    source: str = 'manual'
    backend: str = 'unknown'
    image_url: str = ''
    annotated_url: str = ''
    defects: list[DefectView] = Field(default_factory=list)
    defect_count: int = 0
    severity: str = 'none'
    summary: dict = Field(default_factory=dict)
    inference_ms: float | None = None
    image_path: str = ''
    annotated_path: str = ''


class HistoryPage(BaseModel):
    """Paginated history response for the management console.
    管理控制台使用的历史分页响应。
    """

    items: list[dict] = Field(default_factory=list)
    count: int = 0

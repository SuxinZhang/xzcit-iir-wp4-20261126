"""Runtime settings for the inspection gateway.
巡检业务网关的运行时配置。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    """Gateway configuration resolved from environment variables.
    由环境变量解析得到的网关配置。
    """

    # Capture backend: auto, ros, or fake.
    # 抓拍后端：auto、ros 或 fake。
    backend: str = 'auto'
    # Directory that stores SVG/JPEG artefacts served through /media. It must
    # match the inspection node capture_dir so archived images remain reachable.
    # 通过 /media 提供 SVG/JPEG 产物的存储目录，必须与巡检节点 capture_dir 一致，
    # 以保证归档图像可访问。
    media_dir: Path = Path('~/.cache/iir/captures').expanduser()
    # JSONL history file; None resolves to <media_dir>/history.jsonl.
    # JSONL 历史文件；None 表示 <media_dir>/history.jsonl。
    history_file: Path | None = None
    # ROS 2 service provided by iir_vision_rknn.
    # 由 iir_vision_rknn 提供的 ROS 2 服务。
    capture_service: str = '/inspection/capture'
    # Maximum wait for the ROS capture service to answer.
    # 等待 ROS 抓拍服务响应的最长时间。
    capture_timeout_s: float = 8.0
    # Browser origins allowed to call the REST API.
    # 允许调用 REST API 的浏览器来源。
    allow_origins: tuple[str, ...] = ('*',)
    # HTTP bind address and port.
    # HTTP 绑定地址与端口。
    host: str = '0.0.0.0'
    port: int = 8089
    # Maximum number of records kept in memory for fast history queries.
    # 为快速历史查询保留在内存中的最大记录数。
    max_history: int = 500

    def __post_init__(self):
        """Resolve the default history path after construction.
        构造完成后解析默认历史路径。
        """
        self.media_dir = Path(self.media_dir).expanduser()
        if self.history_file is None:
            self.history_file = self.media_dir / 'history.jsonl'
        else:
            self.history_file = Path(self.history_file).expanduser()

    @classmethod
    def from_env(cls) -> 'Settings':
        """Build settings from OPI_GATEWAY_* environment variables.
        从 OPI_GATEWAY_* 环境变量构建配置。
        """
        media_dir = Path(os.environ.get(
            'OPI_GATEWAY_MEDIA_DIR', '~/.cache/iir/captures')).expanduser()
        history_value = os.environ.get('OPI_GATEWAY_HISTORY_FILE', '').strip()
        origins_value = os.environ.get('OPI_GATEWAY_ALLOW_ORIGINS', '*')
        origins = tuple(
            item.strip() for item in origins_value.split(',') if item.strip())
        return cls(
            backend=os.environ.get('OPI_GATEWAY_BACKEND', 'auto').strip().lower(),
            media_dir=media_dir,
            history_file=Path(history_value).expanduser() if history_value else None,
            capture_service=os.environ.get(
                'OPI_GATEWAY_CAPTURE_SERVICE', '/inspection/capture'),
            capture_timeout_s=float(os.environ.get(
                'OPI_GATEWAY_CAPTURE_TIMEOUT_S', '8.0')),
            allow_origins=origins or ('*',),
            host=os.environ.get('OPI_GATEWAY_HOST', '0.0.0.0'),
            port=int(os.environ.get('OPI_GATEWAY_PORT', '8089')),
            max_history=int(os.environ.get('OPI_GATEWAY_MAX_HISTORY', '500')),
        )

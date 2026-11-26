"""Run the inspection gateway with uvicorn.
使用 uvicorn 运行巡检业务网关。
"""

from __future__ import annotations

import uvicorn

from .main import create_app
from .settings import Settings


def main() -> None:
    """Load environment settings and start the HTTP server.
    加载环境配置并启动 HTTP 服务器。
    """
    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level='info')


if __name__ == '__main__':
    main()

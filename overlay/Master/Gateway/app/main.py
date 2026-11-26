"""FastAPI application for the XZCIT-IIR inspection gateway.
XZCIT-IIR 巡检业务网关的 FastAPI 应用。
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .backends import build_backend
from .history import CaptureHistory
from .models import CaptureRecord, CaptureRequest, HistoryPage
from .settings import Settings

_MEDIA_TYPES = {
    '.svg': 'image/svg+xml',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.json': 'application/json',
}


class ConnectionManager:
    """Track live inspection WebSocket clients and fan out alerts.
    跟踪在线巡检 WebSocket 客户端并广播告警。
    """

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register one browser connection.
        接受并登记一个浏览器连接。
        """
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove one browser connection if still registered.
        移除仍已登记的浏览器连接。
        """
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        """Send one JSON payload to every live client.
        向所有在线客户端发送一条 JSON 载荷。
        """
        text = json.dumps(payload, ensure_ascii=False)
        async with self._lock:
            targets = list(self._connections)
        for websocket in targets:
            try:
                await websocket.send_text(text)
            except Exception:
                # Drop broken clients instead of failing the capture request.
                # 丢弃断开的客户端，避免拖垮抓拍请求。
                await self.disconnect(websocket)


def create_app(settings: Settings | None = None, backend_factory=None) -> FastAPI:
    """Create the gateway application with injectable settings and backend.
    使用可注入的配置与后端创建网关应用。
    """
    resolved = settings or Settings.from_env()
    resolved.media_dir.mkdir(parents=True, exist_ok=True)
    history = CaptureHistory(resolved.history_file, resolved.max_history)
    factory = backend_factory or build_backend
    capture_backend = factory(resolved, history)
    manager = ConnectionManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Release backend resources when the server shuts down.
        服务器关闭时释放后端资源。
        """
        yield
        capture_backend.close()

    app = FastAPI(
        title='XZCIT-IIR Inspection Gateway',
        version='0.1.0',
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.allow_origins),
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.get('/healthz')
    async def healthz():
        """Report gateway and capture-backend health.
        报告网关与抓拍后端健康状态。
        """
        backend_health = await run_in_threadpool(capture_backend.health)
        return {
            'status': 'ok',
            'gateway': 'iir-inspection-gateway',
            'backend': backend_health,
            'history_count': history.count(),
        }

    @app.post('/api/inspection/capture', response_model=CaptureRecord)
    async def capture(request: CaptureRequest):
        """Trigger one inspection capture and broadcast the resulting alert.
        触发一次巡检抓拍并广播产生的告警。
        """
        try:
            record = await run_in_threadpool(capture_backend.capture, request)
        except Exception as exc:
            logging.getLogger(__name__).error('Inspection capture failed: %s', exc)
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        await manager.broadcast({
            't': 'inspection_alert',
            'record': record.model_dump(),
        })
        return record

    @app.get('/api/inspection/history', response_model=HistoryPage)
    async def history_page(limit: int = 20):
        """Return the newest capture records in reverse chronological order.
        按时间倒序返回最新抓拍记录。
        """
        bounded = max(1, min(int(limit), 200))
        items = await run_in_threadpool(history.recent, bounded)
        return HistoryPage(items=items, count=len(items))

    @app.get('/api/inspection/latest')
    async def latest():
        """Return the newest capture record, or an empty object when none exist.
        返回最新抓拍记录；不存在时返回空对象。
        """
        items = await run_in_threadpool(history.recent, 1)
        return items[0] if items else {}

    @app.get('/api/inspection/{capture_id}')
    async def capture_detail(capture_id: str):
        """Return one capture record by identifier.
        按标识返回一条抓拍记录。
        """
        item = await run_in_threadpool(history.get, capture_id)
        if item is None:
            raise HTTPException(status_code=404, detail='capture not found')
        return item

    @app.get('/media/{filename}')
    async def media(filename: str):
        """Serve archived SVG/JPEG artefacts without allowing path traversal.
        提供归档的 SVG/JPEG 产物，并阻止路径穿越。
        """
        if Path(filename).name != filename or filename.startswith('.'):
            raise HTTPException(status_code=404, detail='not found')
        path = resolved.media_dir / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail='not found')
        return FileResponse(
            path, media_type=_MEDIA_TYPES.get(path.suffix.lower(), 'application/octet-stream'))

    @app.websocket('/ws/inspection')
    async def inspection_socket(websocket: WebSocket):
        """Push snapshots on connect and alerts after every capture.
        连接时推送快照，每次抓拍后推送告警。
        """
        await manager.connect(websocket)
        try:
            items = await run_in_threadpool(history.recent, 1)
            await websocket.send_json({'t': 'inspection_snapshot', 'items': items})
            while True:
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=20.0)
                except asyncio.TimeoutError:
                    await websocket.send_json({'t': 'ping'})
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(websocket)

    return app

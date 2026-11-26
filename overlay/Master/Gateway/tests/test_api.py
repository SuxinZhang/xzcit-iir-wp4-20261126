"""End-to-end tests for the FastAPI inspection gateway using synthetic captures.
使用合成抓拍验证 FastAPI 巡检业务网关的端到端测试。
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backends import FakeCaptureBackend
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def client(tmp_path):
    """Create a TestClient backed by the synthetic capture backend.
    创建由合成抓拍后端支撑的 TestClient。
    """
    settings = Settings(
        backend='fake',
        media_dir=tmp_path / 'media',
        history_file=tmp_path / 'history.jsonl',
    )
    app = create_app(settings, backend_factory=lambda s, h: FakeCaptureBackend(s, h))
    with TestClient(app) as test_client:
        yield test_client


def test_capture_persists_record_and_serves_media(client):
    """Capture, fetch media, latest, history, and detail endpoints.
    验证抓拍、媒体访问、最新记录、历史与详情端点。
    """
    response = client.post('/api/inspection/capture', json={
        'inspection_point': 'A-01', 'source': 'manual', 'archive': True,
    })
    assert response.status_code == 200
    record = response.json()
    assert record['defect_count'] == 2
    assert record['severity'] == 'high'
    assert record['inspection_point'] == 'A-01'
    assert record['annotated_url'].startswith('/media/')

    media = client.get(record['annotated_url'])
    assert media.status_code == 200
    assert b'<svg' in media.content

    latest = client.get('/api/inspection/latest').json()
    assert latest['capture_id'] == record['capture_id']

    history = client.get('/api/inspection/history?limit=10').json()
    assert history['count'] == 1
    assert history['items'][0]['capture_id'] == record['capture_id']

    detail = client.get(f"/api/inspection/{record['capture_id']}")
    assert detail.status_code == 200
    assert detail.json()['capture_id'] == record['capture_id']


def test_missing_capture_and_media_return_404(client):
    """Reject missing records and unsafe media names.
    拒绝不存在的记录与不安全的媒体名称。
    """
    assert client.get('/api/inspection/no-such-capture').status_code == 404
    assert client.get('/media/not-exist.svg').status_code == 404
    assert client.get('/media/..%2Fsecret').status_code == 404


def test_health_reports_synthetic_backend(client):
    """Expose backend readiness through the health endpoint.
    通过健康端点暴露后端就绪状态。
    """
    payload = client.get('/healthz').json()
    assert payload['status'] == 'ok'
    assert payload['backend']['backend'] == 'fake'
    assert payload['backend']['ready'] is True


def test_websocket_receives_snapshot_and_alert(client):
    """Receive the initial snapshot and a live alert after a capture.
    接收初始快照以及抓拍后的实时告警。
    """
    with client.websocket_connect('/ws/inspection') as websocket:
        snapshot = websocket.receive_json()
        assert snapshot['t'] == 'inspection_snapshot'
        response = client.post('/api/inspection/capture', json={
            'inspection_point': 'B-02', 'source': 'manual',
        })
        assert response.status_code == 200
        alert = websocket.receive_json()
        assert alert['t'] == 'inspection_alert'
        assert alert['record']['inspection_point'] == 'B-02'

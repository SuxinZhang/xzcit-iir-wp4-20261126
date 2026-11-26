"""Unit tests for the JSONL capture history.
JSONL 抓拍历史的单元测试。
"""

import json
from pathlib import Path

from app.history import CaptureHistory


def test_append_and_recent_returns_newest_first(tmp_path):
    """Return newest records first while persisting every append.
    按最新优先返回记录，并持久化每次追加。
    """
    history = CaptureHistory(tmp_path / 'history.jsonl', max_memory=2)
    history.append({'capture_id': 'one'})
    history.append({'capture_id': 'two'})
    history.append({'capture_id': 'three'})
    assert [item['capture_id'] for item in history.recent(10)] == ['three', 'two']
    assert history.get('two') == {'capture_id': 'two'}
    assert history.get('missing') is None


def test_history_reloads_persisted_records(tmp_path):
    """Reload records from disk on a fresh instance.
    在全新实例上从磁盘重新加载记录。
    """
    path = tmp_path / 'history.jsonl'
    CaptureHistory(path).append({'capture_id': 'persisted'})
    reloaded = CaptureHistory(path)
    assert reloaded.count() == 1
    assert reloaded.recent(1)[0]['capture_id'] == 'persisted'


def test_history_tolerates_corrupt_lines(tmp_path):
    """Skip truncated JSON lines instead of failing startup.
    跳过截断的 JSON 行，而不是让启动失败。
    """
    path = tmp_path / 'history.jsonl'
    path.write_text(
        json.dumps({'capture_id': 'good'}) + '\n{broken\n',
        encoding='utf-8')
    history = CaptureHistory(path)
    assert history.count() == 1
    assert history.recent(1)[0]['capture_id'] == 'good'

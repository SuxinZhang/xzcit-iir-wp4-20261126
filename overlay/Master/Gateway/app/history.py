"""Thread-safe JSONL history for archived inspection captures.
已归档巡检抓拍的线程安全 JSONL 历史存储。
"""

from __future__ import annotations

import json
import threading
from pathlib import Path


class CaptureHistory:
    """Append-only JSONL store with a bounded in-memory recent window.
    带有限内存近期窗口的只追加 JSONL 存储。
    """

    def __init__(self, path: str | Path, max_memory: int = 500):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._max_memory = max(1, int(max_memory))
        self._items: list[dict] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """Load existing records while tolerating truncated or corrupt lines.
        加载已有记录，同时容忍截断或损坏的行。
        """
        if not self.path.is_file():
            return
        with self.path.open(encoding='utf-8') as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    self._items.append(item)
        self._items = self._items[-self._max_memory:]

    def append(self, record) -> dict:
        """Persist one record and return its dictionary form.
        持久化一条记录并返回其字典形式。
        """
        item = record if isinstance(record, dict) else record.model_dump()
        payload = json.dumps(item, ensure_ascii=False)
        with self._lock:
            self._items.append(item)
            if len(self._items) > self._max_memory:
                self._items = self._items[-self._max_memory:]
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(payload + '\n')
        return item

    def recent(self, limit: int = 20) -> list[dict]:
        """Return the newest records in reverse chronological order.
        按时间倒序返回最新记录。
        """
        count = max(0, int(limit))
        with self._lock:
            items = list(self._items)
        if count == 0:
            return []
        return list(reversed(items[-count:]))

    def get(self, capture_id: str) -> dict | None:
        """Return one record by identifier, or None when absent.
        按标识返回一条记录，不存在时返回 None。
        """
        with self._lock:
            for item in reversed(self._items):
                if item.get('capture_id') == capture_id:
                    return dict(item)
        return None

    def count(self) -> int:
        """Return the number of in-memory records.
        返回内存中的记录数量。
        """
        with self._lock:
            return len(self._items)

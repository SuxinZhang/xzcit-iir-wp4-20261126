"""Capture archive writer for inspection images and structured JSON.
巡检图像与结构化 JSON 的抓拍归档写入器。
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

# Capture identifiers are restricted to a filesystem-safe character set.
# 抓拍标识限制为文件系统安全的字符集。
_SAFE_CAPTURE_ID = re.compile(r'^[A-Za-z0-9_.-]{1,96}$')


def new_capture_id(now: float | None = None) -> str:
    """Create a sortable, collision-resistant UTC capture identifier.
    创建可按时间排序且防碰撞的 UTC 抓拍标识。
    """
    moment = datetime.fromtimestamp(time.time() if now is None else float(now),
                                    tz=timezone.utc)
    suffix = secrets.token_hex(3)
    return f'{moment.strftime("%Y%m%dT%H%M%S_%fZ")}-{suffix}'


def utc_now_iso() -> str:
    """Return the current UTC time in ISO-8601 milliseconds.
    以 ISO-8601 毫秒精度返回当前 UTC 时间。
    """
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace(
        '+00:00', 'Z')


class CaptureArchive:
    """Persist original images, annotated images, and result JSON under one root.
    在同一根目录下持久化原图、标注图与结果 JSON。
    """

    def __init__(self, root: str):
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, capture_id: str, suffix: str) -> Path:
        if not _SAFE_CAPTURE_ID.match(capture_id):
            raise ValueError(f'Unsafe capture id: {capture_id!r}')
        return self.root / f'{capture_id}{suffix}'

    @staticmethod
    def _write_atomic(path: Path, data: bytes) -> None:
        """Write bytes through a temporary file and atomically replace the target.
        通过临时文件写入字节，并原子替换目标文件。
        """
        temporary = path.with_name(path.name + '.tmp')
        temporary.write_bytes(data)
        os.replace(temporary, path)

    def save(self, capture_id: str, image_bytes: bytes | None = None,
             annotated_bytes: bytes | None = None, result: dict | None = None) -> dict:
        """Archive the supplied artefacts and return their absolute paths.
        归档给定产物并返回其绝对路径。
        """
        paths = {'image_path': '', 'annotated_path': '', 'result_path': ''}
        if image_bytes is not None:
            path = self._path(capture_id, '.jpg')
            self._write_atomic(path, image_bytes)
            paths['image_path'] = str(path.resolve())
        if annotated_bytes is not None:
            path = self._path(capture_id, '.annotated.jpg')
            self._write_atomic(path, annotated_bytes)
            paths['annotated_path'] = str(path.resolve())
        if result is not None:
            path = self._path(capture_id, '.json')
            payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
            self._write_atomic(path, payload.encode('utf-8'))
            paths['result_path'] = str(path.resolve())
        return paths

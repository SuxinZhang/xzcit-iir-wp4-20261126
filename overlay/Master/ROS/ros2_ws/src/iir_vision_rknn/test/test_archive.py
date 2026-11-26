"""Unit tests for capture archive persistence.
抓拍归档持久化的单元测试。
"""

import json
from pathlib import Path

import pytest

from iir_vision_rknn.archive import CaptureArchive, new_capture_id


def test_new_capture_id_is_sortable_and_filesystem_safe():
    """Generate distinct identifiers that only use safe characters.
    生成仅使用安全字符且互不相同的标识。
    """
    first = new_capture_id(1700000000.0)
    second = new_capture_id(1700000000.0)
    assert first != second
    assert ':' not in first
    assert '/' not in first


def test_archive_writes_original_annotated_and_json(tmp_path):
    """Persist all three artefacts and expose absolute paths.
    持久化全部三类产物并返回绝对路径。
    """
    archive = CaptureArchive(str(tmp_path))
    paths = archive.save(
        'cap-001', b'original-jpeg', b'annotated-jpeg', {'defects': []})
    assert Path(paths['image_path']).read_bytes() == b'original-jpeg'
    assert Path(paths['annotated_path']).read_bytes() == b'annotated-jpeg'
    payload = json.loads(Path(paths['result_path']).read_text(encoding='utf-8'))
    assert payload == {'defects': []}
    assert Path(paths['result_path']).read_text(encoding='utf-8').endswith('\n')


def test_archive_rejects_path_traversal_identifiers(tmp_path):
    """Reject identifiers that could escape the archive root.
    拒绝可能逃逸归档根目录的标识。
    """
    archive = CaptureArchive(str(tmp_path))
    with pytest.raises(ValueError):
        archive.save('../escape', b'x', None, None)
    with pytest.raises(ValueError):
        archive.save('bad/id', b'x', None, None)

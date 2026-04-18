import sqlite3
import subprocess
from pathlib import Path

from wiz_export import WizExporter, Logger


class DummyLogger:
    def info(self, msg):
        pass

    def error(self, msg):
        pass

    def warning(self, msg):
        pass

    def debug(self, msg):
        pass

    def exception(self, msg):
        pass


def test_windows_flat_layout_is_detected_without_notes_dir():
    root = Path('/Users/moringchen/workspace/ai/wizexport/windows-data/wiz/Data/moringchen123@sina.com')
    exporter = WizExporter('moringchen123@sina.com', '/', root, DummyLogger())

    assert exporter._uses_flat_document_layout() is True


def test_windows_note_lookup_finds_real_ziw_file():
    root = Path('/Users/moringchen/workspace/ai/wizexport/windows-data/wiz/Data/moringchen123@sina.com')
    exporter = WizExporter('moringchen123@sina.com', '/', root, DummyLogger())

    conn = sqlite3.connect(str(root / 'index.db'))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT DOCUMENT_GUID, DOCUMENT_TITLE, DOCUMENT_LOCATION, DOCUMENT_NAME, DOCUMENT_FILE_TYPE
        FROM WIZ_DOCUMENT
        WHERE DOCUMENT_LOCATION = '/账号/'
        LIMIT 1
        """
    ).fetchone()
    conn.close()

    assert row is not None

    doc = {
        'guid': row['DOCUMENT_GUID'],
        'title': row['DOCUMENT_TITLE'],
        'location': row['DOCUMENT_LOCATION'],
        'name': row['DOCUMENT_NAME'],
        'file_type': row['DOCUMENT_FILE_TYPE'] or 'ziw',
    }

    path = exporter._get_note_file_path(doc)
    assert path is not None, f"expected to find note file for {doc}"
    assert path.exists()
    assert path.suffix == '.ziw'


def test_convert_to_markdown_works_without_pandoc(tmp_path, monkeypatch):
    exporter = WizExporter('moringchen123@sina.com', '/', tmp_path, DummyLogger())
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    exporter.output_dir.mkdir()
    exporter.media_dir.mkdir()

    html_file = tmp_path / 'note.html'
    md_file = exporter.output_dir / 'note.md'
    html_file.write_text('<h1>标题</h1><p>正文 <strong>加粗</strong></p>', encoding='utf-8')

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == 'pandoc':
            raise FileNotFoundError
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', fake_run)

    success = exporter._convert_to_markdown(html_file, md_file, exporter.output_dir)

    assert success is True
    assert md_file.exists()
    content = md_file.read_text(encoding='utf-8')
    assert '标题' in content
    assert '正文' in content
    assert '加粗' in content


def test_convert_to_markdown_without_pandoc_ignores_head_content(tmp_path, monkeypatch):
    exporter = WizExporter('moringchen123@sina.com', '/', tmp_path, DummyLogger())
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    exporter.output_dir.mkdir()
    exporter.media_dir.mkdir()

    html_file = tmp_path / 'note.html'
    md_file = exporter.output_dir / 'note.md'
    html_file.write_text(
        '<html><head><title>页面标题</title><style>.hidden{display:none}</style><script>console.log("noise")</script></head><body><h1>正文标题</h1><p>真正内容</p></body></html>',
        encoding='utf-8'
    )

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == 'pandoc':
            raise FileNotFoundError
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', fake_run)

    success = exporter._convert_to_markdown(html_file, md_file, exporter.output_dir)

    assert success is True
    content = md_file.read_text(encoding='utf-8')
    assert '正文标题' in content
    assert '真正内容' in content
    assert '页面标题' not in content
    assert 'display:none' not in content
    assert 'console.log' not in content

import sqlite3
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

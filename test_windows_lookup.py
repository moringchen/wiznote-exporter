import sqlite3
import subprocess
from pathlib import Path

import pytest

import key_generator_v1_1
import license_manager as license_manager_module
import wiz_export as wiz_export_module
from build import Builder
from license_manager import LicenseManager
from wiz_export import WizExporter, Logger, parse_attachment_mode


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


def get_windows_sample_root() -> Path:
    relative = Path('windows-data/wiz/Data/moringchen123@sina.com')
    current = Path(__file__).resolve().parent

    for base in [current, *current.parents]:
        candidate = base / relative
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f'找不到测试样本目录: {relative}')


def test_windows_flat_layout_is_detected_without_notes_dir():
    root = get_windows_sample_root()
    exporter = WizExporter('moringchen123@sina.com', '/', root, DummyLogger())

    assert exporter._uses_flat_document_layout() is True


def test_windows_note_lookup_finds_real_ziw_file():
    root = get_windows_sample_root()
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


def test_convert_to_markdown_handles_utf16le_encoding(tmp_path, monkeypatch):
    """测试内置转换器能正确处理 UTF-16LE 编码的 HTML"""
    exporter = WizExporter('moringchen123@sina.com', '/', tmp_path, DummyLogger())
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    exporter.output_dir.mkdir()
    exporter.media_dir.mkdir()

    html_file = tmp_path / 'note.html'
    md_file = exporter.output_dir / 'note.md'

    # 写入 UTF-16LE 编码的 HTML（带 BOM）
    html_content = '<h1>UTF16标题</h1><p>UTF16内容</p>'
    html_file.write_bytes(b'\xff\xfe' + html_content.encode('utf-16-le'))

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == 'pandoc':
            raise FileNotFoundError
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', fake_run)

    success = exporter._convert_to_markdown(html_file, md_file, exporter.output_dir)

    assert success is True
    content = md_file.read_text(encoding='utf-8')
    assert 'UTF16标题' in content
    assert 'UTF16内容' in content


def test_machine_code_v1_0_keeps_legacy_format(monkeypatch):
    manager = LicenseManager()
    monkeypatch.setattr(manager, '_get_machine_fingerprint', lambda: 'abcdef0123456789fedcba9876543210')

    machine_code = manager.get_machine_code()

    assert machine_code == 'ABCD-EF01-2345-6789'


def test_machine_code_v1_1_is_stable_within_same_day(monkeypatch):
    manager = LicenseManager()
    monkeypatch.setattr(manager, '_get_machine_fingerprint', lambda: 'abcdef0123456789fedcba9876543210')
    monkeypatch.setattr(manager, '_get_machine_code_date_stamp', lambda now=None: '20260430', raising=False)

    first = manager.get_machine_code_v1_1()
    second = manager.get_machine_code_v1_1()

    assert first == second
    assert first.startswith('V11-')


def test_machine_code_v1_1_changes_across_days(monkeypatch):
    manager = LicenseManager()
    monkeypatch.setattr(manager, '_get_machine_fingerprint', lambda: 'abcdef0123456789fedcba9876543210')

    stamps = iter(['20260430', '20260501'])
    monkeypatch.setattr(manager, '_get_machine_code_date_stamp', lambda now=None: next(stamps), raising=False)

    first = manager.get_machine_code_v1_1()
    second = manager.get_machine_code_v1_1()

    assert first != second


def test_reset_code_v1_1_round_trip(monkeypatch):
    manager = LicenseManager()
    monkeypatch.setattr(manager, 'ensure_private_key', lambda: 'secret-key-for-tests')
    monkeypatch.setattr(manager, '_load_private_key', lambda: 'secret-key-for-tests')

    machine_code = 'V11-AAAA-BBBB-CCCC-DDDD'
    reset_code = manager.generate_reset_code_v1_1(machine_code)

    assert manager.verify_reset_code_v1_1(machine_code, reset_code) is True


def test_reset_code_v1_1_rejects_v1_0_code(monkeypatch):
    manager = LicenseManager()
    monkeypatch.setattr(manager, 'ensure_private_key', lambda: 'secret-key-for-tests')
    monkeypatch.setattr(manager, '_load_private_key', lambda: 'secret-key-for-tests')

    legacy_machine_code = 'AAAA-BBBB-CCCC-DDDD'
    v1_1_reset_code = manager.generate_reset_code_v1_1('V11-AAAA-BBBB-CCCC-DDDD')

    assert manager.verify_reset_code(legacy_machine_code, v1_1_reset_code) is False


def test_reset_with_code_v1_1_uses_v1_1_machine_code(monkeypatch):
    manager = LicenseManager()
    manager.license_data = {'usage_count': 5, 'usage_limit': 0, 'unlocked': False}
    monkeypatch.setattr(manager, 'get_machine_code_v1_1', lambda: 'V11-AAAA-BBBB-CCCC-DDDD', raising=False)
    monkeypatch.setattr(
        manager,
        'verify_reset_code_v1_1',
        lambda machine_code, reset_code: reset_code == 'valid-v11-code',
        raising=False,
    )
    monkeypatch.setattr(manager, 'save_license', lambda: True)

    assert manager.reset_with_code_v1_1('valid-v11-code') is True
    assert manager.license_data['usage_count'] == 0
    assert manager.license_data['usage_limit'] == manager.RESET_LIMIT
    assert manager.license_data['unlocked'] is True


def test_get_machine_code_for_display_uses_requested_version(monkeypatch):
    manager = LicenseManager()
    monkeypatch.setattr(manager, 'get_machine_code', lambda: 'AAAA-BBBB-CCCC-DDDD')
    monkeypatch.setattr(manager, 'get_machine_code_v1_1', lambda: 'V11-AAAA-BBBB-CCCC-DDDD', raising=False)

    assert manager.get_machine_code_for_display('1.0') == 'AAAA-BBBB-CCCC-DDDD'
    assert manager.get_machine_code_for_display('1.1') == 'V11-AAAA-BBBB-CCCC-DDDD'


def test_attachment_mode_shared_media_resolves_to_outer_media(tmp_path):
    exporter = WizExporter('user@example.com', '/', tmp_path, DummyLogger(), attachment_mode='shared')
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    note_dir = exporter.output_dir / '工作'
    note_dir.mkdir(parents=True)

    media_dir = exporter._get_attachment_target_dir(note_dir)

    assert media_dir == exporter.output_dir / 'media' / '工作'


def test_attachment_mode_per_note_resolves_to_note_media(tmp_path):
    exporter = WizExporter('user@example.com', '/', tmp_path, DummyLogger(), attachment_mode='per_note')
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    note_dir = exporter.output_dir / '工作'
    note_dir.mkdir(parents=True)

    media_dir = exporter._get_attachment_target_dir(note_dir)

    assert media_dir == note_dir / 'media'


def test_fix_image_paths_shared_mode_uses_outer_media(tmp_path):
    exporter = WizExporter('user@example.com', '/', tmp_path, DummyLogger(), attachment_mode='shared')
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    note_dir = exporter.output_dir / '工作'
    note_dir.mkdir(parents=True)
    md_file = note_dir / '周报.md'
    md_file.write_text('![图](index_files/a.png)', encoding='utf-8')

    exporter._fix_image_paths(md_file, note_dir)

    assert md_file.read_text(encoding='utf-8') == '![图](../media/工作/a.png)'


def test_fix_image_paths_shared_mode_uses_depth_aware_outer_media(tmp_path):
    exporter = WizExporter('user@example.com', '/', tmp_path, DummyLogger(), attachment_mode='shared')
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    note_dir = exporter.output_dir / 'My Journals' / '2013'
    note_dir.mkdir(parents=True)
    md_file = note_dir / 'note.md'
    md_file.write_text('![图](index_files/a.png)', encoding='utf-8')

    exporter._fix_image_paths(md_file, note_dir)

    assert md_file.read_text(encoding='utf-8') == '![图](../../media/My Journals/2013/a.png)'


def test_fix_image_paths_per_note_mode_uses_local_media(tmp_path):
    exporter = WizExporter('user@example.com', '/', tmp_path, DummyLogger(), attachment_mode='per_note')
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    note_dir = exporter.output_dir / '工作'
    note_dir.mkdir(parents=True)
    md_file = note_dir / '周报.md'
    md_file.write_text('![图](index_files/a.png)', encoding='utf-8')

    exporter._fix_image_paths(md_file, note_dir)

    assert md_file.read_text(encoding='utf-8') == '![图](media/a.png)'


def test_process_attachments_shared_mode_copies_into_outer_media(tmp_path):
    exporter = WizExporter('user@example.com', '/', tmp_path, DummyLogger(), attachment_mode='shared')
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    exporter.output_dir.mkdir()
    exporter.media_dir.mkdir()
    note_dir = exporter.output_dir / '工作'
    note_dir.mkdir()
    index_files_dir = tmp_path / 'index_files'
    index_files_dir.mkdir()
    (index_files_dir / 'a.png').write_text('img', encoding='utf-8')

    exporter._process_attachments(index_files_dir, note_dir, '周报')

    assert (exporter.output_dir / 'media' / '工作' / 'a.png').exists()


def test_process_attachments_per_note_mode_copies_into_note_media(tmp_path):
    exporter = WizExporter('user@example.com', '/', tmp_path, DummyLogger(), attachment_mode='per_note')
    exporter.output_dir = tmp_path / 'wiz'
    exporter.media_dir = exporter.output_dir / 'media'
    exporter.output_dir.mkdir()
    note_dir = exporter.output_dir / '工作'
    note_dir.mkdir(parents=True)
    index_files_dir = tmp_path / 'index_files'
    index_files_dir.mkdir()
    (index_files_dir / 'a.png').write_text('img', encoding='utf-8')

    exporter._process_attachments(index_files_dir, note_dir, '周报')

    assert (note_dir / 'media' / 'a.png').exists()


def test_parse_attachment_mode_defaults_to_shared():
    exporter_mode = parse_attachment_mode('')
    explicit_shared_mode = parse_attachment_mode('1')
    per_note_mode = parse_attachment_mode('2')

    assert exporter_mode == 'shared'
    assert explicit_shared_mode == 'shared'
    assert per_note_mode == 'per_note'


def test_reset_license_accepts_v1_1_code(monkeypatch, capsys):
    monkeypatch.setattr(LicenseManager, 'reset_with_code', lambda self, code: False)
    monkeypatch.setattr(LicenseManager, 'reset_with_code_v1_1', lambda self, code: code == 'valid-v11-code')
    monkeypatch.setattr(license_manager_module, 'show_license_status', lambda: None)

    license_manager_module.reset_license('valid-v11-code')

    output = capsys.readouterr().out
    assert '✓ 重置成功' in output



def test_key_generator_v1_1_rejects_invalid_machine_code(monkeypatch, capsys):
    monkeypatch.setattr(key_generator_v1_1.sys, 'argv', ['key_generator_v1_1.py', 'AAAA-BBBB-CCCC-DDDD'])

    with pytest.raises(SystemExit) as exc_info:
        key_generator_v1_1.main()

    assert exc_info.value.code == 1
    output = capsys.readouterr().out
    assert 'V11-' in output



def test_create_directory_structure_per_note_does_not_create_top_level_media(tmp_path):
    exporter = WizExporter('user@example.com', '/', tmp_path, DummyLogger(), attachment_mode='per_note')
    exporter.output_dir = tmp_path / 'wiz'
    exporter.tmp_dir = tmp_path / 'wiz_tmp'
    exporter.media_dir = exporter.output_dir / 'media'

    exporter.create_directory_structure([{'path': '/', 'name': 'root'}])

    assert exporter.output_dir.exists()
    assert exporter.tmp_dir.exists()
    assert not exporter.media_dir.exists()



def test_builder_macos_launcher_preserves_cwd_and_shows_wait_message():
    launcher = Builder()._get_macos_launcher_content()

    assert '工具启动中，请稍候' in launcher
    assert 'cd "$(dirname "$0")"' not in launcher
    assert 'SCRIPT_DIR=' in launcher
    assert '"$SCRIPT_DIR/WizNote导出工具"' in launcher



def test_discard_pending_stdin_input_flushes_macos_tty():
    class FakeStdin:
        def isatty(self):
            return True

        def fileno(self):
            return 7

    calls = {}

    def fake_tcflush(fd, mode):
        calls['fd'] = fd
        calls['mode'] = mode

    flushed = wiz_export_module.discard_pending_stdin_input(
        platform_name='darwin',
        stdin=FakeStdin(),
        tcflush_fn=fake_tcflush,
        tciflush=123,
    )

    assert flushed is True
    assert calls == {'fd': 7, 'mode': 123}



def test_main_discards_pending_input_before_wiz_home_prompt(monkeypatch):
    events = []

    monkeypatch.setattr(wiz_export_module, 'check_license', lambda: (True, 3))
    monkeypatch.setattr(wiz_export_module, 'get_default_wiz_home', lambda: Path('/tmp/.wiznote'))
    monkeypatch.setattr(wiz_export_module, 'get_default_wiz_home_display', lambda: '~/.wiznote')
    monkeypatch.setattr(wiz_export_module, 'get_os_name', lambda: 'macOS')
    monkeypatch.setattr(wiz_export_module, 'discard_pending_stdin_input', lambda: events.append('discard'))

    class DummyRuntimeLogger:
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

    monkeypatch.setattr(wiz_export_module, 'Logger', lambda log_dir: DummyRuntimeLogger())

    def fake_input(prompt=''):
        events.append(prompt)
        raise KeyboardInterrupt

    monkeypatch.setattr('builtins.input', fake_input)

    wiz_export_module.main()

    assert events[0] == 'discard'
    assert '请输入 WizNote 数据目录' in events[1]

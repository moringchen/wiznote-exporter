#!/usr/bin/env python3
"""
为知笔记(WizNote)导出工具
将 WizNote 笔记导出为 Markdown 格式，便于导入 Obsidian
"""

import os
import sys
import sqlite3
import shutil
import zipfile
import subprocess
import logging
import traceback
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime

# 导入授权管理模块
try:
    from license_manager import LicenseManager
    LICENSE_ENABLED = True
except ImportError:
    LICENSE_ENABLED = False


class Logger:
    """日志管理器"""
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / "wiz_export.log"

        # 配置日志
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(self.log_file, mode='w', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def info(self, msg: str):
        self.logger.info(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def debug(self, msg: str):
        self.logger.debug(msg)

    def exception(self, msg: str):
        self.logger.exception(msg)


class WizExporter:
    def __init__(self, username: str, export_path: str, wiz_home: Path, logger: Logger):
        self.username = username
        self.export_path = export_path
        self.wiz_home = wiz_home
        self.db_path = self.wiz_home / "index.db"
        self.notes_dir = self.wiz_home / "notes"
        self.attachments_dir = self.wiz_home / "attachments"
        self.logger = logger

        # 输出目录
        self.output_dir = Path("wiz")
        self.tmp_dir = Path("wiz_tmp")
        self.media_dir = self.output_dir / "media"

        self.conn: Optional[sqlite3.Connection] = None

    def connect_db(self) -> bool:
        """连接 SQLite 数据库"""
        self.logger.info(f"尝试连接数据库: {self.db_path}")
        if not self.db_path.exists():
            self.logger.error(f"数据库文件不存在: {self.db_path}")
            return False

        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self.logger.info(f"成功连接到数据库: {self.db_path}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"数据库连接错误: {e}")
            return False

    def show_tables(self) -> None:
        """显示数据库中的所有表"""
        if not self.conn:
            return

        cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        self.logger.info(f"数据库中的表: {', '.join(tables)}")

    def get_folders(self, parent_path: str) -> List[Dict]:
        """获取指定路径下的所有子目录"""
        if not self.conn:
            return []

        # 从 DOCUMENT_LOCATION 字段提取目录
        cursor = self.conn.execute(
            "SELECT DISTINCT DOCUMENT_LOCATION FROM WIZ_DOCUMENT WHERE DOCUMENT_LOCATION LIKE ?",
            (f"{parent_path}%",)
        )

        folders = set()
        for row in cursor.fetchall():
            folder_path = row[0]
            if folder_path and folder_path != parent_path and folder_path.startswith(parent_path):
                # 提取直接子目录
                relative = folder_path[len(parent_path):].lstrip('/')
                if relative:
                    parts = relative.split('/')
                    # 构建直接子目录路径
                    subfolder = parent_path.rstrip('/') + '/' + parts[0] if parent_path != '/' else '/' + parts[0]
                    folders.add(subfolder)

        # 转换为列表并获取名称
        result = []
        for folder_path in sorted(folders):
            result.append({
                'path': folder_path,
                'name': os.path.basename(folder_path) or 'root'
            })

        return result

    def get_all_subfolders(self, parent_path: str) -> List[Dict]:
        """递归获取所有子目录"""
        if not self.conn:
            return []

        # 从 DOCUMENT_LOCATION 字段提取所有目录
        cursor = self.conn.execute(
            "SELECT DISTINCT DOCUMENT_LOCATION FROM WIZ_DOCUMENT WHERE DOCUMENT_LOCATION LIKE ?",
            (f"{parent_path}%",)
        )

        folders = set()
        for row in cursor.fetchall():
            folder_path = row[0]
            if not folder_path:
                continue
            # 添加路径本身
            if folder_path != parent_path and folder_path.startswith(parent_path):
                folders.add(folder_path)
            # 添加路径的所有父目录（相对于parent_path）
            relative = folder_path[len(parent_path):].lstrip('/')
            parts = relative.split('/')
            current = parent_path.rstrip('/')
            for i, part in enumerate(parts[:-1]):
                current = current + '/' + part if current else '/' + part
                if current != parent_path:
                    folders.add(current)

        # 转换为列表
        result = []
        for folder_path in sorted(folders):
            result.append({
                'path': folder_path,
                'name': os.path.basename(folder_path) or 'root'
            })

        return result

    def get_documents(self, folder_path: str) -> List[Dict]:
        """获取指定目录下的所有笔记"""
        if not self.conn:
            return []

        cursor = self.conn.execute(
            """SELECT DOCUMENT_GUID, DOCUMENT_TITLE, DOCUMENT_LOCATION,
                      DOCUMENT_NAME, DOCUMENT_FILE_TYPE
               FROM WIZ_DOCUMENT
               WHERE DOCUMENT_LOCATION = ?""",
            (folder_path,)
        )

        documents = []
        for row in cursor.fetchall():
            documents.append({
                'guid': row[0],
                'title': row[1],
                'location': row[2],
                'name': row[3],
                'file_type': row[4] or 'ziw'
            })

        return documents

    def create_directory_structure(self, folders: List[Dict]) -> None:
        """创建目录结构"""
        # 创建基础目录
        self.output_dir.mkdir(exist_ok=True)
        self.tmp_dir.mkdir(exist_ok=True)
        self.media_dir.mkdir(exist_ok=True)

        # 为每个目录创建对应的路径
        for folder in folders:
            relative_path = self._get_relative_path(folder['path'])
            if relative_path:
                (self.output_dir / relative_path).mkdir(parents=True, exist_ok=True)
                (self.tmp_dir / relative_path).mkdir(parents=True, exist_ok=True)

        self.logger.info(f"目录结构创建完成:")
        self.logger.info(f"  - 输出目录: {self.output_dir.absolute()}")
        self.logger.info(f"  - 临时目录: {self.tmp_dir.absolute()}")
        self.logger.info(f"  - 媒体目录: {self.media_dir.absolute()}")

    def _get_relative_path(self, folder_path: str) -> str:
        """获取相对于导出根目录的相对路径"""
        # 规范化路径（去掉末尾的/）
        normalized_folder = folder_path.rstrip('/')
        normalized_export = self.export_path.rstrip('/')

        # 移除开头的 / 来构建相对路径
        export_relative = normalized_export.lstrip('/')

        if normalized_folder == normalized_export:
            # 如果就是导出路径本身，使用完整的相对路径
            return export_relative

        if normalized_folder.startswith(normalized_export + '/'):
            # 子目录：保留完整的相对路径结构
            relative = normalized_folder[len(normalized_export) + 1:]
            return f"{export_relative}/{relative}"

        return ""

    def _get_note_file_path(self, doc: Dict) -> Optional[Path]:
        """获取笔记文件在 notes 目录中的路径"""
        guid = doc['guid']

        # WizNote 笔记文件以 GUID（带花括号）命名，无扩展名
        # 尝试几种格式：带花括号、不带花括号
        possible_names = [
            f"{{{guid}}}",  # {guid} 格式
            guid,           # 纯 guid 格式
        ]

        for name in possible_names:
            path = self.notes_dir / name
            if path.exists():
                return path

        # 如果没找到，尝试搜索
        for path in self.notes_dir.rglob(f"*{guid}*"):
            if path.is_file():
                return path

        return None

    def process_document(self, doc: Dict) -> bool:
        """处理单个笔记文档"""
        guid = doc['guid']
        title = doc['title'] or doc['name'] or "untitled"
        location = doc['location']

        # 清理文件名中的非法字符
        safe_title = self._sanitize_filename(title)

        # 获取相对路径
        relative_dir = self._get_relative_path(location)

        # 确定输出路径
        tmp_output_dir = self.tmp_dir / relative_dir if relative_dir else self.tmp_dir
        final_output_dir = self.output_dir / relative_dir if relative_dir else self.output_dir

        # 获取源文件路径
        source_path = self._get_note_file_path(doc)
        if not source_path:
            self.logger.warning(f"找不到笔记文件: {title} ({guid})")
            return False

        try:
            # 确保输出目录存在
            tmp_output_dir.mkdir(parents=True, exist_ok=True)
            final_output_dir.mkdir(parents=True, exist_ok=True)

            # 复制到临时目录
            tmp_zip_path = tmp_output_dir / f"{safe_title}.zip"
            shutil.copy2(source_path, tmp_zip_path)

            # 解压
            extract_dir = tmp_output_dir / safe_title
            extract_dir.mkdir(exist_ok=True)

            with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # 查找 index.html
            html_file = extract_dir / "index.html"
            if not html_file.exists():
                # 尝试其他可能的 html 文件
                html_files = list(extract_dir.glob("*.html"))
                if html_files:
                    html_file = html_files[0]
                else:
                    self.logger.warning(f"找不到 HTML 文件: {title}")
                    return False

            # 处理附件
            index_files_dir = extract_dir / "index_files"
            if index_files_dir.exists():
                self._process_attachments(index_files_dir, final_output_dir, safe_title)

            # 使用 pandoc 转换为 markdown
            md_file = final_output_dir / f"{safe_title}.md"
            success = self._convert_to_markdown(html_file, md_file, final_output_dir)

            if success:
                self.logger.info(f"✓ {title}")
                return True
            else:
                self.logger.error(f"转换失败: {title}")
                return False

        except Exception as e:
            self.logger.exception(f"处理失败: {title}")
            return False

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip() or "untitled"

    def _process_attachments(self, index_files_dir: Path, output_dir: Path, note_name: str) -> None:
        """处理笔记中的附件和图片，放在wiz/media下与markdown相同的目录结构中"""
        # 计算相对于output_dir的路径，构建到media的相同结构
        try:
            relative_path = output_dir.relative_to(self.output_dir)
        except ValueError:
            relative_path = Path()

        # 在media下创建相同的目录结构
        media_dir = self.media_dir / relative_path
        media_dir.mkdir(parents=True, exist_ok=True)

        for file_path in index_files_dir.iterdir():
            if file_path.is_file():
                # 生成唯一的文件名
                base_name = file_path.name
                dest_path = media_dir / base_name

                # 处理重名
                counter = 1
                while dest_path.exists():
                    stem = Path(base_name).stem
                    suffix = Path(base_name).suffix
                    dest_path = media_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                shutil.copy2(file_path, dest_path)

    def _convert_to_markdown(self, html_file: Path, md_file: Path, output_dir: Path) -> bool:
        """使用 pandoc 将 HTML 转换为 Markdown"""
        try:
            # 检查 pandoc 是否安装
            result = subprocess.run(
                ["pandoc", "--version"],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                self.logger.error("未找到 pandoc，请先安装 pandoc")
                self.logger.info("  macOS: brew install pandoc")
                self.logger.info("  Ubuntu/Debian: sudo apt-get install pandoc")
                self.logger.info("  Windows: choco install pandoc")
                return False

            # 使用 pandoc 转换
            result = subprocess.run(
                [
                    "pandoc",
                    str(html_file),
                    "-f", "html-native_divs-native_spans",
                    "-t", "markdown",
                    "-o", str(md_file),
                    "--wrap=none"
                ],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                # 修复图片路径和格式
                self._fix_image_paths(md_file, output_dir)
                self._clean_markdown_format(md_file)
                return True
            else:
                self.logger.error(f"pandoc 错误: {result.stderr}")
                return False

        except FileNotFoundError:
            self.logger.error("未找到 pandoc，请先安装 pandoc")
            return False
        except Exception as e:
            self.logger.exception("转换错误")
            return False

    def _fix_image_paths(self, md_file: Path, output_dir: Path) -> None:
        """修复 Markdown 中的图片路径为相对路径（指向wiz/media下的相同目录结构）"""
        if not md_file.exists():
            return

        content = md_file.read_text(encoding='utf-8')

        # 计算从markdown所在目录到media目录的相对路径
        try:
            relative_path = output_dir.relative_to(self.output_dir)
        except ValueError:
            relative_path = Path()

        # 构建media的相对路径前缀 (如 ../media/My Journals/2013/2013-02/)
        media_prefix = "../media"
        if relative_path.parts:
            # 需要向上退的层级数 = markdown所在目录的深度
            # 但因为我们想要 media/My Journals/2013/2013-02/ 这样的结构
            # 所以直接用 ../media/相对路径/
            media_prefix = f"../media/{'/'.join(relative_path.parts)}"

        # 确保路径以/结尾
        if not media_prefix.endswith('/'):
            media_prefix += '/'

        import re

        # 匹配 ![alt](index_files/filename) 格式
        content = re.sub(
            r'!\[(.*?)\]\(index_files/([^)]+)\)',
            rf'![\1]({media_prefix}\2)',
            content
        )

        # 匹配 [text](index_files/filename) 格式的链接
        content = re.sub(
            r'\[(.*?)\]\(index_files/([^)]+)\)',
            rf'[\1]({media_prefix}\2)',
            content
        )

        md_file.write_text(content, encoding='utf-8')

    def _clean_markdown_format(self, md_file: Path) -> None:
        """清理 Markdown 格式问题"""
        if not md_file.exists():
            return

        content = md_file.read_text(encoding='utf-8')
        import re

        # 移除行尾的反斜杠（Markdown 硬换行符）
        content = re.sub(r'\\\s*$', '', content, flags=re.MULTILINE)

        # 移除孤立的反斜杠（前面是空格或行首，后面是空格或行尾）
        content = re.sub(r'(?<=\s)\\(?=\s|$)', '', content)

        # 清理多余的空行（超过2个连续换行）
        content = re.sub(r'\n{3,}', '\n\n', content)

        md_file.write_text(content, encoding='utf-8')

    def export(self) -> bool:
        """执行导出操作"""
        self.logger.info("=" * 60)
        self.logger.info("为知笔记导出工具")
        self.logger.info("=" * 60)

        # 检查必要路径
        self.logger.info(f"检查 WizNote 数据目录: {self.wiz_home}")
        if not self.wiz_home.exists():
            self.logger.error(f"WizNote 数据目录不存在: {self.wiz_home}")
            return False

        self.logger.info(f"检查 notes 目录: {self.notes_dir}")
        if not self.notes_dir.exists():
            self.logger.error(f"notes 目录不存在: {self.notes_dir}")
            return False

        # 连接数据库
        if not self.connect_db():
            return False

        # 显示表结构（用于调试）
        self.show_tables()

        # 获取所有子目录
        self.logger.info(f"正在扫描目录: {self.export_path}")
        folders = self.get_all_subfolders(self.export_path)
        self.logger.info(f"找到 {len(folders)} 个目录")

        # 添加根目录本身
        root_folder = {'path': self.export_path, 'name': os.path.basename(self.export_path) or 'root'}
        all_folders = [root_folder] + folders

        # 创建目录结构
        self.logger.info("创建目录结构...")
        self.create_directory_structure(all_folders)

        # 处理每个目录中的笔记
        total_docs = 0
        success_docs = 0

        for folder in all_folders:
            folder_path = folder['path']
            docs = self.get_documents(folder_path)

            if docs:
                self.logger.info(f"处理目录: {folder_path}")
                for doc in docs:
                    total_docs += 1
                    if self.process_document(doc):
                        success_docs += 1

        # 关闭数据库
        if self.conn:
            self.conn.close()

        # 统计信息
        self.logger.info("=" * 60)
        self.logger.info("导出完成!")
        self.logger.info(f"总笔记数: {total_docs}")
        self.logger.info(f"成功导出: {success_docs}")
        self.logger.info(f"失败: {total_docs - success_docs}")
        self.logger.info(f"输出目录: {self.output_dir.absolute()}")
        self.logger.info("=" * 60)

        return success_docs > 0

    def cleanup(self) -> None:
        """清理临时目录"""
        if self.tmp_dir.exists():
            self.logger.info(f"清理临时目录: {self.tmp_dir}")
            shutil.rmtree(self.tmp_dir)
            self.logger.info("清理完成")


def get_default_wiz_home() -> Path:
    """获取默认的 WizNote 数据目录"""
    return Path.home() / ".wiznote"


def get_os_name() -> str:
    """获取操作系统名称"""
    if sys.platform == "darwin":
        return "macOS"
    elif sys.platform == "win32":
        return "Windows"
    elif sys.platform.startswith("linux"):
        return "Linux"
    else:
        return "Unknown"


def get_default_wiz_home_display() -> str:
    """获取当前操作系统下的默认 WizNote 数据目录显示路径"""
    if sys.platform == "darwin":
        return "~/.wiznote"
    elif sys.platform == "win32":
        return "C:\\Users\\用户名\\.wiznote"
    else:
        return "~/.wiznote"


# 全局授权管理器实例（用于在导出成功后扣次数）
_license_manager = None

def get_license_manager():
    """获取授权管理器实例"""
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager

def check_license():
    """检查授权，返回是否允许继续运行（不扣次数）"""
    if not LICENSE_ENABLED:
        return True, None

    manager = get_license_manager()
    allowed, remaining, machine_code, error = manager.check_only()

    if not allowed:
        print("\n" + "=" * 60)
        print("           ⚠️ 需要解锁")
        print("=" * 60)
        print()
        print("本工具需要解锁后才能使用。")
        print()
        print("请联系我获取解锁码：")
        print()
        print("  QQ: 843115404")
        print()
        print("-" * 60)
        print(f"您的机器码: {machine_code}")
        print("-" * 60)
        print()
        print("提示: 选中上面的机器码，按 Enter 键即可复制")
        print()
        print("请复制机器码发送给我，我会为您生成解锁码。")
        print("=" * 60)
        print()

        # 循环直到解锁成功或用户退出
        while True:
            reset_code = input("请输入解锁码 (或按 Ctrl+C 退出): ").strip()
            if not reset_code:
                continue

            if manager.reset_with_code(reset_code):
                print("\n✓ 解锁成功！")
                # 重新检查授权
                allowed, remaining, machine_code, error = manager.check_only()
                if allowed:
                    print(f"剩余使用次数: {remaining}")
                    return True, remaining
            else:
                print("\n✗ 解锁码无效，请检查输入是否正确。")
                print("请重新输入或联系 QQ: 843115404\n")

    return True, remaining

def consume_license():
    """消耗一次使用次数（导出成功后调用）"""
    if not LICENSE_ENABLED:
        return True

    manager = get_license_manager()
    if manager.use_one():
        info = manager.get_usage_info()
        print(f"\n本次导出已记录，剩余使用次数: {info['remaining']}")
        return True
    return False


def main():
    # 首先检查授权
    try:
        license_ok, remaining = check_license()
    except KeyboardInterrupt:
        print("\n\n已取消操作，程序退出。")
        sys.exit(0)

    if not license_ok:
        print("\n授权检查失败。")
        print("\n按回车键退出...")
        input()
        return

    # 创建日志目录
    log_dir = Path("wizlog")
    logger = Logger(log_dir)

    try:
        print("为知笔记(WizNote)导出工具")
        print("-" * 60)
        if remaining is not None:
            print(f"剩余使用次数: {remaining}")
        logger.info("程序启动")

        # 获取 WizNote 数据目录
        default_wiz_home = get_default_wiz_home()
        default_display = get_default_wiz_home_display()
        os_name = get_os_name()

        print(f"\n默认 WizNote 数据目录: {default_display}")
        if os_name == "macOS":
            print("查看方式: WizNote → 偏好设置 → 存储")
        elif os_name == "Windows":
            print("查看方式: 菜单 → 向下箭头 → 选项 → 数据存储")
        else:
            print("(可通过 WizNote 菜单-选项-数据存储 查看或修改)")

        wiz_home_input = input(f"请输入 WizNote 数据目录 [直接回车使用默认]: ").strip()
        if wiz_home_input:
            wiz_home = Path(wiz_home_input)
        else:
            wiz_home = default_wiz_home

        logger.info(f"使用数据目录: {wiz_home}")

        # 获取邮箱（WizNote 账号）
        username = input("\n请输入 WizNote 邮箱: ").strip()
        if not username:
            print("错误: 邮箱不能为空")
            logger.error("邮箱不能为空")
            print("\n按回车键继续...")
            input()
            return

        logger.info(f"用户名: {username}")

        # 获取导出路径
        export_path = input("请输入要导出的目录路径 (如 /我的笔记/工作) [直接回车导出全部]: ").strip()
        if not export_path:
            export_path = "/"  # 默认为根目录

        # 确保路径以 / 开头
        if not export_path.startswith("/"):
            export_path = "/" + export_path

        logger.info(f"导出路径: {export_path}")

        # 创建导出器 - 根据操作系统选择数据目录策略
        if sys.platform == "win32":
            # Windows: 优先 Data/邮箱，降级 data/邮箱，最后尝试 邮箱/Data 和 邮箱/data
            data_paths = [
                wiz_home / "Data" / username,
                wiz_home / "data" / username,
                wiz_home / username / "Data",
                wiz_home / username / "data",
            ]
        else:
            # macOS/Linux: 优先 邮箱/data，降级 邮箱/Data，最后尝试 data/邮箱 和 Data/邮箱
            data_paths = [
                wiz_home / username / "data",
                wiz_home / username / "Data",
                wiz_home / "data" / username,
                wiz_home / "Data" / username,
            ]

        wiz_home_full = None
        for path in data_paths:
            logger.info(f"检查目录: {path} (exists: {path.exists()})")
            if path.exists():
                wiz_home_full = path
                logger.info(f"使用目录: {path}")
                break

        if wiz_home_full is None:
            # 如果都不存在，使用默认的第一个路径
            wiz_home_full = data_paths[0]
            logger.info(f"未找到存在的目录，使用默认: {wiz_home_full}")
        exporter = WizExporter(username, export_path, wiz_home_full, logger)

        # 执行导出
        success = exporter.export()

        # 导出成功后消耗使用次数
        if success:
            consume_license()

        # 询问是否清理临时目录
        if success:
            print()
            cleanup = input("是否清理临时目录 wiz_tmp? (y/n): ").strip().lower()
            if cleanup == 'y':
                exporter.cleanup()

        logger.info(f"程序结束，成功: {success}")

        if not success:
            print("\n导出失败，请检查错误信息。")
            print("\n按回车键继续...")
            input()

    except KeyboardInterrupt:
        print("\n\n用户取消操作")
        logger.info("用户取消操作 (KeyboardInterrupt)")
    except Exception as e:
        print(f"\n程序发生错误: {e}")
        logger.exception("程序发生未捕获的异常")
        traceback.print_exc()
        print("\n按回车键继续...")
        input()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
WizNote Exporter 打包脚本
使用 PyInstaller 生成 Windows 和 macOS 可执行文件
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path


class Builder:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.dist_dir = self.script_dir / "dist"
        self.build_dir = self.script_dir / "build"
        self.spec_dir = self.script_dir / "specs"

    def check_pyinstaller(self):
        """检查是否安装了 PyInstaller"""
        try:
            subprocess.run(["pyinstaller", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("错误: 未安装 PyInstaller")
            print("请先安装: pip install pyinstaller")
            return False

    def clean(self):
        """清理构建目录"""
        print("清理构建目录...")
        for dir_path in [self.dist_dir, self.build_dir, self.spec_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"  已删除: {dir_path}")
        print("清理完成\n")

    def get_icon_path(self):
        """获取图标路径（如果存在）"""
        icon_path = self.script_dir / "icon.ico"
        if icon_path.exists():
            return str(icon_path)
        return None

    def build_windows(self):
        """构建 Windows 可执行文件"""
        print("=" * 60)
        print("构建 Windows 可执行文件 (.exe)")
        print("=" * 60)

        if platform.system() != "Windows":
            print("警告: 当前不是 Windows 系统，无法构建 Windows 可执行文件")
            print("请在 Windows 系统上运行此脚本进行构建\n")
            return False

        icon = self.get_icon_path()
        cmd = [
            "pyinstaller",
            "--onefile",  # 打包成单个文件
            "--windowed",  # Windows 下不使用控制台窗口
            "--name", "WizNote导出工具",
            "--distpath", str(self.dist_dir / "windows"),
            "--workpath", str(self.build_dir / "windows"),
            "--specpath", str(self.spec_dir),
            "--clean",
        ]

        if icon:
            cmd.extend(["--icon", icon])

        cmd.append(str(self.script_dir / "wiz_export.py"))

        try:
            subprocess.run(cmd, check=True)
            print("\n✓ Windows 可执行文件构建成功!")
            print(f"  输出位置: {self.dist_dir / 'windows' / 'WizNote导出工具.exe'}\n")
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n✗ 构建失败: {e}\n")
            return False

    def build_macos(self):
        """构建 macOS 可执行文件"""
        print("=" * 60)
        print("构建 macOS 应用程序 (.app)")
        print("=" * 60)

        if platform.system() != "Darwin":
            print("警告: 当前不是 macOS 系统，无法构建 macOS 应用程序")
            print("请在 macOS 系统上运行此脚本进行构建\n")
            return False

        icon = self.script_dir / "icon.icns"
        cmd = [
            "pyinstaller",
            "--onefile",  # 打包成单个文件
            "--name", "WizNote导出工具",
            "--distpath", str(self.dist_dir / "macos"),
            "--workpath", str(self.build_dir / "macos"),
            "--specpath", str(self.spec_dir),
            "--clean",
        ]

        # macOS 下使用 .icns 图标
        if icon.exists():
            cmd.extend(["--icon", str(icon)])

        cmd.append(str(self.script_dir / "wiz_export.py"))

        try:
            subprocess.run(cmd, check=True)

            # 创建 .app  bundles (可选，需要更复杂的配置)
            # 目前生成的是命令行工具

            print("\n✓ macOS 可执行文件构建成功!")
            print(f"  输出位置: {self.dist_dir / 'macos' / 'WizNote导出工具'}\n")

            # 创建启动脚本
            self._create_macos_launcher()

            return True
        except subprocess.CalledProcessError as e:
            print(f"\n✗ 构建失败: {e}\n")
            return False

    def _create_macos_launcher(self):
        """创建 macOS 启动脚本"""
        launcher_path = self.dist_dir / "macos" / "启动.command"
        content = """#!/bin/bash
# WizNote 导出工具启动脚本
cd "$(dirname "$0")"
./WizNote导出工具
read -p "按回车键退出..."
"""
        launcher_path.write_text(content, encoding='utf-8')
        launcher_path.chmod(0o755)
        print(f"  启动脚本已创建: {launcher_path}")

    def create_release_package(self):
        """创建发布包"""
        print("=" * 60)
        print("创建发布包")
        print("=" * 60)

        release_dir = self.script_dir / "release"
        if release_dir.exists():
            shutil.rmtree(release_dir)
        release_dir.mkdir(parents=True)

        current_platform = platform.system()

        if current_platform == "Windows":
            # Windows 发布包
            if (self.dist_dir / "windows" / "WizNote导出工具.exe").exists():
                import zipfile
                zip_path = release_dir / "WizNote导出工具-Windows.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    exe_path = self.dist_dir / "windows" / "WizNote导出工具.exe"
                    zf.write(exe_path, "WizNote导出工具.exe")
                print(f"✓ Windows 发布包已创建: {zip_path}")

        elif current_platform == "Darwin":
            # macOS 发布包
            if (self.dist_dir / "macos" / "WizNote导出工具").exists():
                # 创建 dmg 或 zip
                import zipfile
                zip_path = release_dir / "WizNote导出工具-macOS.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    macos_dir = self.dist_dir / "macos"
                    for item in macos_dir.iterdir():
                        if item.is_file():
                            zf.write(item, item.name)
                print(f"✓ macOS 发布包已创建: {zip_path}")

        print()

    def run(self):
        """运行构建流程"""
        print("\n" + "=" * 60)
        print("WizNote 导出工具 - 构建脚本")
        print("=" * 60 + "\n")

        # 检查 PyInstaller
        if not self.check_pyinstaller():
            sys.exit(1)

        # 清理旧构建
        self.clean()

        # 根据当前平台构建
        current_platform = platform.system()

        if current_platform == "Windows":
            self.build_windows()
        elif current_platform == "Darwin":
            self.build_macos()
        else:
            print(f"不支持的平台: {current_platform}")
            print("支持的系统: Windows, macOS")
            sys.exit(1)

        # 创建发布包
        self.create_release_package()

        print("=" * 60)
        print("构建完成!")
        print("=" * 60)


if __name__ == "__main__":
    builder = Builder()
    builder.run()

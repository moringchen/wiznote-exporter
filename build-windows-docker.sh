#!/bin/bash
# 使用 Docker 在 macOS 上构建 Windows 可执行文件

set -e

echo "=============================================="
echo "使用 Docker 构建 Windows 可执行文件"
echo "=============================================="
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    echo "请先安装 Docker Desktop for Mac:"
    echo "https://www.docker.com/products/docker-desktop"
    exit 1
fi

# 检查 Docker 是否运行
if ! docker info &> /dev/null; then
    echo "错误: Docker 未运行"
    echo "请启动 Docker Desktop"
    exit 1
fi

echo "1. 构建 Docker 镜像..."
docker build -t wiznote-builder -f Dockerfile.windows .

echo ""
echo "2. 运行构建容器..."
mkdir -p dist/windows-docker
docker run --rm \
    -v "$(pwd)/dist/windows-docker:/app/dist" \
    wiznote-builder \
    wine pyinstaller --onefile --windowed --distpath /app/dist --name "WizNote导出工具" wiz_export.py

echo ""
echo "3. 创建发布包..."
mkdir -p release
cd dist/windows-docker

# 创建使用说明
cat > 使用说明.txt << 'EOF'
═══════════════════════════════════════════════════════════════
    WizNote 为知笔记导出工具 - Windows 版本
═══════════════════════════════════════════════════════════════

【系统要求】
- Windows 10/11 64位
- 无需安装 Python，已打包为独立应用

【使用方法】

1. 双击运行 "WizNote导出工具.exe"

2. 输入信息：
   - 用户名：你的 WizNote 账号（如 yourname@email.com）
   - 导出目录：要导出的笔记路径

3. 导出路径示例：
   - /           - 导出全部笔记
   - /My Journals - 只导出日记
   - /工作/项目   - 只导出特定目录

【输出文件】

导出完成后会在当前目录生成：

wiz/
  └── My Journals/          ← Markdown 文件
      └── 2013/
          └── 2013-02/
              └── xxx.md

wiz_tmp/                      ← 临时文件（可删除）

wiz/media/                    ← 图片附件
  └── My Journals/
      └── 2013/
          └── 2013-02/
              └── xxx.png

【导入 Obsidian】

1. 打开 Obsidian
2. 创建或选择一个仓库
3. 将 "wiz" 文件夹中的所有内容复制到 Obsidian 仓库
4. 图片会自动显示（使用相对路径）

【注意事项】

- 如果杀毒软件提示风险，请添加到白名单
- 首次运行可能需要允许权限

【常见问题】

Q: 提示"找不到笔记文件"？
A: 请确认用户名输入正确，且 WizNote 数据存在于 C:\Users\你的用户名\.wiznote\data\

Q: 图片不显示？
A: 确保 wiz 和 wiz/media 目录一起复制到 Obsidian 中

【作者】
个人工具，仅供学习交流使用
EOF

# 创建启动脚本
cat > 快速启动.bat << 'EOF'
@echo off
chcp 65001 >nul
echo ============================================
echo WizNote 为知笔记导出工具
echo ============================================
echo.

WizNote导出工具.exe

if errorlevel 1 (
    echo.
    echo 运行出错，请查看错误信息
    pause
)
EOF

# 打包
zip -r ../../release/WizNote导出工具-Windows-Docker.zip \
    WizNote导出工具.exe \
    使用说明.txt \
    快速启动.bat

cd ../..

echo ""
echo "=============================================="
echo "构建完成！"
echo "=============================================="
echo ""
echo "输出文件: release/WizNote导出工具-Windows-Docker.zip"
echo ""
echo "文件列表:"
ls -lh dist/windows-docker/

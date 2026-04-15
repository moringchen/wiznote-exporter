# WizNote 为知笔记导出工具

将 WizNote 为知笔记导出为 Markdown 格式，便于导入 Obsidian。

## 下载地址

- **Windows 版本**: [WizNote导出工具-Windows.zip](release/WizNote导出工具-Windows.zip)
  - 解压后运行 `WizNote导出工具.exe`

- **macOS 版本**: [WizNote导出工具-macOS.zip](release/WizNote导出工具-macOS.zip)
  - 解压后双击运行 `启动.command`

## 使用方法

### 查看 WizNote 数据存储路径

**Windows:**
1. 打开 WizNote 客户端
2. 点击菜单栏的 **向下箭头** (位于左上角头像旁)
3. 选择 **选项**
4. 在左侧选择 **数据存储**
5. 查看 "数据文件存放位置"，这就是你的笔记存储路径

**macOS:**
1. 打开 WizNote 客户端
2. 点击菜单栏 **WizNote** → **偏好设置** (或按 `Cmd + ,`)
3. 在 **存储** 标签页查看数据存放位置
4. 默认位置：`~/.wiznote/` (即 `/Users/你的用户名/.wiznote/`)

**注意：** WizNote 数据可以修改到其他位置，导出工具会询问你确认实际存储路径。

### Windows

1. 下载并解压 `WizNote导出工具-Windows.zip`
2. 双击运行 `WizNote导出工具.exe`
3. 按提示输入信息：
   - **WizNote 数据目录**: 默认为 `C:\Users\你的用户名\.wiznote`，可修改
   - **用户名**: 你的 WizNote 账号（如 `yourname@email.com`）
   - **导出目录**: 要导出的笔记路径（如 `/My Journals` 或 `/`）

### macOS

1. 下载并解压 `WizNote导出工具-macOS.zip`
2. 双击运行 `启动.command`
   - 首次运行可能需要右键选择"打开"，或在系统偏好设置中允许
3. 按提示输入信息：
   - **WizNote 数据目录**: 默认为 `~/.wiznote`，可修改
   - **用户名**: 你的 WizNote 账号
   - **导出目录**: 要导出的笔记路径

## 导出路径说明

输入的导出路径格式：
- `/` - 导出全部笔记
- `/My Journals` - 只导出日记
- `/工作/项目` - 只导出特定目录

## 输出结构

导出完成后，会在当前目录生成：

```
wiz/                          # Markdown 文件
└── My Journals/              # 与为知笔记相同的目录结构
    └── 2013/
        └── 2013-02/
            └── xxx.md

wiz_tmp/                      # 临时文件（可删除）

wiz/media/                    # 图片附件
└── My Journals/
    └── 2013/
        └── 2013-02/
            └── xxx.png

wizlog/                       # 运行日志
└── wiz_export.log            # 每次运行的日志（覆盖式）
```

### 日志说明

程序会在 `wizlog/wiz_export.log` 中记录运行日志，包括：
- 数据目录路径
- 数据库连接状态
- 处理的笔记数量
- 错误和异常信息
- 导出统计信息

如果程序报错或闪退，请查看此日志文件排查问题。每次运行会覆盖旧日志。

## 导入 Obsidian

1. 打开 Obsidian
2. 创建或选择一个仓库
3. 将 `wiz` 文件夹中的所有内容复制到 Obsidian 仓库中
4. 图片路径已自动调整为相对路径，可直接显示

## 常见问题

### Q: 找不到笔记文件？
A: 请确认：
- 用户名输入正确（通常为邮箱格式）
- WizNote 数据目录设置正确
- 数据存在于 `{数据目录}/{用户名}/data/`

### Q: 导出的 Markdown 中图片不显示？
A: 确保 `wiz` 和 `wiz/media` 目录一起复制到 Obsidian 中，图片使用相对路径 `../media/...` 引用。

### Q: 程序报错或闪退？
A: 请查看 `wizlog/wiz_export.log` 日志文件，其中记录了详细的错误信息。常见问题：
- 数据目录不存在
- 用户名不正确
- 数据库文件损坏

### Q: Windows 上运行时被杀毒软件拦截？
A: 这是 PyInstaller 打包的常见问题，请将程序添加到杀毒软件白名单。

### Q: macOS 上提示"无法打开，因为无法验证开发者"？
A: 右键点击 `启动.command`，选择"打开"。或在 系统设置 -> 隐私与安全性 中允许。

## 从源码运行

如果你有 Python 环境：

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python wiz_export.py
```

## 构建可执行文件

### 构建当前平台的版本

```bash
python build.py
```

### 手动构建

**Windows:**
```bash
pyinstaller --onefile --windowed --name "WizNote导出工具" wiz_export.py
```

**macOS:**
```bash
pyinstaller --onefile --name "WizNote导出工具" wiz_export.py
```

## 系统要求

- **Windows**: Windows 10/11 64位
- **macOS**: macOS 10.15 或更高版本

## 依赖

- Python 3.8+ (仅源码运行需要)
- pandoc (可选，用于更好的 Markdown 转换)

## 许可证

MIT License

## 作者

个人工具，仅供学习交流使用。

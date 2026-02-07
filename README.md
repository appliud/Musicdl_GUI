# 🎵 MusicDL-GUI 音乐下载器

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue)](https://www.microsoft.com/windows)

一个功能强大、界面友好的音乐下载器GUI应用，支持多个主流音乐平台，具备并行搜索、智能去重、极速下载等功能。

## ✨ 功能特性

### 🎯 核心功能
- **多平台支持**：酷狗音乐、网易云音乐、QQ音乐、酷我音乐、咪咕音乐、千千音乐
- **并行搜索**：同时搜索多个平台，速度快效率高
- **智能去重**：基于歌手+歌名自动检测重复，避免重复下载
- **极速模式**：跳过链接验证，搜索速度提升3-5倍
- **实时进度**：搜索和下载都有实时进度条显示
- **批量下载**：支持多线程并行下载多首歌曲

### 🚀 性能优化
- **启动速度**：目录模式打包，启动时间从10-15秒优化到2-3秒
- **并行处理**：多平台同时搜索，多歌曲同时下载
- **内存优化**：智能缓存，避免重复加载

### 🎨 用户体验
- **图形界面**：基于Tkinter的现代化GUI设计
- **一键启动**：提供启动脚本，双击即可运行
- **友好提示**：操作提示清晰，错误信息明确
- **重复提醒**：下载前自动提示重复歌曲

## 📦 安装说明

### 方式一：使用预编译版本（推荐）

1. 下载 `MusicDL-GUI.zip` 压缩包
2. 解压到任意目录
3. 双击 `MusicDL-GUI.exe` 运行

**系统要求：**
- Windows 10/11 64位
- 2GB 内存
- 1GB 磁盘空间

### 方式二：从源码运行

#### 环境要求
- Python 3.8 或更高版本
- pip 包管理器

#### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/musicdl-gui.git
cd musicdl-gui

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行程序
python musicdl_gui.py
```

#### 依赖列表
```
musicdl>=2.9.0
Pillow>=9.0.0
requests>=2.28.0
```

## 🚀 使用方法

### 快速开始

1. **选择音乐平台**
   - 勾选要搜索的音乐平台（支持多选）
   - 建议同时选择2-3个平台以获得更好结果

2. **配置搜索选项**
   - **每平台结果数**：设置每个平台返回的歌曲数量（默认5）
   - **搜索模式**：
     - ⚡ **极速模式**：跳过链接验证，搜索更快（推荐）
     - **标准模式**：完整验证，更稳定但较慢
   - **下载线程数**：设置并行下载的线程数（默认5）

3. **输入歌曲名称**
   - 在搜索框输入要搜索的歌曲名称
   - 按回车或点击"🔍 开始搜索"

4. **查看搜索结果**
   - 程序会实时显示每个平台的搜索结果
   - 已存在的歌曲会自动过滤，不会显示

5. **选择并下载**
   - 在结果列表中勾选要下载的歌曲
   - 选择保存目录
   - 点击"⬇️ 开始下载"

### 高级功能

#### 批量下载
- 支持按住 `Ctrl` 或 `Shift` 多选歌曲
- 点击"全选"按钮选择所有歌曲
- 点击"反选"按钮反转选择

#### 重复检测
程序会在以下时机检测重复：
1. **搜索时**：自动过滤目录中已存在的歌曲
2. **下载前**：再次检查，提示重复歌曲

检测依据：**歌手 + 歌名**（不区分大小写）

#### 文件命名
下载的文件会自动命名为：
```
歌手 - 歌名 (专辑) [音质].扩展名
```

示例：
```
G.E.M. 邓紫棋 - 唯一 (T.I.M.E.) [无损 FLAC].flac
告五人 - 唯一 (运气来得若有似无) [无损 FLAC].flac
```

## 📁 项目结构

```
MusicDL-GUI/
├── musicdl_gui.py          # 主程序（GUI版本）
├── musicdl_cmd.py                     # 命令行版本
├── create_icon.py           # 图标生成脚本
├── musicdl_icon.ico         # 应用程序图标
├── requirements.txt         # 依赖列表
├── README.md               # 项目说明
├── 使用说明.md              # 详细使用文档
├── 启动音乐下载器.bat       # Windows启动脚本
├── dist/                   # 打包输出目录
│   └── MusicDL-GUI/        # 可执行程序
│       ├── MusicDL-GUI.exe # 主程序
│       └── _internal/      # 依赖文件
└── build/                  # 构建临时文件
```

## 🔧 打包说明

如果你想自己打包成EXE文件：

### 1. 安装 PyInstaller
```bash
pip install pyinstaller
```

### 2. 打包命令
```bash
# 创建图标
python create_icon.py

# 打包GUI版本（目录模式，启动更快）
pyinstaller --clean --noconfirm --name "MusicDL-GUI" --windowed --onedir --icon="musicdl_icon.ico" musicdl_gui.py

# 或打包为单文件（文件更小，启动较慢）
pyinstaller --clean --noconfirm --name "MusicDL-GUI" --windowed --onefile --icon="musicdl_icon.ico" musicdl_gui.py
```

### 3. 输出文件
打包完成后，可执行文件位于 `dist/MusicDL-GUI/` 目录

## ⚠️ 注意事项

1. **网络要求**：程序需要联网才能搜索和下载音乐
2. **版权问题**：下载的音乐仅供个人学习使用，请勿用于商业用途
3. **依赖文件夹**：`_internal` 文件夹包含运行必需的依赖库，请勿删除
4. **杀毒软件**：某些杀毒软件可能误报，如遇此情况请添加信任

## 🐛 常见问题

### Q: 程序启动很慢？
**A**: 首次启动需要初始化环境，可能会稍慢。后续启动会快很多（目录模式约2-3秒）。

### Q: 搜索结果为空？
**A**: 请检查：
1. 是否已连接到互联网
2. 是否选择了至少一个音乐平台
3. 搜索关键词是否正确

### Q: 下载失败？
**A**: 可能原因：
1. 网络连接不稳定
2. 该歌曲在当前平台不可用
3. 尝试切换其他音乐平台

### Q: 如何创建桌面快捷方式？
**A**: 
1. 找到 `MusicDL-GUI.exe`
2. 右键 → 发送到 → 桌面快捷方式

### Q: 可以复制到其他电脑使用吗？
**A**: 可以！复制整个 `MusicDL-GUI` 文件夹到其他电脑，双击 `MusicDL-GUI.exe` 即可运行，无需安装Python。

## 📝 更新日志

### v2.0 (2024-02-07)
- ✅ 优化启动速度（从10-15秒优化到2-3秒）
- ✅ 添加智能重复检测功能
- ✅ 支持并行搜索多平台
- ✅ 添加实时进度条显示
- ✅ 添加极速搜索模式
- ✅ 优化文件命名格式
- ✅ 添加应用图标

### v1.0 (2024-02-01)
- 🎉 初始版本发布
- 支持6个主流音乐平台
- 基础搜索下载功能
- GUI图形界面

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 提交Issue
- 描述清楚问题和复现步骤
- 提供系统环境和版本信息
- 附上错误截图（如有）

### 提交PR
1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 开源协议

本项目基于 [MIT](LICENSE) 协议开源。

## 🙏 致谢

- [musicdl](https://github.com/CharlesPikachu/musicdl) - 提供音乐下载核心功能
- [PyInstaller](https://pyinstaller.org/) - 提供打包工具
- 所有测试和提出建议的用户


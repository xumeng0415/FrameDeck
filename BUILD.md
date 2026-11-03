# FrameDeck 构建方法

本项目是 FrameDeck（PySide6 桌面 VFX 审片播放器）的**中文化 + 功能增强版**：
- 全界面简体中文（i18n 架构，支持 9 种语言运行时切换：简体中文 / 繁體中文 / English / 日本語 / 한국어 / Русский / Français / Deutsch / Español）
- Shotgun RV 式逐帧拖动（查看器内按住左键左右拖动，10 像素 = 1 帧）

本包内已附带一份构建好的单文件程序：`dist/FrameDeck.exe`（109 MB，双击即用，无需安装）。
以下说明用于**从源码重新构建**或进行二次开发。

---

## 一、环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / 11（64 位） |
| Python | 3.13（已在 3.13 完整验证；3.10–3.12 用原版方式 A 亦可） |
| 网络 | 需要联网安装依赖；国内推荐使用阿里云 PyPI 镜像 |
| 磁盘 | 构建过程约需 2 GB 临时空间，产物约 109 MB |

## 二、统一构建脚本（推荐）

包内自带跨平台脚本 `build.sh`（Windows 上用 **Git Bash** 运行，Linux 上直接 bash）：

```bash
./build.sh              # 自动：Windows 上构建单 exe，Linux 上构建 AppImage
./build.sh onefile      # 单文件 exe → dist/FrameDeck.exe（不含 ACES 配置）
./build.sh windows      # Windows 多目录 → dist/FrameDeck/（尽力下载 ACES 1.2）
./build.sh linux        # Ubuntu 22.04+ AppImage → dist/FrameDeck-Ubuntu-x86_64.AppImage
```

脚本会自动完成：创建 `.venv-build` 虚拟环境（阿里云 PyPI 镜像，可用 `PIP_INDEX_URL` 覆盖）→ 安装依赖（自动识别 Python 3.13+ 并处理 pyqtdarktheme）→ PyInstaller 打包。`SKIP_DEPS=1 ./build.sh onefile` 可复用已有环境跳过装依赖。

> Linux 目标只能在 Linux 上构建（无法交叉打包）；onefile/windows 目标在 Windows 上构建。
> 环境要求与下方"方式 B"一致：Python 3.10–3.13（3.13 已完整验证），构建约需 2 GB 临时空间。

## 三、方式 B：手动单文件 exe（与脚本等价，已验证）

在项目根目录（本文件所在目录）打开 PowerShell，逐条执行：

### 1. 创建构建虚拟环境
```powershell
python -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install --index-url https://mirrors.aliyun.com/pypi/simple/ --upgrade pip
```

### 2. 安装依赖
```powershell
.venv-build\Scripts\python.exe -m pip install `
  --index-url https://mirrors.aliyun.com/pypi/simple/ `
  --timeout 120 `
  "PySide6==6.9.0" numpy "av==17.0.0" requests "PyOpenGL==3.1.9" `
  opencolorio OpenImageIO "pyinstaller==6.21.0"
```

### 3. 安装深色主题（仅 Python 3.13 需要 `--ignore-requires-python`）
```powershell
.venv-build\Scripts\python.exe -m pip install `
  --index-url https://mirrors.aliyun.com/pypi/simple/ `
  --ignore-requires-python "pyqtdarktheme==2.1.0"
```
> 3.10–3.12 用户可去掉 `--ignore-requires-python` 直接安装。

### 4. 打包单文件 exe
```powershell
.venv-build\Scripts\python.exe -m PyInstaller --noconfirm --clean framedeck-onefile.spec
```
产物：`dist\FrameDeck.exe`

### 5.（可选）启用 ACES 1.2 内置色彩配置
单文件包**不包含** ACES 1.2 OCIO 配置（数百 MB，不适合单 exe）。程序对缺失有容错，以 OCIO Off 模式运行。如需启用：
```powershell
.venv-build\Scripts\python.exe scripts\fetch_aces12.py    # 下载并校验 ACES 1.2 配置
```
然后改用多目录方式打包（`framedeck.spec`，产物为 `dist\FrameDeck\` 文件夹）。

## 四、方式 A：原版多目录打包（Python 3.10）

> **本包未包含原版一键脚本**（`build-windows.ps1` / `build-ubuntu-appimage.sh`，发布时已裁剪）。
> 跨平台打包请用 `build.sh windows` / `build.sh linux`；其依赖安装与下面的手动命令一致。

```powershell
# Windows（等价于原 build-windows.ps1，Python 3.10 + onedir 产物）
py -3.10 -m venv .venv-build
.venv-build\Scripts\python.exe -m pip install -r requirements-windows.txt
.venv-build\Scripts\python.exe scripts\fetch_aces12.py
.venv-build\Scripts\python.exe -m PyInstaller --noconfirm --clean framedeck.spec
# 产物：dist\FrameDeck\ （多目录，含 ACES 1.2 色彩配置）
```

```bash
# Ubuntu 22.04+（等价于原 build-ubuntu-appimage.sh）
# 先装系统依赖：
sudo apt update
sudo apt install -y python3 python3-venv curl libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 libpulse0
python3 -m venv build-linux/venv
build-linux/venv/bin/python -m pip install -r requirements-linux.txt
build-linux/venv/bin/python scripts/fetch_aces12.py
build-linux/venv/bin/python -m PyInstaller --noconfirm --clean framedeck-linux.spec
# 产物 dist/FrameDeck/ 需再按原脚本组装 AppImage（packaging/appimage/ 内有 AppRun 与 desktop）
```

依赖为 3.10 时代的锁定版本（numpy 1.26 等），不要与方式 B 混用环境。

## 五、开发模式运行（不打包）

```powershell
python -m venv .venv-dev
.venv-dev\Scripts\python.exe -m pip install --index-url https://mirrors.aliyun.com/pypi/simple/ -r requirements-windows.txt
.venv-dev\Scripts\python.exe main.py
```

## 六、构建验证清单

构建完成后建议依次确认：
1. 双击 `dist\FrameDeck.exe` 能打开主界面
2. 导入素材后在画面上**按住左键左右拖动** —— 应逐帧平滑移动（10px = 1 帧）
3. 播放中抓帧应自动暂停，松手停在当前位置
4. 菜单 工具 → 语言：简体中文 / 繁體中文 / English 即时切换，当前素材自动保留
5. 帮助 → FrameDeck 快捷键：包含拖拽说明

## 七、目录速览

| 路径 | 内容 |
| --- | --- |
| `main.py` | 程序入口（启动前解析语言偏好） |
| `widgets/` | 全部界面（主窗口、查看器、播放列表、导出等） |
| `playback/` | 播放与解码（MoviePlayer / SequencePlayer / 缓存） |
| `constants/` | 枚举与配置（含拖拽灵敏度 `FRAME_DRAG_PIXELS_PER_FRAME = 10`） |
| `utils/i18n.py` | 国际化运行时（键 = 英文原句） |
| `resources/i18n/` | 语言文件 ×9：`zh_CN` / `zh_TW` / `en_US` / `ja` / `ko` / `ru` / `fr` / `de` / `es` |
| `resources/ocio/` | OCIO 相关资源 |
| `doc/l10n/` | 术语表、汉化规范、译文索引、静态验收工具 `check_l10n.py` |
| `tests/` | 测试套件（需先安装 pytest 与 PySide6 才能运行） |
| `build.sh` | 统一构建脚本（Windows/Linux 通用，Git Bash 运行） |
| `framedeck-onefile.spec` | 单 exe 打包配置（本包 exe 由它构建） |
| `framedeck.spec` | 原版多目录打包配置 |

## 八、已知事项

- `zh_TW.json` 为 OpenCC 全量繁体（标准字形）；如需台湾词汇级习惯（影片/滑鼠/檔案等），换 `s2twp` 档位重新生成即可。
- 六门新语言（ja/ko/ru/fr/de/es）术语按影视后期软件惯例翻译，个别长句偏直译，可按反馈单点修订 `resources/i18n/<lang>.json`。
- Python 3.13 下 `pyqtdarktheme==2.1.0` 官方声明不支持，需 `--ignore-requires-python` 强装（已实测功能正常）。
- PDF 报告导出使用系统默认字体（已含中文回退），Windows 下正常；如在其他平台出现方块请安装 CJK 字体。

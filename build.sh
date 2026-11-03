#!/usr/bin/env bash
# ============================================================================
# FrameDeck 统一构建脚本（Windows / Linux 通用，在 Windows 上用 Git Bash 运行）
#
# 用法:
#   ./build.sh                # 自动: Linux 上构建 AppImage, Windows 上构建单 exe
#   ./build.sh onefile        # 单文件 exe (dist/FrameDeck.exe, 不含 ACES 配置)
#   ./build.sh windows        # Windows 多目录 (dist/FrameDeck/, 尽力下载 ACES)
#   ./build.sh linux          # Ubuntu 22.04+ AppImage (dist/FrameDeck-Ubuntu-x86_64.AppImage)
#
# 可用环境变量:
#   PIP_INDEX_URL             # PyPI 镜像, 默认阿里云
#   SKIP_DEPS=1               # 复用已有 .venv-build, 跳过依赖安装
#
# 依赖版本与 BUILD.md 保持一致 (已在 Python 3.13 完整验证; 3.10-3.12 亦适用)。
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

TARGET="${1:-auto}"
PIP_INDEX="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"

# ---------------------------------------------------------------- OS 检测 ---
OS="windows"
case "$(uname -s)" in
    Linux*) OS="linux" ;;
    Darwin*) echo "错误: 本脚本不支持 macOS (项目依赖的解码库无 macOS wheel)"; exit 1 ;;
esac

if [[ "$TARGET" == "auto" ]]; then
    if [[ "$OS" == "linux" ]]; then TARGET="linux"; else TARGET="onefile"; fi
fi

echo "==> 目标: $TARGET  (宿主: $OS)"

# ------------------------------------------------------------ 虚拟环境准备 ---
if [[ "$OS" == "linux" ]]; then
    PY_CMD="python3"
    VENV_PY="$ROOT/.venv-build/bin/python"
else
    PY_CMD="python"
    VENV_PY="$ROOT/.venv-build/Scripts/python.exe"
fi

if [[ ! -x "$VENV_PY" ]]; then
    echo "==> 创建构建虚拟环境 .venv-build"
    "$PY_CMD" -m venv .venv-build
fi

"$VENV_PY" -m pip install --index-url "$PIP_INDEX" --disable-pip-version-check \
    --upgrade pip >/dev/null

# -------------------------------------------------------------- 依赖安装 ---
if [[ "${SKIP_DEPS:-0}" == "1" && -x "$VENV_PY" ]]; then
    echo "==> SKIP_DEPS=1, 跳过依赖安装"
else
    echo "==> 安装依赖 (镜像: $PIP_INDEX)"
    "$VENV_PY" -m pip install --index-url "$PIP_INDEX" --disable-pip-version-check \
        --timeout 120 \
        "PySide6==6.9.0" numpy "av==17.0.0" requests "PyOpenGL==3.1.9" \
        opencolorio OpenImageIO "pyinstaller==6.21.0"

    # pyqtdarktheme 声明不支持 3.13+, 但为纯 Python 包, 实测 3.13 下功能正常
    PY_MINOR="$("$VENV_PY" -c 'import sys; print(sys.version_info[1])')"
    PY_MAJOR="$("$VENV_PY" -c 'import sys; print(sys.version_info[0])')"
    DT_FLAGS=()
    if (( PY_MAJOR > 3 || (PY_MAJOR == 3 && PY_MINOR >= 13) )); then
        DT_FLAGS=(--ignore-requires-python)
    fi
    "$VENV_PY" -m pip install --index-url "$PIP_INDEX" --disable-pip-version-check \
        "${DT_FLAGS[@]}" "pyqtdarktheme==2.1.0"
fi

# ------------------------------------------------------- ACES 配置(尽力而为) ---
fetch_aces() {
    echo "==> 尝试下载 ACES 1.2 色彩配置 (失败不影响构建, 程序以 OCIO Off 模式运行)"
    if ! "$VENV_PY" scripts/fetch_aces12.py; then
        echo "    [警告] ACES 配置下载失败, 已跳过 (OCIO Off 容错)"
    fi
}

# ------------------------------------------------------------------ 构建 ---
case "$TARGET" in
    onefile)
        echo "==> PyInstaller: framedeck-onefile.spec (单文件, 不打 ACES 配置)"
        "$VENV_PY" -m PyInstaller --noconfirm --clean framedeck-onefile.spec
        echo ""
        echo "构建完成: dist/FrameDeck.exe"
        ;;
    windows)
        fetch_aces
        echo "==> PyInstaller: framedeck.spec (Windows 多目录)"
        "$VENV_PY" -m PyInstaller --noconfirm --clean framedeck.spec
        echo ""
        echo "构建完成: dist/FrameDeck/FrameDeck.exe"
        ;;
    linux)
        if [[ "$OS" != "linux" ]]; then
            echo "错误: linux 目标只能在 Linux 上构建 (无法跨平台交叉打包)"; exit 1
        fi
        fetch_aces
        echo "==> PyInstaller: framedeck-linux.spec"
        "$VENV_PY" -m PyInstaller --noconfirm --clean framedeck-linux.spec

        BUILD_ROOT="$ROOT/build-linux"
        APPDIR="$BUILD_ROOT/FrameDeck.AppDir"
        TOOLS="$BUILD_ROOT/tools"
        OUTPUT="$ROOT/dist/FrameDeck-Ubuntu-x86_64.AppImage"

        rm -rf "$APPDIR"
        mkdir -p "$APPDIR/usr/lib" "$TOOLS"
        cp -a "$ROOT/dist/FrameDeck" "$APPDIR/usr/lib/framedeck"
        cp "$ROOT/packaging/appimage/AppRun" "$APPDIR/AppRun"
        cp "$ROOT/packaging/appimage/framedeck.desktop" "$APPDIR/framedeck.desktop"
        cp "$ROOT/resources/icons/framedeck.png" "$APPDIR/framedeck.png"
        chmod +x "$APPDIR/AppRun" "$APPDIR/usr/lib/framedeck/FrameDeck"

        APPIMAGETOOL="$TOOLS/appimagetool-x86_64.AppImage"
        if [[ ! -x "$APPIMAGETOOL" ]]; then
            echo "==> 下载 appimagetool"
            curl -L --fail --retry 3 -o "$APPIMAGETOOL" \
                https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
            chmod +x "$APPIMAGETOOL"
        fi

        rm -f "$OUTPUT"
        ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUTPUT"
        chmod +x "$OUTPUT"
        sha256sum "$OUTPUT" | tee "$OUTPUT.sha256"
        echo ""
        echo "构建完成: $OUTPUT"
        ;;
    *)
        echo "错误: 未知目标 '$TARGET' (可用: onefile | windows | linux | auto)"; exit 1
        ;;
esac

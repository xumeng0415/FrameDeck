#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FrameDeck 汉化静态校验工具（文档配套工具，不进运行时、不 import 项目模块）。

⚠️ 本工具**仅做静态检查，不替代 GUI 实机验证**。跑绿只代表"源码层面没有明显问题"，
不代表界面不截断、PDF 不出豆腐块、HUD 不串位。实机项见规范 §7.5「未验证清单」。

为什么存在：交付环境装不上 PySide6（pip 在 66 MB 主包处 IncompleteRead），
`QT_QPA_PLATFORM=offscreen pytest` 无法执行。本脚本用**标准库 ast + git** 提供
与 pytest 互补的静态门禁，只读源码文本，**不 import 任何项目模块**。

四项检查：

  1. residue       残留英文：UI 调用点的英文字符串，分 VIOLATION / ALLOWED / UNKNOWN
  2. placeholder   占位符漂移：与 baseline 提交比对，每个模板的占位符集合必须等价
  3. scope         改动范围：git diff 只含预期文件；widgets/__init__.py 775 行之后不许有删除行
  4. assertions    测试断言归类：A=源已译必须同步改 / B=源未动保持 / C=人工判定

三类结果的判定（核心约定）：

  VIOLATION  在**本次检查范围内**的英文 UI 文案，且未命中白名单  → 应译未译，必须 0
  ALLOWED    命中白名单（刻意保留的合规英文：配置名/品牌/字体族/结构值）→ 计数，不算失败
  UNKNOWN    在**范围之外**的英文 UI 文案，且未命中白名单          → 尚未施工的批次
             全库收尾时（--expect 覆盖全部源码）UNKNOWN 也必须为 0

用法：

    python doc/l10n/check_l10n.py --baseline d3d8497
    python doc/l10n/check_l10n.py --baseline d3d8497 --only widgets/__init__.py --strict
    python doc/l10n/check_l10n.py --only residue -v
    python doc/l10n/check_l10n.py --only placeholder
    python doc/l10n/check_l10n.py --only scope --expect widgets/__init__.py
    python doc/l10n/check_l10n.py --only assertions

`--only` 的值既可以是检查名（residue/placeholder/scope/assertions/all），
也可以是文件路径前缀（如 `widgets/__init__.py`、`widgets/`）——后者用于按批次限定范围。

设计约定（改本脚本时请遵守）：

    * 只用标准库：argparse ast collections re subprocess sys pathlib
    * 不 import constants / widgets / playback 等任何项目模块
    * 白名单只放"有明确理由的合规英文"，不放"暂时懒得译"的词；
      第四列非空的条目是施工中间态，到该批次必须删除（脚本会提示）。
"""

from __future__ import print_function

import argparse
import ast
import collections
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SOURCE_DIRS = ["constants", "logger", "ocio", "playback", "scripts", "utils", "widgets"]
SOURCE_FILES = ["main.py"]
CHECK_NAMES = {"all", "residue", "placeholder", "scope", "assertions"}

# ---------------------------------------------------------------- 白名单
# 每项：(文件子串, 精确子串, 理由, 何时该删)
# 匹配规则：`file` 命中相对路径（空 = 任意文件）、`text` 命中字面量（空 = 该文件全部）。
# 第四列非空 = 施工中间态，到该批次收尾必须删除本条。
WHITELIST = [
    # 只列"**能够被扫描到**（即出现在 UI 调用参数里）且刻意不译"的项。
    # 匹配规则：`file` 命中相对路径（空 = 任意文件）、`text` 命中字面量（子串）。
    # 第四列非空 = 施工中间态，到该批次收尾必须删除本条。
    ("widgets/ocio.py", "ACES 1.2 Legacy", "OCIO 配置显示名，与 config:// 名并列，不译（L-01 同类）", ""),
]

# 刻意保留英文、但**不在扫描面内**的字符串（它们不是 UI 调用参数，扫描器本就看不到）。
# 保留这份清单是为了让"为什么这些英文没被报"有据可查，而不是让脚本去放过它们。
EXEMPT_NOT_SCANNED = [
    ("constants/__init__.py", "FPS_VALUES[*][\"code\"]", "23.976- FPS 等 8 条，dict 值，不参与 UI 调用（§3.6 决定保留 FPS）"),
    ("constants/__init__.py", "REVIEW_TYPES[*][\"tooltip\"] x6", "全库无读取点的死字符串，裁定不译（含原文拼写瑕疵 Notifiction）"),
    ("constants/__init__.py", "\"Auto\"", "色彩空间兜底值，与 OCIO AUTO_INPUT 语义相连"),
    ("widgets/ocio.py", "AUTO_INPUT / config_label", "被 != 比较 + 存 QSettings（R3）"),
    ("widgets/ocio.py", "\"Academy Color Encoding System - \"", "OCIO description 的 replace 目标串"),
    ("widgets/styles.py", "\"Segoe UI\"", "QFont 参数，不在 UI 调用面内；改它属样式变更"),
    ("widgets/labels.py", "constants.FONT_FAMILY", "QFont 参数（Arial），不改"),
    ("widgets/pdfreport.py", "\"Helvetica\"", "QFont 参数 → B5 改 QFont()（见 §6 B5 字体子项）"),
    ("widgets/viewer.py", "\"Consolas\"", "QFont 参数 → B5 加 setFamilies 回退"),
    ("widgets/viewer.py", "\"Radius\" / \"Thicknes\" / \"Thickness\"", "setValue 参数，不是 UI 调用；L-03 由 §6.2-B5 的 grep 判据守"),
    ("widgets/labels.py", "\"Radius\"", "__eq__ 比较字面量，不是 UI 调用；L-03 同上"),
    ("ocio/__init__.py", "全部 9 条", "OCIO 契约（色彩空间 / display / view / environment）"),
    ("playback/*", "异常文案", "内部异常，多数无 UI 暴露路径；见 §9 不译文件清单"),
    ("main.py", "setApplicationName / OrganizationName", "改则全部 QSettings 失效"),
]

# 明确禁止翻译的 API 调用名（其中字符串无条件跳过，不进任何桶）
FORBIDDEN_CALLS = {"setObjectName", "setStyleSheet", "setData", "addData",
                   "setProperty", "QKeySequence", "QSettings", "setShortcut",
                   "setShortcuts", "setNameFilter", "setFamilies", "setFamily"}

# 这些对象上的同名方法不是 UI 文案来源（日志 / 测试替身 / 资源层）
NON_UI_ROOTS = {"LOGGER", "logger", "logging", "log", "pytest",
                "monkeypatch", "mock", "patch", "sys", "os", "resources", "utils"}

UI_ATTRS = {
    "setText", "setToolTip", "setStatusTip", "setWindowTitle", "setTitle",
    "setPlaceholderText", "setSuffix", "setPrefix", "setLabelText",
    "addItem", "addItems", "addRow", "addTab", "addMenu", "addAction",
    "setHeaderLabels", "setHorizontalHeaderLabels", "setNameFilters",
    "showMessage", "information", "warning", "critical", "question",
    "getSaveFileName", "getOpenFileName", "getExistingDirectory",
}
UI_CTORS = {"QAction", "QLabel", "QPushButton", "QCheckBox", "QMenu", "QGroupBox",
            "MessageBox", "QProgressDialog"}

ALLOW_EXACT = {
    "FPS", "ms", "GB", "MB", "KB", "px", "%", "x", "A", "B", "A/B", "ID", "HUD",
    "RGB", "R", "G", "B", "A", "LUMA", "Alpha", "sRGB", "Rec.709", "ACES", "ACEScg",
    "OCIO", "AOV", "LUT", "Log", "Raw", "HDR", "SDR",
    "EXR", "DPX", "PNG", "JPG", "JPEG", "TIFF", "MP4", "MOV", "MXF", "MKV",
    "H.264", "H.265", "AAC", "ProRes", "DNxHD", "DNxHR", "PDF", "CSV",
    "Alpha", "Luma", "LUMA", "VFX", "CG", "ARRI", "Sony", "RED", "Blackmagic",
    "LogC3", "LogC4", "S-Log3", "Log3G10", "ACEScct", "ACES2065-1",
    "Space", "Wheel", "Ctrl", "Alt", "Shift", "Esc", "Enter", "Delete", "F11",
    "Ok", "OK", "Yes", "No", "Cancel", "Close", "Save", "Retry", "Apply",
    "Question", "Information", "Warning", "Critical",
    "Auto", "environment",
}
ALLOW_PREFIX = ("ocio://", "bundled://", "http://", "https://", "*.",
                "FRAMEDECK_", "framedeck-", "%Y", "%H", "%I", "%M", "%S")


# ---------------------------------------------------------------- 基础工具

def _source_relpaths(root):
    found = list()
    for directory in SOURCE_DIRS:
        base = Path(root) / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            found.append(path.relative_to(root).as_posix())
    for name in SOURCE_FILES:
        if (Path(root) / name).is_file():
            found.append(name)
    return found


def iter_source_files(root, only=None):
    for relpath in _source_relpaths(root):
        if only and not relpath.startswith(only):
            continue
        yield Path(root) / relpath


def read_text(path):
    with open(path, "r", encoding="utf-8") as stream:
        return stream.read()


def git_show(rev, relpath):
    try:
        out = subprocess.run(["git", "show", "%s:%s" % (rev, relpath)],
                             cwd=str(REPO_ROOT), capture_output=True)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", "replace")


def git_diff_names(baseline):
    out = subprocess.run(["git", "diff", "--name-status", baseline],
                         cwd=str(REPO_ROOT), capture_output=True)
    if out.returncode != 0:
        return list()
    rows = list()
    for line in out.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0], parts[-1]))
    return rows


def call_root_name(func):
    while isinstance(func, ast.Attribute):
        func = func.value
    if isinstance(func, ast.Name):
        return func.id
    return ""


def str_constant_nodes(node):
    """Yield (node, text) for one expression, handling implicit concat and f-strings.

    只产出"该表达式自身的静态文本"，不再深入子节点 —— 否则 f-string 的每个
    片段会被当成独立文案重复上报（早期版本的 bug，会把一处报成 2~3 处）。
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node, node.value
    elif isinstance(node, ast.JoinedStr):
        static = "".join(value.value for value in node.values
                         if isinstance(value, ast.Constant)
                         and isinstance(value.value, str))
        if static:
            yield node, static
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        # 相邻字符串字面量的隐式拼接在 AST 里是 BinOp/Add
        left = "".join(text for _n, text in str_constant_nodes(node.left))
        right = "".join(text for _n, text in str_constant_nodes(node.right))
        if left or right:
            yield node, left + right


PLACEHOLDER_BRACE = re.compile(r"\{([^{}]*)\}")
PLACEHOLDER_PERCENT = re.compile(r"%(?!%)([-+ 0#]*\d*(?:\.\d+)?[sdifri%])")


def placeholders(text):
    found = collections.Counter()
    for raw in PLACEHOLDER_BRACE.findall(text):
        spec = raw.strip()
        if not spec:
            found["{}"] += 1
            continue
        name = re.split(r"[:!]", spec, maxsplit=1)[0].strip()
        found["{" + name + spec[len(name):] + "}"] += 1
    for raw in PLACEHOLDER_PERCENT.findall(text):
        found["%" + raw] += 1
    return found


def collect_placeholders(text):
    total = collections.Counter()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return total
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            total.update(placeholders(sub.value))
    return total


def looks_like_ui_text(text):
    """Is this literal English copy a user would read (candidate for translation)?"""
    stripped = text.strip()
    if not stripped or not stripped.isascii():
        return False                    # 含中文 → 已译或混排，放行
    if stripped in ALLOW_EXACT:
        return False
    if stripped.startswith(ALLOW_PREFIX):
        return False
    words = [word for word in re.split(r"\s+", stripped) if word]
    alpha = [word for word in words if re.match(r"^[A-Za-z]", word)]
    if len(alpha) >= 2:
        return True
    if len(alpha) == 1 and len(stripped) >= 4 and stripped[0].isupper():
        return True
    return False


QSS_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}")
TRIPLE = ('\"' * 3, "'" * 3)


def stylesheet_range(old_lines, after=0):
    """Return (start, end) of the first triple-quoted stylesheet block, or None.

    只保护"样式表字符串块"这一段，而不是"775 行之后的全部" —— 后者会误报：
    行号随施工漂移，而且 1041 行之后本来就是正常代码与文案。
    """
    start = None
    for index, line in enumerate(old_lines, start=1):
        if index <= after:
            continue
        if start is None:
            if "setStyleSheet(" in line and any(q in line for q in TRIPLE):
                start = index
                if sum(line.count(q) for q in TRIPLE) >= 2:
                    return (start, start)          # 单行样式表
            continue
        if any(q in line for q in TRIPLE):
            return (start, index)
    return None


def looks_like_qss(line):
    """A removed line carrying a hex colour is stylesheet content, never copy."""
    return bool(QSS_COLOR.search(line))


def whitelist_hit(relpath, text):
    for entry in WHITELIST:
        needle_file, needle_text = entry[0], entry[1]
        if needle_file and needle_file not in relpath:
            continue
        if needle_text and needle_text not in text:
            continue
        return entry
    return None


# ---------------------------------------------------------------- 检查 1：残留英文

def check_residue(root, only=None, expect=None):
    buckets = {"VIOLATION": list(), "ALLOWED": list(), "UNKNOWN": list()}
    for path in iter_source_files(root):
        relpath = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError as error:
            buckets["VIOLATION"].append((relpath, 0, "SYNTAX ERROR: %s" % error, None))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute):
                name = node.func.attr
            elif isinstance(node.func, ast.Name):
                name = node.func.id
            else:
                continue
            if name in FORBIDDEN_CALLS or call_root_name(node.func) in NON_UI_ROOTS:
                continue
            if name not in UI_ATTRS and name not in UI_CTORS:
                continue
            if only and not relpath.startswith(only):
                continue          # 按批次限定范围：范围外的文件不扫、不入任何桶
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                for sub_node, text in str_constant_nodes(arg):
                    if not looks_like_ui_text(text):
                        continue
                    entry = whitelist_hit(relpath, text)
                    if entry is not None:
                        buckets["ALLOWED"].append((relpath, sub_node.lineno, text, entry))
                        continue
                    key = "VIOLATION" if _in_scope(relpath, only, expect) else "UNKNOWN"
                    buckets[key].append((relpath, sub_node.lineno, text, None))
    return buckets


def _in_scope(relpath, only, expect):
    if only:
        return relpath.startswith(only)
    if expect:
        return any(relpath.startswith(prefix) for prefix in expect)
    return True


# ---------------------------------------------------------------- 检查 2：占位符漂移

def check_placeholders(root, baseline, only=None):
    problems = list()
    for path in iter_source_files(root, only=only):
        relpath = path.relative_to(root).as_posix()
        before = git_show(baseline, relpath)
        if before is None:
            continue
        old = collect_placeholders(before)
        new = collect_placeholders(read_text(path))
        for key in sorted(set(old) | set(new)):
            if old[key] != new[key]:
                problems.append((relpath, key,
                                 "baseline=%d current=%d" % (old[key], new[key])))
    return problems


# ---------------------------------------------------------------- 检查 3：改动范围

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def max_changed_line(baseline, relpath):
    """Return the highest OLD line number touched by the diff of *relpath*.

    行号只能从 `@@ -a,b +c,d @@` 里取 —— patch 的 `-` 行本身不带行号，
    所以 `git diff -U0 | grep '^-' | awk -F: '{print $2}'` 永远空输出、永远通过。
    """
    out = subprocess.run(["git", "diff", "-U0", baseline, "--", relpath],
                         cwd=str(REPO_ROOT), capture_output=True)
    if out.returncode != 0:
        return 0
    text = out.stdout.decode("utf-8", "replace")
    highest = 0
    for match in HUNK.finditer(text):
        start = int(match.group(1))
        count = int(match.group(2) or 1)
        highest = max(highest, start + max(count, 1) - 1)
    return highest


def check_scope(baseline, expect, protected_file, protected_after, only=None,
                max_line=None):
    problems = list()
    for status, relpath in git_diff_names(baseline):
        if relpath.startswith("doc/"):
            continue
        if only and not relpath.startswith(only):
            continue
        if status.startswith("D"):
            problems.append((relpath, 0, "文件被删除"))
            continue
        if expect and not any(relpath.startswith(prefix) for prefix in expect):
            problems.append((relpath, 0, "不在本批预期清单内（status=%s）" % status))

    if not only or protected_file.startswith(only):
        before = git_show(baseline, protected_file)
        if before is not None:
            old_lines = before.splitlines()
            new_lines = read_text(REPO_ROOT / protected_file).splitlines()
            new_set = set(new_lines)
            span = stylesheet_range(old_lines, after=protected_after)
            removed = list()
            for index, line in enumerate(old_lines, start=1):
                if index <= protected_after or not line.strip() or line in new_set:
                    continue
                if span is not None and span[0] <= index <= span[1]:
                    removed.append(index)
                elif looks_like_qss(line):
                    removed.append(index)
            if removed:
                problems.append((protected_file, removed[0],
                                 "样式表区（%s）有 %d 行被删除/改写"
                                 % ("%d-%d" % span if span else "含颜色值行", len(removed))))

    if max_line:
        for relpath in sorted({rel for _status, rel in git_diff_names(baseline)}):
            if relpath.startswith("doc/"):
                continue
            if only and not relpath.startswith(only):
                continue
            highest = max_changed_line(baseline, relpath)
            if highest > max_line:
                problems.append((relpath, highest,
                                 "最大改动行号 %d 超过本批上限 %d（越界）"
                                 % (highest, max_line)))
    return problems


# ---------------------------------------------------------------- 检查 4：断言归类

ASSERT_STRING = re.compile(r"[\"']([^\"']{2,})[\"']")


def collect_source_strings(root, baseline=None):
    known = set()
    for path in iter_source_files(root):
        relpath = path.relative_to(root).as_posix()
        text = git_show(baseline, relpath) if baseline else read_text(path)
        if text is None:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            for _sub, value in str_constant_nodes(node):
                known.add(value)
    return known


def check_assertions(root, baseline):
    """A = 源已译（必须同步改）；B = 源未动（保持）；C = 测试自造（人工判定）。"""
    before = collect_source_strings(root, baseline=baseline)
    after = collect_source_strings(root)
    buckets = {"A": list(), "B": list(), "C": list()}
    tests_dir = Path(root) / "tests"
    if not tests_dir.is_dir():
        return buckets
    for path in sorted(tests_dir.glob("test_*.py")):
        relpath = path.relative_to(root).as_posix()
        for lineno, line in enumerate(read_text(path).splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("assert"):
                continue
            for match in ASSERT_STRING.finditer(stripped):
                literal = match.group(1) or ""
                if len(literal) < 3 or not any(ch.isalpha() for ch in literal):
                    continue
                if literal in before and literal not in after:
                    buckets["A"].append((relpath, lineno, literal))
                elif literal in before and literal in after:
                    buckets["B"].append((relpath, lineno, literal))
                elif looks_like_ui_text(literal) or not literal.isascii():
                    buckets["C"].append((relpath, lineno, literal))
    return buckets


# ---------------------------------------------------------------- 入口

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="FrameDeck 汉化静态校验（仅静态，不替代 GUI 实机验证）")
    parser.add_argument("--baseline", default="HEAD", help="基线提交（默认 HEAD）")
    parser.add_argument("--only", default="all",
                        help="检查名（residue/placeholder/scope/assertions/all）"
                             "或文件路径前缀（如 widgets/__init__.py）")
    parser.add_argument("--expect", default="",
                        help="本批预期改动的路径前缀，逗号分隔")
    parser.add_argument("--strict", action="store_true",
                        help="有 FAILURES 时退出码 1")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="打印 ALLOWED 明细")
    parser.add_argument("--max-line", type=int, default=0,
                        help="本批允许改到的最大行号（如 B2=775、B3=3085；0=不检查）")
    parser.add_argument("--protected", default="widgets/__init__.py")
    parser.add_argument("--protected-after", type=int, default=775)
    args = parser.parse_args(argv)

    only_path = None
    check = args.only
    if args.only not in CHECK_NAMES:
        only_path = args.only
        check = "all"
    expect = [part.strip() for part in args.expect.split(",") if part.strip()]
    root = REPO_ROOT
    failures = 0

    if check in ("all", "residue"):
        buckets = check_residue(root, only=only_path, expect=expect or None)
        print("== 1. 残留英文")
        print("   VIOLATION %d 处（应译未译，必须 0）" % len(buckets["VIOLATION"]))
        for relpath, lineno, text, _entry in buckets["VIOLATION"][:80]:
            print("     %s:%s  %r" % (relpath, lineno, text.replace("\n", "\\n")[:80]))
        print("   ALLOWED   %d 处（命中白名单，不算失败）" % len(buckets["ALLOWED"]))
        if args.verbose:
            for relpath, lineno, text, entry in buckets["ALLOWED"]:
                print("     %s:%s  %r   <- %s" % (relpath, lineno, text[:46], entry[2]))
        print("   UNKNOWN   %d 处（范围外且未命中白名单 = 尚未施工的批次）"
              % len(buckets["UNKNOWN"]))
        for relpath, lineno, text, _entry in buckets["UNKNOWN"][:20]:
            print("     %s:%s  %r" % (relpath, lineno, text.replace("\n", "\\n")[:60]))
        failures += len(buckets["VIOLATION"]) + len(buckets["UNKNOWN"])

        hit = set()
        for _relpath, _lineno, _text, entry in buckets["ALLOWED"]:
            hit.add(id(entry))
        print("   白名单命中 %d / %d 条" % (len(hit), len(WHITELIST)))
        stale = [entry for entry in WHITELIST if id(entry) not in hit]
        if stale:
            print("   ⚠ 白名单条目未命中 %d 条（可能已译完，应删）:" % len(stale))
            for entry in stale[:10]:
                print("     %s | %r" % (entry[0] or "<any>", entry[1]))
        expired = [entry for entry in WHITELIST if entry[3]]
        if expired:
            print("   ⚠ 白名单中间态 %d 条（到该批次必须删除）:" % len(expired))
            for entry in expired:
                print("     [%s] %s | %r" % (entry[3], entry[0] or "<any>", entry[1]))
        if args.verbose:
            print("   扫描面外的刻意英文 %d 条（EXEMPT_NOT_SCANNED，仅供查阅）:"
                  % len(EXEMPT_NOT_SCANNED))
            for relpath, name, reason in EXEMPT_NOT_SCANNED:
                print("     %s | %s  <- %s" % (relpath, name, reason))

    if check in ("all", "placeholder"):
        problems = check_placeholders(root, args.baseline, only=only_path)
        print("== 2. 占位符漂移：%d 处（必须 0）" % len(problems))
        for relpath, key, detail in problems[:40]:
            print("   %s  %s  %s" % (relpath, key, detail))
        failures += len(problems)

    if check in ("all", "scope"):
        problems = check_scope(args.baseline, expect, args.protected,
                              args.protected_after, only=only_path,
                              max_line=args.max_line)
        print("== 3. 改动范围：%d 处异常（必须 0）" % len(problems))
        for relpath, lineno, detail in problems:
            print("   %s:%s  %s" % (relpath, lineno, detail))
        failures += len(problems)

    if check in ("all", "assertions"):
        buckets = check_assertions(root, args.baseline)
        print("== 4. 断言归类：A(必须同步改)=%d  B(保持)=%d  C(人工判定)=%d"
              % (len(buckets["A"]), len(buckets["B"]), len(buckets["C"])))
        for relpath, lineno, literal in buckets["A"]:
            print("   [A] %s:%s  %r" % (relpath, lineno, literal))
        for relpath, lineno, literal in buckets["C"][:40]:
            print("   [C] %s:%s  %r" % (relpath, lineno, literal))
        failures += len(buckets["A"])       # 交付门禁：A 必须为 0

    print("\nFAILURES: %d   （VIOLATION + UNKNOWN + drift + scope + A）" % failures)
    if args.strict and failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

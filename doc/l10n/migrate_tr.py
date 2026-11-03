"""Rewrite translated CJK literals back into tr("english key") calls. v2.

Pairing comes from the baseline diff (same logic as extract_pairs.py) but keeps
the NEW-file line number and in-line occurrence order for every pair, so each
replacement lands exactly where the translation was applied — critical for
same-translation/different-key cases (Thicknes vs Thickness).

Safety nets:
- import injection located via ast (never breaks __future__ ordering)
- "+" connectors only inside the same implicit-concatenation expression
- per-file syntax self-check: any file that fails to compile after rewriting is
  restored untouched and reported for manual migration
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "d3d8497"
STR_RE = re.compile(r"(?:[rbfu]{0,2})(['\"])((?:\\.|(?!\1).)*)\1")
TARGETS = (
    "constants/__init__.py", "main.py", "utils/__init__.py",
    "playback/reader.py", "playback/player.py", "playback/proxy.py",
    "widgets/annotations.py", "widgets/cachemanager.py", "widgets/comboboxs.py",
    "widgets/comments.py", "widgets/dialogs.py", "widgets/fontdialog.py",
    "widgets/imageexport.py", "widgets/labels.py", "widgets/menus.py",
    "widgets/messagebox.py", "widgets/ocio.py", "widgets/pdfreport.py",
    "widgets/playlist.py", "widgets/recaps.py", "widgets/shotstrip.py",
    "widgets/videoexport.py", "widgets/viewer.py", "widgets/widgetItems.py",
    "widgets/__init__.py",
)


def has_ascii(t):
    return any(c.isascii() and c.isalpha() for c in t)


def has_cjk(t):
    return any("\u4e00" <= c <= "\u9fff" for c in t)


def strings_in(line):
    return [m.group(2) for m in STR_RE.finditer(line)]


def collect_pairs():
    diff = subprocess.run(
        ["git", "diff", f"{BASELINE}..HEAD", "--unified=1", "--", *TARGETS],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    pairs = []
    current_file = None
    dels, adds = [], []
    new_lineno = 0

    def flush():
        if current_file and dels and len(dels) == len(adds):
            for old, (lineno, text) in zip(dels, adds):
                if old != text and has_ascii(old) and not has_cjk(old) and has_cjk(text):
                    pairs.append((current_file, lineno, text, old))
        dels.clear()
        adds.clear()

    for raw in diff.splitlines():
        if raw.startswith("diff --git"):
            flush()
            current_file = raw.split(" b/")[-1]
        elif raw.startswith("@@"):
            flush()
            new_lineno = int(re.search(r"\+(\d+)", raw).group(1)) - 1
        elif raw.startswith("-") and not raw.startswith("---"):
            dels.extend(strings_in(raw[1:]))
        elif raw.startswith("+") and not raw.startswith("+++"):
            new_lineno += 1
            adds.extend((new_lineno, s) for s in strings_in(raw[1:]))
        elif current_file and not raw.startswith("\\"):
            new_lineno += 1
    flush()
    return pairs


def py_dq(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sq_or_none(text):
    if "'" in text or "\\" in text or "{" in text or "}" in text:
        return None
    return f"'{text}'"


def replace_in_line(line, frag_start, frag_end, en, issues, lineno, next_line):
    qpos, qchar = -1, ""
    for i in range(frag_start - 1, -1, -1):
        if line[i] in "\"'":
            qpos, qchar = i, line[i]
            break
    if qpos < 0:
        issues.append(f"{lineno}: no open quote {line!r}")
        return line
    prefix_f = qpos > 0 and line[qpos - 1] in "fF" and (
        qpos - 2 < 0 or not (line[qpos - 2].isalnum() or line[qpos - 2] == "_")
    )
    close, i = -1, qpos + 1
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == qchar:
            close = i
            break
        i += 1
    if close < 0:
        issues.append(f"{lineno}: no close quote {line!r}")
        return line
    whole = frag_start - 1 == qpos and frag_end == close

    if whole and not prefix_f:
        replacement = f"tr({py_dq(en)})"
        tail = line[close + 1:]
        tail_stripped = tail.strip()
        if tail_stripped.startswith((",", ")", "]", "}")):
            pass  # argument/value ended — no concatenation here
        elif tail_stripped.startswith(('"', "'")) or (
            not tail_stripped
            and (next_line or "").lstrip().startswith(('"', "'", "f\"", "f'", "+ ", "tr("))
        ):
            replacement += " +"
        return line[:qpos] + replacement + tail

    if prefix_f:
        key = sq_or_none(en)
        if key is None:
            issues.append(f"{lineno}: unsafe f-key {en!r}")
            return line
        return line[:frag_start] + "{tr(" + key + ")}" + line[frag_end:]

    issues.append(f"{lineno}: partial fragment in non-f string {en!r}")
    return line


def ensure_import(text):
    if "from utils.i18n import tr" in text:
        return text, False
    tree = ast.parse(text)
    last_import_end = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last_import_end = max(last_import_end, node.end_lineno)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # module docstring
        else:
            break
    if last_import_end == 0 and tree.body and isinstance(tree.body[0], ast.Expr):
        last_import_end = tree.body[0].end_lineno
    lines = text.splitlines(keepends=True)
    inject = "from utils.i18n import tr  # i18n: keys are the English source strings\n"
    lines.insert(last_import_end, inject)
    return "".join(lines), True


def main():
    pairs = collect_pairs()
    by_file = {}
    for f, lineno, text, old in pairs:
        by_file.setdefault(f, []).append((lineno, text, old))

    total, changed, issues, reverted = 0, [], [], []
    for f, items in sorted(by_file.items()):
        path = ROOT / f
        original = path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        per_line = {}
        for lineno, text, old in items:
            per_line.setdefault(lineno, []).append((text, old))
        file_changed = False
        for lineno, frags in sorted(per_line.items(), reverse=True):
            line = lines[lineno - 1]
            frags_sorted = sorted(
                frags, key=lambda t: line.find(t[0]) if t[0] in line else -1, reverse=True
            )
            consumed = len(line) + 1
            for text, old in frags_sorted:
                start = line.rfind(text, 0, consumed)
                if start < 0:
                    issues.append(f"{f}:{lineno}: fragment not found {text!r}")
                    continue
                end = start + len(text)
                consumed = start
                nxt = lines[lineno] if lineno < len(lines) else ""
                new_line = replace_in_line(line, start, end, old, issues, lineno, nxt)
                if new_line != line:
                    line = new_line
                    file_changed = True
                    total += 1
            lines[lineno - 1] = line
        if not file_changed:
            continue
        candidate = "".join(lines)
        try:
            compile(candidate, f, "exec")
        except SyntaxError as exc:
            reverted.append(f"{f}: pre-import line {exc.lineno} {exc.msg}")
            continue
        candidate, injected = ensure_import(candidate)
        try:
            compile(candidate, f, "exec")
        except SyntaxError as exc:
            reverted.append(f"{f}: post-import line {exc.lineno} {exc.msg}")
            continue
        path.write_text(candidate, encoding="utf-8", newline="")
        changed.append((f, injected))
    print(
        f"replacements: {total}  files changed: {len(changed)}  "
        f"reverted: {len(reverted)}  issues: {len(issues)}"
    )
    for f, inj in changed:
        print("CHANGED", f, "import-injected" if inj else "")
    for r in reverted:
        print("REVERTED", r)
    for s in issues[:40]:
        print("ISSUE", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())

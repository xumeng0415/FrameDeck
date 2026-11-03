"""Stage 2 of f-string i18n: template f-strings -> tr("EN {0}").format(...).

 zh_CN.json entries whose key/value contain expression placeholders are first
 normalised to positional {0}/{1} templates (expression sequences must match on
 both sides), then translated JoinedStr nodes are rewritten via the positional
 reverse lookup.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAIRS = json.loads((ROOT / "doc" / "l10n" / "extracted-pairs.json").read_text(encoding="utf-8"))

TARGETS = [
    "playback/player.py", "playback/reader.py", "utils/__init__.py",
    "widgets/__init__.py", "widgets/imageexport.py", "widgets/pdfreport.py",
    "widgets/playlist.py", "widgets/videoexport.py", "widgets/viewer.py",
    "widgets/widgetItems.py", "widgets/cachemanager.py", "widgets/ocio.py",
    "widgets/comments.py", "widgets/recaps.py", "widgets/shotstrip.py",
    "widgets/comboboxs.py", "widgets/dialogs.py", "widgets/fontdialog.py",
    "widgets/messagebox.py", "widgets/labels.py", "widgets/menus.py",
]

EXPR_RE = re.compile(r"\{([^{}]*)\}")


def has_cjk(t):
    return any("\u4e00" <= c <= "\u9fff" for c in t)


def positional(template):
    """Replace {expr(:spec)(!c)} with {i(:spec)(!c)}; return (positional, exprs)."""
    exprs = []

    def sub(match):
        inner = match.group(1)
        conv_spec = ""
        if "!" in inner:
            expr, conv_spec = inner.split("!", 1)
        elif ":" in inner and not inner.startswith("{"):
            # split on the LAST colon outside quotes/brackets is overkill here:
            # expression texts in this project never contain a bare ':' except
            # in slices/dicts, so only treat ':' as spec start when the left
            # side is a plain identifier chain or a call ending in ')'
            left, sep, right = inner.partition(":")
            if sep and re.fullmatch(r"[\w.\(\)\[\]]+", left or ""):
                expr, conv_spec = left, sep + right
            else:
                expr, conv_spec = inner, ""
        else:
            expr = inner
        exprs.append(expr.strip())
        return "{" + str(len(exprs) - 1) + conv_spec + "}"

    return EXPR_RE.sub(sub, template), exprs


def build_lookup():
    zh2en_pos = {}
    skipped = []
    for en, zh in PAIRS.items():
        if "{" not in en or not has_cjk(zh):
            continue
        en_pos, en_exprs = positional(en)
        zh_pos, zh_exprs = positional(zh)
        if [e.strip() for e in en_exprs] != [e.strip() for e in zh_exprs]:
            skipped.append((en, zh))
            continue
        zh2en_pos[zh_pos] = en_pos
    return zh2en_pos, skipped


def segment(source, node):
    return ast.get_source_segment(source, node)


def convert(node, source, zh2en_pos):
    zh_full, args = "", []
    for value in node.values:
        if isinstance(value, ast.Constant):
            zh_full += value.value
        elif isinstance(value, ast.FormattedValue):
            expr = segment(source, value.value)
            if expr is None:
                return None
            conv = {-1: "", 115: "!s", 114: "!r", 97: "!a"}.get(value.conversion or -1, "")
            spec = ":" + segment(source, value.format_spec) if value.format_spec is not None else ""
            zh_full += "{" + expr.strip() + conv + spec + "}"
            args.append(expr)
        else:
            return None
    zh_pos, zh_exprs = positional(zh_full)
    en_pos = zh2en_pos.get(zh_pos)
    if en_pos is None or '"' in en_pos or "\\" in en_pos:
        return None
    # expressions inside the node must match the template's sequence
    if [e for e in zh_exprs] != [a.strip() for a in args]:
        return None
    call = f'tr("{en_pos}")'
    if args:
        call += ".format(" + ", ".join(a.strip() for a in args) + ")"
    return call


def main():
    zh2en_pos, skipped = build_lookup()
    print(f"positional template pairs: {len(zh2en_pos)}  skipped: {len(skipped)}")
    for s in skipped[:10]:
        print("SKIP-PAIR", s)

    # refresh zh_CN.json with positional templates
    # merge into the existing file so manually-added keys survive a re-run
    _path = ROOT / "resources" / "i18n" / "zh_CN.json"
    zh = json.loads(_path.read_text(encoding="utf-8")) if _path.is_file() else {}
    zh.setdefault("$code", "zh_CN")
    zh.setdefault("$language", "简体中文")
    zh.setdefault("$note", "Key = original English source string; expression placeholders are positional {0}.")
    for en, zhv in PAIRS.items():
        if "{" in en and has_cjk(zhv):
            en_pos, en_exprs = positional(en)
            zh_pos, zh_exprs = positional(zhv)
            if [e.strip() for e in en_exprs] == [e.strip() for e in zh_exprs]:
                zh[en_pos] = zh_pos
                continue
        zh[en] = zhv
    _path.write_text(
        json.dumps(zh, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )
    print("zh_CN.json refreshed")

    total, changed, issues = 0, [], []
    for rel in TARGETS:
        path = ROOT / rel
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        spots = []
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr) and any(
                isinstance(v, ast.FormattedValue) for v in node.values
            ):
                call = convert(node, source, zh2en_pos)
                if call and call != segment(source, node):
                    spots.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, call))
        if not spots:
            continue
        lines = source.splitlines(keepends=True)
        # ast col_offset counts UTF-8 BYTES; convert to character offsets
        def to_char(lineno_1based, col_byte):
            raw = lines[lineno_1based - 1]
            return len(raw.encode("utf-8")[:col_byte].decode("utf-8"))

        for sl, sc_b, el, ec_b, call in sorted(spots, reverse=True):
            sc, ec = to_char(sl, sc_b), to_char(el, ec_b)
            if sl == el:
                line = lines[sl - 1]
                lines[sl - 1] = line[:sc] + call + line[ec:]
            else:
                first = lines[sl - 1]
                last = lines[el - 1]
                indent = first[: len(first) - len(first.lstrip())]
                lines[sl - 1] = first[:sc] + call + "\n"
                for k in range(sl, el - 1):
                    lines[k] = ""
                rest = last[ec:]
                lines[el - 1] = indent + rest.lstrip() if rest.strip() else ""
            total += 1
        candidate = "".join(lines)
        try:
            compile(candidate, rel, "exec")
        except SyntaxError as exc:
            issues.append(f"{rel}: line {exc.lineno} {exc.msg}")
            continue
        path.write_text(candidate, encoding="utf-8", newline="")
        changed.append(rel)
    print(f"converted: {total}  files: {len(changed)}  issues: {len(issues)}")
    for c in changed:
        print("CHANGED", c)
    for s in issues:
        print("ISSUE", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Extract EN->ZH translation pairs from `git diff baseline..HEAD`, pairing
deleted/addded string literals **within each diff hunk** so positional drift
between unrelated hunks cannot pollute the mapping."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
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


def has_ascii(t: str) -> bool:
    return any(c.isascii() and c.isalpha() for c in t)


def has_cjk(t: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in t)


def strings_in(line: str) -> list[str]:
    return [m.group(2) for m in STR_RE.finditer(line)]


def main() -> int:
    diff = subprocess.run(
        ["git", "diff", f"{BASELINE}..HEAD", "--unified=1", "--", *TARGETS],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    mapping: dict[str, str] = {}
    skipped: list[str] = []
    file_hunks: Counter = Counter()
    hunk: list[tuple[str, list[str], list[str]]] = []  # (file, dels, adds)
    current_file = None
    dels: list[str] = []
    adds: list[str] = []

    def flush():
        nonlocal dels, adds
        if current_file and (dels or adds):
            file_hunks[current_file] += 1
            if len(dels) == len(adds) and dels:
                for o, n in zip(dels, adds):
                    if o != n and has_ascii(o) and not has_cjk(o) and has_cjk(n):
                        if o in mapping and mapping[o] != n:
                            skipped.append(f"{current_file}: {o!r} -> {mapping[o]!r} | {n!r}")
                        mapping[o] = n
            elif dels or adds:
                skipped.append(f"{current_file}: unbalanced del={len(dels)} add={len(adds)}")
        dels, adds = [], []

    for line in diff.splitlines():
        if line.startswith("diff --git"):
            flush()
            current_file = line.split(" b/")[-1]
        elif line.startswith("@@"):
            flush()
        elif line.startswith("-") and not line.startswith("---"):
            dels.extend(strings_in(line[1:]))
        elif line.startswith("+") and not line.startswith("+++"):
            adds.extend(strings_in(line[1:]))
    flush()

    out = ROOT / "doc" / "l10n" / "extracted-pairs.json"
    out.write_text(json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"pairs: {len(mapping)}   hunks: {sum(file_hunks.values())}   skipped: {len(skipped)}")
    for s in skipped[:40]:
        print("SKIP", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())

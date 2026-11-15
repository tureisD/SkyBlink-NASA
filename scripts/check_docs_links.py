"""Check local Markdown destinations in docs and repository entry points.

Does not request external URLs, inspect anchor spelling or change any files.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
INLINE = re.compile(r"\]\(([^\n)]+)\)")
REFERENCE = re.compile(r"^\s*\[[^\]\n]+\]:\s*(.+)$", re.MULTILINE)
HTML = re.compile(r"(?:src|href)=[\"']([^\"']+)[\"']")


def main() -> int:
    files = sorted((ROOT / "docs").rglob("*.md")) + sorted(ROOT.glob("*.md"))
    failures = []
    checked = 0
    for path in files:
        content = path.read_text(encoding="utf-8")
        # Example code is not a rendered link and may intentionally use placeholders.
        content = re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", content)
        for pattern in (INLINE, REFERENCE, HTML):
            for match in pattern.finditer(content):
                value = match[1].strip()
                if value.startswith("<") and ">" in value:
                    value = value[1:value.index(">")]
                else:
                    value = value.split()[0] if value else ""
                if not value or value.startswith(("#", "//")) or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", value):
                    continue
                target = unquote(value.split("#", 1)[0].split("?", 1)[0])
                destination = ROOT / target.lstrip("/") if target.startswith("/") else path.parent / target
                checked += 1
                if not destination.exists():
                    line = content[:match.start()].count("\n") + 1
                    failures.append(f"{path.relative_to(ROOT).as_posix()}:{line}: {value}")
    for failure in failures:
        print("BROKEN:", failure)
    print(f"{'FAIL' if failures else 'PASS'}: {checked} local destinations in {len(files)} Markdown files; {len(failures)} missing")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())

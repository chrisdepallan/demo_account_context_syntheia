"""Print the size of the repo: files and bytes per top-level folder and per type.

Use it to check how big the corpus is before indexing it with the MCP
documentation server:

    python tools/repo_stats.py            # table per folder and extension
    python tools/repo_stats.py --headings # also count Markdown headings (chunks)

Only tracked-looking content is counted: ``.git`` and cache folders are skipped.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules"}
REPO_ROOT = Path(__file__).resolve().parent.parent


def iter_files(root: Path):
    """Yield every file under ``root``, skipping SKIP_DIRS."""
    for path in sorted(root.rglob("*")):
        if path.is_file() and not SKIP_DIRS.intersection(path.relative_to(root).parts):
            yield path


def count_headings(path: Path) -> int:
    """Count Markdown headings outside fenced code blocks.

    The indexer splits each Markdown file at its headings, so this is a
    rough count of the chunks the file produces.
    """
    in_fence = False
    count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith("#"):
            count += 1
    return count


def collect(root: Path, with_headings: bool) -> tuple[dict, dict, int]:
    """Return (per-folder stats, per-extension stats, heading count)."""
    by_folder: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_ext: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    headings = 0
    for path in iter_files(root):
        rel = path.relative_to(root)
        folder = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        if folder == "docs" and len(rel.parts) > 2:
            folder = f"docs/{rel.parts[1]}"
        size = path.stat().st_size
        ext = path.suffix or "(none)"
        for bucket, key in ((by_folder, folder), (by_ext, ext)):
            bucket[key][0] += 1
            bucket[key][1] += size
        if with_headings and path.suffix == ".md":
            headings += count_headings(path)
    return by_folder, by_ext, headings


def print_table(title: str, rows: dict[str, list[int]]) -> None:
    print(f"\n{title:<24}{'files':>8}{'KB':>10}")
    print("-" * 42)
    for key in sorted(rows):
        files, size = rows[key]
        print(f"{key:<24}{files:>8}{size / 1024:>10.1f}")
    total_files = sum(v[0] for v in rows.values())
    total_bytes = sum(v[1] for v in rows.values())
    print("-" * 42)
    print(f"{'total':<24}{total_files:>8}{total_bytes / 1024:>10.1f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--headings", action="store_true", help="count Markdown headings")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="folder to measure")
    args = parser.parse_args(argv)

    by_folder, by_ext, headings = collect(args.root, args.headings)
    print_table("Folder", by_folder)
    print_table("Extension", by_ext)
    if args.headings:
        print(f"\nMarkdown headings (approximate chunks): {headings}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

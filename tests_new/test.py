"""Generate/check structured markdown JSON snapshots for sample HWPX files.

Usage:
    uv run python tests_new/test.py
    uv run python tests_new/test.py --check
    uv run python tests_new/test.py --input-dir tests_new/input --output-dir tests_new/output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from hwpx import HwpxDocument
from hwpx.tools.exporter import export_markdown_structured


def _build_summary(mapping: dict[str, str], output_path: Path) -> dict[str, Any]:
    preview_items = list(mapping.items())[:8]
    return {
        "count": len(mapping),
        "preview": [{"id": key, "text": value} for key, value in preview_items],
        "output": str(output_path),
    }


def _render_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _load_hwpx_structured(
    path: Path,
    *,
    include_page_index: bool = False,
    paragraph_level_only: bool = False,
) -> dict[str, str]:
    document = HwpxDocument.open(path)
    try:
        return export_markdown_structured(
            document,
            include_page_index=include_page_index,
            paragraph_level_only=paragraph_level_only,
        )
    finally:
        document.close()


def _process_file(
    path: Path,
    output_dir: Path,
    check: bool,
    *,
    include_page_index: bool = False,
    paragraph_level_only: bool = False,
) -> tuple[bool, dict[str, Any]]:
    mapping = _load_hwpx_structured(
        path,
        include_page_index=include_page_index,
        paragraph_level_only=paragraph_level_only,
    )
    output_path = output_dir / f"{path.stem}.structured.json"
    content = _render_json(mapping)

    changed = False
    if check:
        if not output_path.exists() or output_path.read_text(encoding="utf-8") != content:
            changed = True
    else:
        output_path.write_text(content, encoding="utf-8")

    return changed, _build_summary(mapping, output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or check structured JSON snapshots for HWPX samples."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("tests_new/input"),
        help="Directory containing .hwpx sample files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests_new/output"),
        help="Directory for generated snapshot JSON files.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write files; fail if generated content differs from snapshots.",
    )
    parser.add_argument(
        "--include-page-index",
        action="store_true",
        help="Include explicit page index segment (pgN) in IDs.",
    )
    parser.add_argument(
        "--paragraph-level-only",
        action="store_true",
        help="Flatten output to paragraph IDs only and exclude table entries.",
    )
    args = parser.parse_args()

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    check: bool = args.check
    include_page_index: bool = args.include_page_index
    paragraph_level_only: bool = args.paragraph_level_only

    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 2

    hwpx_files = sorted(input_dir.glob("*.hwpx"))
    if not hwpx_files:
        print(f"No .hwpx files found in: {input_dir}", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {}
    changed_files: list[str] = []

    for path in hwpx_files:
        changed, item_summary = _process_file(
            path,
            output_dir,
            check,
            include_page_index=include_page_index,
            paragraph_level_only=paragraph_level_only,
        )
        summary[path.name] = item_summary
        if changed:
            changed_files.append(path.name)
        status = "DIFF" if changed else "OK"
        print(f"[{status}] {path.name} -> {item_summary['count']} fragments")

    summary_path = output_dir / "structured_summary.json"
    summary_content = _render_json(summary)
    summary_changed = False
    if check:
        if not summary_path.exists() or summary_path.read_text(encoding="utf-8") != summary_content:
            summary_changed = True
    else:
        summary_path.write_text(summary_content, encoding="utf-8")

    if summary_changed:
        changed_files.append(summary_path.name)

    if check and changed_files:
        print("\nChanged snapshots detected:")
        for name in changed_files:
            print(f"- {name}")
        return 1

    mode = "checked" if check else "written"
    print(f"\nDone: {len(hwpx_files)} files {mode}.")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

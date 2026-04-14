#!/usr/bin/env python3
"""Write a dashboard export markdown file into the wiki syntheses folder."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
WIKI_ROOT = SCRIPT_DIR.parent / "Roofing company" / "wiki"
SYNTHESIS_DIR = WIKI_ROOT / "syntheses"


def read_source(path: str | None) -> tuple[str, str]:
    if path and path != "-":
        source_path = Path(path).expanduser()
        return source_path.read_text(encoding="utf-8"), source_path.name

    if sys.stdin.isatty():
        raise SystemExit("Provide a markdown file path or pipe markdown into stdin.")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sys.stdin.read(), f"dashboard-export-{stamp}.md"


def resolve_output(source_name: str, explicit_output: str | None) -> Path:
    if explicit_output:
        output = Path(explicit_output).expanduser()
        if output.exists() and output.is_dir():
            return output / source_name
        if explicit_output.endswith(("/", "\\")):
            return output / source_name
        return output

    return SYNTHESIS_DIR / source_name


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a dashboard export markdown file into the roofing wiki."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="-",
        help="Markdown file to copy, or - to read from stdin.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional destination file path. Defaults to wiki/syntheses/<source name>.",
    )
    args = parser.parse_args()

    content, source_name = read_source(args.source)
    output_path = resolve_output(source_name, args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

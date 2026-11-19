"""Subprocess entry point for export composition.

Invocation: python -m app.render.export_runner --input <json> --output <dir> --format PPTX
Exit codes: 0 success, 2 validation failure, 3 composition failure, 4 internal failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.render import pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bound PPT export renderer")
    parser.add_argument("--input", required=True, help="Render input JSON path")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--format", required=True, choices=sorted(pipeline.OUTPUT_NAMES))
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    input_path = Path(args.input)
    output_dir = Path(args.output)
    try:
        data: Any = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return 2
        pages = data.get("pages")
        if not isinstance(pages, list) or not pages:
            return 2
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / pipeline.output_name(args.format)
        result = pipeline.render_document(data, output_path, args.format)
        if not output_path.is_file() or output_path.stat().st_size <= 0:
            return 3
        summary = {
            "ok": True,
            "format": args.format.upper(),
            "pagesRendered": int(result.get("pages", len(pages))),
            "byteSize": output_path.stat().st_size,
        }
        print(json.dumps(summary, separators=(",", ":")))
        return 0
    except ValueError:
        return 2
    except RuntimeError:
        return 3
    except Exception:  # noqa: BLE001 - exit code only; never print content or tracebacks
        return 4


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

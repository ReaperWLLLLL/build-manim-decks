#!/usr/bin/env python3
"""Normalize PDF, Markdown, LaTeX, or plain-text sources into reviewable Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".tex"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_stem(path: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("-")
    return slug or "source"


def extract_text_source(source: Path, output: Path) -> dict[str, Any]:
    text = source.read_text(encoding="utf-8", errors="replace")
    output.write_text(
        f"# Extracted source: {source.name}\n\n"
        f"- Original path: `{source}`\n"
        f"- SHA-256: `{sha256(source)}`\n\n"
        "---\n\n"
        + text,
        encoding="utf-8",
    )
    return {"pages": None, "images": [], "characters": len(text)}


def extract_pdf_source(
    source: Path, output: Path, *, image_dir: Path | None
) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF extraction") from exc

    try:
        document = PdfReader(source)
    except (OSError, PyPdfError) as exc:
        raise RuntimeError(f"could not read PDF: {exc}") from exc

    page_count = len(document.pages)
    lines = [
        f"# Extracted source: {source.name}",
        "",
        f"- Original path: `{source}`",
        f"- SHA-256: `{sha256(source)}`",
        f"- Pages: {page_count}",
        "",
        "---",
        "",
    ]
    extracted_images: list[str] = []
    character_count = 0

    if image_dir is not None:
        image_dir.mkdir(parents=True, exist_ok=True)

    for page_number, page in enumerate(document.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except (KeyError, PyPdfError, ValueError):
            text = ""
        character_count += len(text)
        lines.extend([f"## Page {page_number}", "", text or "_[No extractable text]_", ""])

        if image_dir is None:
            continue
        seen_images: set[str] = set()
        try:
            page_images = page.images
        except (KeyError, PyPdfError, ValueError):
            page_images = []
        for image_index, image in enumerate(page_images, start=1):
            image_bytes = image.data
            image_digest = hashlib.sha256(image_bytes).hexdigest()
            if image_digest in seen_images:
                continue
            seen_images.add(image_digest)
            extension = Path(image.name).suffix.lstrip(".") or "bin"
            filename = f"{safe_stem(source)}-p{page_number:03d}-img{image_index:02d}.{extension}"
            destination = image_dir / filename
            destination.write_bytes(image_bytes)
            extracted_images.append(str(destination))
            relative_image = destination.relative_to(output.parent)
            lines.extend(
                [f"![Extracted image on page {page_number}]({relative_image.as_posix()})", ""]
            )

    output.write_text("\n".join(lines), encoding="utf-8")
    return {
        "pages": page_count,
        "images": extracted_images,
        "characters": character_count,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--extract-images", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"schema_version": "0.1", "sources": []}
    failures = 0

    for source_arg in args.sources:
        source = source_arg.resolve()
        if not source.is_file():
            print(f"Missing source: {source}", file=sys.stderr)
            failures += 1
            continue
        suffix = source.suffix.lower()
        output = output_dir / f"{safe_stem(source)}.extracted.md"
        try:
            if suffix == ".pdf":
                image_dir = output_dir / "images" if args.extract_images else None
                details = extract_pdf_source(source, output, image_dir=image_dir)
            elif suffix in TEXT_SUFFIXES:
                details = extract_text_source(source, output)
            else:
                raise RuntimeError(
                    f"Unsupported source type {suffix!r}; use PDF, Markdown, LaTeX, or text"
                )
        except (OSError, RuntimeError) as exc:
            print(f"Failed to extract {source}: {exc}", file=sys.stderr)
            failures += 1
            continue

        record = {
            "source": str(source),
            "sha256": sha256(source),
            "extracted_markdown": str(output),
            **details,
        }
        manifest["sources"].append(record)
        print(f"Extracted {source.name} -> {output}")

    manifest_path = output_dir / "source-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote manifest: {manifest_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

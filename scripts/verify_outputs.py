#!/usr/bin/env python3
"""Verify final HTML, video-based PPTX, PDF, and speech deliverables."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from common import SkillInputError, load_structured_file, project_root_for
from validate_deck import validate_deck


@dataclass
class Check:
    output: str
    severity: str
    ok: bool
    message: str


def check_html(path: Path, expected_slides: list[dict[str, Any]]) -> list[Check]:
    if not path.is_file():
        return [Check("html", "blocker", False, f"missing file: {path}")]
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r'<script id="deck-data" type="application/json">(.*?)</script>',
        text,
        flags=re.DOTALL,
    )
    payload: list[dict[str, Any]] = []
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, list):
                payload = [entry for entry in parsed if isinstance(entry, dict)]
        except json.JSONDecodeError:
            pass
    actual_scene_order = list(dict.fromkeys(str(entry.get("scene")) for entry in payload))
    expected_scene_order = [str(slide["scene_class"]) for slide in expected_slides]
    notes_by_scene = {
        str(entry.get("scene")): str(entry.get("notes") or "").strip() for entry in payload
    }
    expected_notes = {
        str(slide["scene_class"]): str(slide["notes"]).strip() for slide in expected_slides
    }

    checks = [
        Check("html", "blocker", path.stat().st_size > 1024, f"size={path.stat().st_size} bytes"),
        Check(
            "html",
            "blocker",
            'id="deck-data"' in text,
            "self-contained player data present",
        ),
        Check(
            "html",
            "blocker",
            "<video" in text or "data:video" in text,
            "embedded or linked video media present",
        ),
        Check(
            "html",
            "blocker",
            re.search(r"(?:src|href)=[\"']https?://", text, flags=re.IGNORECASE) is None,
            "no external script, style, or media dependencies",
        ),
        Check(
            "html",
            "blocker",
            actual_scene_order == expected_scene_order,
            f"scene order={actual_scene_order}, expected={expected_scene_order}",
        ),
        Check(
            "html",
            "major",
            notes_by_scene == expected_notes,
            "speaker notes match deck.yaml",
        ),
    ]
    return checks


def check_pptx(path: Path, expected_slides: int, expected_videos: int) -> list[Check]:
    if not path.is_file():
        return [Check("pptx", "blocker", False, f"missing file: {path}")]
    try:
        with zipfile.ZipFile(path) as archive:
            corrupt = archive.testzip()
            names = archive.namelist()
    except (OSError, zipfile.BadZipFile) as exc:
        return [Check("pptx", "blocker", False, f"invalid OOXML archive: {exc}")]

    slide_files = [
        name
        for name in names
        if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
    ]
    video_files = [
        name
        for name in names
        if name.startswith("ppt/media/")
        and Path(name).suffix.lower() in {".mp4", ".mov", ".m4v", ".webm"}
    ]
    note_files = [
        name
        for name in names
        if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", name)
    ]
    return [
        Check("pptx", "blocker", corrupt is None, f"archive integrity: {corrupt or 'ok'}"),
        Check(
            "pptx",
            "blocker",
            len(slide_files) == expected_slides,
            f"slides={len(slide_files)}, expected={expected_slides}",
        ),
        Check(
            "pptx",
            "blocker",
            len(video_files) >= expected_videos,
            f"video media={len(video_files)}, expected at least={expected_videos}",
        ),
        Check(
            "pptx",
            "major",
            len(note_files) >= expected_slides,
            f"notes slides={len(note_files)}, expected at least={expected_slides}",
        ),
    ]


def pdf_page_count(path: Path) -> int | None:
    try:
        import fitz

        with fitz.open(path) as document:
            return document.page_count
    except (ImportError, OSError, RuntimeError):
        result = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, check=False
        )
        if result.returncode:
            return None
        match = re.search(r"^Pages:\s+(\d+)$", result.stdout, flags=re.MULTILINE)
        return int(match.group(1)) if match else None


def check_pdf(path: Path, expected_pages: int) -> list[Check]:
    if not path.is_file():
        return [Check("pdf", "blocker", False, f"missing file: {path}")]
    pages = pdf_page_count(path)
    return [
        Check("pdf", "blocker", path.stat().st_size > 512, f"size={path.stat().st_size} bytes"),
        Check(
            "pdf",
            "blocker",
            pages == expected_pages,
            f"pages={pages if pages is not None else 'unknown'}, expected={expected_pages}",
        ),
    ]


def check_speech(path: Path, expected_slides: int) -> list[Check]:
    if not path.is_file():
        return [Check("speech", "blocker", False, f"missing file: {path}")]
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = re.findall(r"^##\s+s\d{2,3}\s+—", text, flags=re.MULTILINE)
    return [
        Check(
            "speech",
            "blocker",
            len(sections) == expected_slides,
            f"slide sections={len(sections)}, expected={expected_slides}",
        ),
        Check(
            "speech",
            "major",
            "## Timing summary" in text,
            "timing summary present",
        ),
    ]


def report_markdown(checks: list[Check]) -> str:
    lines = [
        "# Deliverable verification",
        "",
        "| Output | Severity | Status | Evidence |",
        "|---|---|---|---|",
    ]
    for check in checks:
        lines.append(
            f"| {check.output} | {check.severity} | {'PASS' if check.ok else 'FAIL'} | {check.message} |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        data = load_structured_file(args.deck)
    except SkillInputError as exc:
        print(exc)
        return 1
    errors = [
        finding
        for finding in validate_deck(data, deck_path=args.deck, check_paths=False)
        if finding.severity == "error"
    ]
    if errors:
        print("deck.yaml must pass validation before output verification")
        return 1

    root = project_root_for(args.deck)
    expected_slides = len(data["slides"])
    expected_videos = sum(slide["visual_mode"] in {"manim", "media", "hybrid"} for slide in data["slides"])
    checks: list[Check] = []
    checks.extend(check_html(root / data["outputs"]["html"], data["slides"]))
    checks.extend(check_pptx(root / data["outputs"]["pptx"], expected_slides, expected_videos))
    checks.extend(check_pdf(root / data["outputs"]["pdf"], expected_slides))
    checks.extend(check_speech(root / data["outputs"]["speech"], expected_slides))

    report = root / "qa" / "deliverable-verification.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(report_markdown(checks) + "\n", encoding="utf-8")

    if args.json:
        print(
            json.dumps(
                {"ok": all(check.ok for check in checks), "checks": [asdict(check) for check in checks]},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for check in checks:
            print(f"[{'PASS' if check.ok else 'FAIL'}] {check.output}: {check.message}")
        print(f"Wrote verification report: {report}")

    blockers = [check for check in checks if not check.ok and check.severity == "blocker"]
    majors = [check for check in checks if not check.ok and check.severity == "major"]
    return 1 if blockers or majors else 0


if __name__ == "__main__":
    raise SystemExit(main())

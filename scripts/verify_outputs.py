#!/usr/bin/env python3
"""Verify final HTML, video-based PPTX, PDF, and speech deliverables."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from common import SkillInputError, load_structured_file, project_root_for
from postprocess_pptx import resolve_target
from validate_deck import validate_deck
from write_speech import estimate_minutes


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


def check_pptx(path: Path, expected_slides: list[dict[str, Any]]) -> list[Check]:
    if not path.is_file():
        return [Check("pptx", "blocker", False, f"missing file: {path}")]
    expected_count = len(expected_slides)
    expected_videos = sum(
        slide["visual_mode"] in {"manim", "media", "hybrid"}
        for slide in expected_slides
    )
    try:
        with zipfile.ZipFile(path) as archive:
            corrupt = archive.testzip()
            names = archive.namelist()
            slide_files = sorted(
                (
                    name
                    for name in names
                    if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
                ),
                key=lambda name: int(re.search(r"(\d+)", Path(name).stem).group(1)),
            )
            poster_members: list[str] = []
            autoplay_count = 0
            notes_match_count = 0
            blank_posters: list[str] = []
            static_fallback_count = 0

            for index, slide_file in enumerate(slide_files, start=1):
                slide_xml = ET.fromstring(archive.read(slide_file))
                p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
                a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
                if any(
                    condition.get("delay") == "0"
                    for condition in slide_xml.findall(f".//{{{p_ns}}}video//{{{p_ns}}}cond")
                ):
                    autoplay_count += 1

                shape_tree = slide_xml.find(f".//{{{p_ns}}}spTree")
                if shape_tree is not None:
                    video_positions: list[int] = []
                    fallback_positions: list[int] = []
                    for position, node in enumerate(list(shape_tree)):
                        if node.tag != f"{{{p_ns}}}pic":
                            continue
                        properties = node.find(f".//{{{p_ns}}}cNvPr")
                        if (
                            properties is not None
                            and properties.get("name", "").startswith("manim-static-poster-")
                        ):
                            fallback_positions.append(position)
                        if node.find(f".//{{{a_ns}}}videoFile") is not None:
                            video_positions.append(position)
                    if (
                        video_positions
                        and fallback_positions
                        and min(fallback_positions) < min(video_positions)
                    ):
                        static_fallback_count += 1

                rel_path = f"ppt/slides/_rels/slide{index}.xml.rels"
                if rel_path in names:
                    rel_root = ET.fromstring(archive.read(rel_path))
                    has_video = any(
                        relationship.get("Type", "").endswith("/video")
                        for relationship in rel_root
                    )
                    for relationship in rel_root:
                        if has_video and relationship.get("Type", "").endswith("/image"):
                            target = relationship.get("Target", "")
                            poster_members.append(resolve_target(rel_path, target))

                note_path = f"ppt/notesSlides/notesSlide{index}.xml"
                if note_path in names and index <= expected_count:
                    note_root = ET.fromstring(archive.read(note_path))
                    drawing_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
                    actual_notes = " ".join(
                        text.strip()
                        for node in note_root.findall(f".//{{{drawing_ns}}}t")
                        if (text := node.text or "").strip()
                    )
                    expected_notes = " ".join(str(expected_slides[index - 1]["notes"]).split())
                    if " ".join(actual_notes.split()) == expected_notes:
                        notes_match_count += 1

            from PIL import Image, ImageStat

            for member in poster_members:
                if member not in names:
                    blank_posters.append(f"missing:{member}")
                    continue
                with Image.open(BytesIO(archive.read(member))) as poster:
                    stat = ImageStat.Stat(poster.convert("L"))
                    mean, stddev = float(stat.mean[0]), float(stat.stddev[0])
                if stddev < 2.0 and (mean < 5.0 or mean > 250.0):
                    blank_posters.append(member)

            presentation_root = ET.fromstring(archive.read("ppt/presentation.xml"))
            p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
            size_node = presentation_root.find(f"{{{p_ns}}}sldSz")
            slide_ratio = None
            if size_node is not None:
                width = int(size_node.get("cx", "0"))
                height = int(size_node.get("cy", "0"))
                slide_ratio = width / height if height else None
    except (OSError, zipfile.BadZipFile) as exc:
        return [Check("pptx", "blocker", False, f"invalid OOXML archive: {exc}")]

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
            len(slide_files) == expected_count,
            f"slides={len(slide_files)}, expected={expected_count}",
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
            len(note_files) >= expected_count,
            f"notes slides={len(note_files)}, expected at least={expected_count}",
        ),
        Check(
            "pptx",
            "major",
            notes_match_count == expected_count,
            f"speaker notes matching deck.yaml={notes_match_count}/{expected_count}",
        ),
        Check(
            "pptx",
            "blocker",
            len(poster_members) == expected_videos
            and len(set(poster_members)) == expected_videos,
            f"unique video poster images={len(set(poster_members))}, expected={expected_videos}",
        ),
        Check(
            "pptx",
            "major",
            not blank_posters,
            f"blank or missing poster images={blank_posters or 'none'}",
        ),
        Check(
            "pptx",
            "major",
            autoplay_count == expected_videos,
            f"automatic video playback={autoplay_count}, expected={expected_videos}",
        ),
        Check(
            "pptx",
            "major",
            static_fallback_count == expected_videos,
            f"static poster fallbacks behind video={static_fallback_count}, "
            f"expected={expected_videos}",
        ),
        Check(
            "pptx",
            "blocker",
            slide_ratio is not None and abs(slide_ratio - 16 / 9) < 0.01,
            f"slide aspect ratio={slide_ratio:.4f}" if slide_ratio else "slide size unavailable",
        ),
    ]


def pdf_page_info(path: Path) -> tuple[int | None, list[tuple[float, float]]]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError

        document = PdfReader(path)
        sizes = [
            (float(page.mediabox.width), float(page.mediabox.height))
            for page in document.pages
        ]
        return len(document.pages), sizes
    except (ImportError, OSError, PyPdfError, TypeError, ValueError):
        result = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, check=False
        )
        if result.returncode:
            return None, []
        match = re.search(r"^Pages:\s+(\d+)$", result.stdout, flags=re.MULTILINE)
        return (int(match.group(1)) if match else None), []


def check_pdf(path: Path, expected_pages: int) -> list[Check]:
    if not path.is_file():
        return [Check("pdf", "blocker", False, f"missing file: {path}")]
    pages, sizes = pdf_page_info(path)
    consistent = len(set((round(width, 2), round(height, 2)) for width, height in sizes)) <= 1
    widescreen = bool(sizes) and all(
        height > 0 and abs(width / height - 16 / 9) < 0.01 for width, height in sizes
    )
    return [
        Check("pdf", "blocker", path.stat().st_size > 512, f"size={path.stat().st_size} bytes"),
        Check(
            "pdf",
            "blocker",
            pages == expected_pages,
            f"pages={pages if pages is not None else 'unknown'}, expected={expected_pages}",
        ),
        Check(
            "pdf",
            "blocker",
            widescreen and consistent,
            f"consistent 16:9 page sizes={sizes[:3] if sizes else 'unavailable'}",
        ),
    ]


def check_speech(path: Path, data: dict[str, Any]) -> list[Check]:
    if not path.is_file():
        return [Check("speech", "blocker", False, f"missing file: {path}")]
    text = path.read_text(encoding="utf-8", errors="replace")
    expected_slides = len(data["slides"])
    sections = re.findall(r"^##\s+s\d{2,3}\s+\|", text, flags=re.MULTILINE)
    notes_present = sum(
        slide["notes"].strip() in text for slide in data["slides"] if slide["notes"].strip()
    )
    estimated_minutes = sum(
        estimate_minutes(slide["notes"], data["project"]["language"])
        for slide in data["slides"]
    )
    target_minutes = float(data["project"]["duration_minutes"])
    timing_delta = (
        abs(estimated_minutes - target_minutes) / target_minutes if target_minutes else 1.0
    )
    slide_timing_outliers: list[str] = []
    for slide in data["slides"]:
        target_seconds = float(slide["duration_seconds"])
        estimated_seconds = (
            estimate_minutes(slide["notes"], data["project"]["language"]) * 60.0
        )
        if target_seconds and abs(estimated_seconds - target_seconds) / target_seconds > 0.35:
            slide_timing_outliers.append(slide["id"])
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
        Check(
            "speech",
            "major",
            notes_present == expected_slides,
            f"manuscript sections containing deck notes={notes_present}/{expected_slides}",
        ),
        Check(
            "speech",
            "major",
            timing_delta <= 0.10,
            f"estimated={estimated_minutes:.2f}min, target={target_minutes:.2f}min, "
            f"variance={timing_delta:.1%}",
        ),
        Check(
            "speech",
            "major",
            not slide_timing_outliers,
            f"slide timing outliers beyond 35%={slide_timing_outliers or 'none'}",
        ),
    ]


def check_qa(root: Path, expected_slides: int) -> list[Check]:
    final_dir = root / "qa" / "final"
    automated = final_dir / "automated-report.md"
    contact_sheet = final_dir / "contact-sheet.png"
    frames_dir = final_dir / "frames"
    human_report = root / "qa" / "report.md"
    text_report = root / "qa" / "text-review.md"

    automated_text = (
        automated.read_text(encoding="utf-8", errors="replace")
        if automated.is_file()
        else ""
    )
    human_text = (
        human_report.read_text(encoding="utf-8", errors="replace")
        if human_report.is_file()
        else ""
    )
    text_review = (
        text_report.read_text(encoding="utf-8", errors="replace")
        if text_report.is_file()
        else ""
    )
    frames = list(frames_dir.glob("*.png")) if frames_dir.is_dir() else []
    approved = re.search(
        r"^Final visual approval:\s*approved\s*$",
        human_text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text_approved = re.search(
        r"^Text review:\s*approved\s*$",
        text_review,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return [
        Check(
            "qa",
            "blocker",
            text_approved is not None,
            "audience-facing text review approved",
        ),
        Check(
            "qa",
            "blocker",
            automated.is_file()
            and "- Blocking findings: 0" in automated_text
            and "- Major findings: 0" in automated_text,
            "final automated report exists with zero blocker and major findings",
        ),
        Check(
            "qa",
            "blocker",
            contact_sheet.is_file() and contact_sheet.stat().st_size > 1024,
            f"final contact sheet={'present' if contact_sheet.is_file() else 'missing'}",
        ),
        Check(
            "qa",
            "blocker",
            len(frames) >= expected_slides * 3,
            f"final review frames={len(frames)}, expected at least={expected_slides * 3}",
        ),
        Check(
            "qa",
            "blocker",
            approved is not None,
            "human or vision-agent final approval recorded",
        ),
    ]


def check_rebuild(root: Path) -> list[Check]:
    path = root / "deliverables" / "rebuild.md"
    if not path.is_file():
        return [Check("rebuild", "blocker", False, f"missing file: {path}")]
    text = path.read_text(encoding="utf-8", errors="replace")
    required_commands = {
        "preflight.py",
        "validate_deck.py",
        "render_deck.py",
        "visual_qa.py",
        "verify_outputs.py",
    }
    missing = sorted(command for command in required_commands if command not in text)
    machine_path = re.search(r"/(?:Users|home)/|[A-Za-z]:\\Users\\", text)
    return [
        Check(
            "rebuild",
            "blocker",
            not missing,
            f"required rebuild commands missing={missing or 'none'}",
        ),
        Check(
            "rebuild",
            "major",
            machine_path is None and "Replace this placeholder" not in text,
            "commands are machine-independent and contain no placeholder",
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
        for finding in validate_deck(data, deck_path=args.deck, check_paths=True)
        if finding.severity == "error"
    ]
    if errors:
        print("deck.yaml must pass validation before output verification")
        return 1

    root = project_root_for(args.deck)
    expected_slides = len(data["slides"])
    checks: list[Check] = []
    checks.extend(check_html(root / data["outputs"]["html"], data["slides"]))
    checks.extend(check_pptx(root / data["outputs"]["pptx"], data["slides"]))
    checks.extend(check_pdf(root / data["outputs"]["pdf"], expected_slides))
    checks.extend(check_speech(root / data["outputs"]["speech"], data))
    checks.extend(check_qa(root, expected_slides))
    checks.extend(check_rebuild(root))

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

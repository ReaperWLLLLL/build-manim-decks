#!/usr/bin/env python3
"""Inspect rendered slide videos, extract review frames, and build a QA contact sheet."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common import SkillInputError, load_structured_file, project_root_for
from validate_deck import validate_deck


@dataclass
class Finding:
    severity: str
    slide_id: str
    evidence: str
    message: str


def probe_video(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames:format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or "ffprobe failed").strip())
    payload = json.loads(result.stdout)
    stream = (payload.get("streams") or [{}])[0]
    duration = float((payload.get("format") or {}).get("duration") or 0)
    return {
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "frames": int(stream.get("nb_frames") or 0) if str(stream.get("nb_frames", "")).isdigit() else None,
        "duration": duration,
    }


def extract_frame(video: Path, timestamp: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, timestamp):.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-y",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or not output.is_file():
        raise RuntimeError((result.stderr or "frame extraction failed").strip())


def image_statistics(path: Path) -> tuple[float, float]:
    from PIL import Image, ImageStat

    with Image.open(path) as image:
        grayscale = image.convert("L")
        stat = ImageStat.Stat(grayscale)
        return float(stat.mean[0]), float(stat.stddev[0])


def content_bounds(path: Path) -> tuple[int, int, int, int] | None:
    """Estimate non-background bounds using the four corner colors."""
    from PIL import Image, ImageChops

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        corners = [
            rgb.getpixel((0, 0)),
            rgb.getpixel((width - 1, 0)),
            rgb.getpixel((0, height - 1)),
            rgb.getpixel((width - 1, height - 1)),
        ]
        background = tuple(sorted(channel)[len(channel) // 2] for channel in zip(*corners))
        flat = Image.new("RGB", rgb.size, background)
        difference = ImageChops.difference(rgb, flat).convert("L")
        mask = difference.point(lambda value: 255 if value > 10 else 0)
        return mask.getbbox()


def build_contact_sheet(frames: list[tuple[str, Path]], output: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    if not frames:
        raise RuntimeError("no frames available for a contact sheet")
    thumb_width, thumb_height, label_height = 480, 270, 36
    columns = 3
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "#111111")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, (label, frame_path) in enumerate(frames):
        row, column = divmod(index, columns)
        x = column * thumb_width
        y = row * (thumb_height + label_height)
        with Image.open(frame_path) as source:
            thumb = source.convert("RGB")
            thumb.thumbnail((thumb_width, thumb_height))
            canvas = Image.new("RGB", (thumb_width, thumb_height), "black")
            canvas.paste(thumb, ((thumb_width - thumb.width) // 2, (thumb_height - thumb.height) // 2))
            sheet.paste(canvas, (x, y))
        draw.text((x + 8, y + thumb_height + 7), label, fill="white", font=font)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def video_candidates(slides_folder: Path, scene_class: str) -> list[Path]:
    scene_dir = slides_folder / "files" / scene_class
    if not scene_dir.is_dir():
        return []
    return sorted(path for path in scene_dir.rglob("*") if path.suffix.lower() in {".mp4", ".mov", ".webm"})


def render_report(findings: list[Finding], metadata: list[dict[str, Any]]) -> str:
    lines = ["# Automated visual QA report", ""]
    blockers = sum(item.severity == "blocker" for item in findings)
    majors = sum(item.severity == "major" for item in findings)
    lines.extend(
        [
            f"- Blocking findings: {blockers}",
            f"- Major findings: {majors}",
            f"- Videos inspected: {len(metadata)}",
            "",
        ]
    )
    if findings:
        lines.append("## Findings")
        lines.append("")
        for item in findings:
            lines.extend(
                [
                    f"### {item.slide_id} — {item.severity}",
                    "",
                    f"- Evidence: `{item.evidence}`" if item.evidence else "- Evidence: unavailable",
                    f"- Finding: {item.message}",
                    "- Status: open",
                    "",
                ]
            )
    else:
        lines.extend(["## Findings", "", "No automated blocking or major findings.", ""])

    lines.extend(
        [
            "## Manual review required",
            "",
            "Inspect the profile contact sheet and representative full-resolution frames for:",
            "",
            "- text and equation clipping;",
            "- collisions and safe margins;",
            "- contrast and color-independent meaning;",
            "- visual hierarchy and density;",
            "- animation order, pacing, and stable final frames;",
            "- scientific accuracy and evidence alignment.",
            "",
            "Automated success does not constitute final visual approval.",
            "",
            "## Media inventory",
            "",
            "| Slide | File | Resolution | Duration | Frames |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for item in metadata:
        lines.append(
            f"| {item['slide_id']} | `{item['file']}` | {item['width']}x{item['height']} | "
            f"{item['duration']:.2f}s | {item['frames'] or 'unknown'} |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--profile", choices=["draft", "final"], default="draft")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        print("ffmpeg and ffprobe are required", file=sys.stderr)
        return 1
    try:
        data = load_structured_file(args.deck)
    except SkillInputError as exc:
        print(exc, file=sys.stderr)
        return 1
    errors = [
        item
        for item in validate_deck(data, deck_path=args.deck, check_paths=False)
        if item.severity == "error"
    ]
    if errors:
        print("deck.yaml must pass validation before visual QA", file=sys.stderr)
        return 1

    root = project_root_for(args.deck)
    slides_folder = root / "build" / args.profile / "slides"
    qa_dir = root / "qa" / args.profile
    frame_dir = qa_dir / "frames"
    findings: list[Finding] = []
    frames: list[tuple[str, Path]] = []
    metadata: list[dict[str, Any]] = []

    for slide in data["slides"]:
        slide_id = slide["id"]
        candidates = video_candidates(slides_folder, slide["scene_class"])
        if not candidates:
            findings.append(
                Finding("blocker", slide_id, "", f"no rendered video for {slide['scene_class']}")
            )
            continue
        if len(candidates) > 1:
            findings.append(
                Finding(
                    "major",
                    slide_id,
                    str(candidates[0]),
                    f"expected one logical video but found {len(candidates)}; verify segment mapping",
                )
            )

        video = candidates[-1]
        try:
            info = probe_video(video)
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            findings.append(Finding("blocker", slide_id, str(video), f"cannot decode video: {exc}"))
            continue
        metadata.append({"slide_id": slide_id, "file": str(video), **info})

        if info["duration"] <= 0:
            findings.append(Finding("blocker", slide_id, str(video), "video duration is zero"))
            continue
        if not info["height"] or abs(info["width"] / info["height"] - 16 / 9) > 0.02:
            findings.append(
                Finding(
                    "blocker",
                    slide_id,
                    str(video),
                    f"video is not 16:9 ({info['width']}x{info['height']})",
                )
            )

        timestamps = {
            "first": min(0.1, info["duration"] / 4),
            "middle": info["duration"] / 2,
            "last": max(0.0, info["duration"] - 0.1),
        }
        for label, timestamp in timestamps.items():
            frame_path = frame_dir / f"{slide_id}-{label}.png"
            try:
                extract_frame(video, timestamp, frame_path)
                mean, stddev = image_statistics(frame_path)
            except (OSError, RuntimeError) as exc:
                findings.append(
                    Finding("blocker", slide_id, str(video), f"cannot extract {label} frame: {exc}")
                )
                continue
            frames.append((f"{slide_id} {label}", frame_path))
            if stddev < 2.0 and (mean < 5.0 or mean > 250.0):
                kind = "black" if mean < 5.0 else "white"
                findings.append(
                    Finding("blocker", slide_id, str(frame_path), f"near-uniform {kind} frame detected")
                )
            if label == "last":
                bounds = content_bounds(frame_path)
                if bounds:
                    safe_x = info["width"] * 0.02
                    safe_y = info["height"] * 0.02
                    left, top, right, bottom = bounds
                    if (
                        left < safe_x
                        or top < safe_y
                        or right > info["width"] - safe_x
                        or bottom > info["height"] - safe_y
                    ):
                        findings.append(
                            Finding(
                                "major",
                                slide_id,
                                str(frame_path),
                                f"visible content enters the outer 2% frame margin (bounds={bounds})",
                            )
                        )

    contact_sheet = qa_dir / "contact-sheet.png"
    if frames:
        try:
            build_contact_sheet(frames, contact_sheet)
        except (OSError, RuntimeError) as exc:
            findings.append(Finding("blocker", "deck", "", f"contact sheet failed: {exc}"))

    report = qa_dir / "automated-report.md"
    qa_dir.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(findings, metadata) + "\n", encoding="utf-8")
    print(f"Wrote QA report: {report}")
    if frames:
        print(f"Wrote contact sheet: {contact_sheet}")

    blocking = [item for item in findings if item.severity == "blocker"]
    major = [item for item in findings if item.severity == "major"]
    if blocking or major:
        print(
            f"Visual QA requires attention: {len(blocking)} blocker(s), {len(major)} major finding(s).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

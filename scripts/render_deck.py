#!/usr/bin/env python3
"""Render selected Manim scenes and export HTML, video-based PPTX, and PDF."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from common import SkillInputError, load_structured_file, project_root_for
from export_html import export_html
from postprocess_pptx import replace_posters
from validate_deck import validate_deck
from write_speech import build_speech


OUTPUT_TYPES = {"html", "pptx", "pdf", "speech"}
PROFILE_CONFIG = {
    "draft": {"quality": "l", "fps": "15"},
    "final": {"quality": "h", "fps": "30"},
}


def parse_selection(data: dict[str, Any], selected_ids: str | None) -> list[dict[str, Any]]:
    slides = data["slides"]
    if not selected_ids:
        return slides
    requested = [item.strip() for item in selected_ids.split(",") if item.strip()]
    by_id = {slide["id"]: slide for slide in slides}
    missing = [slide_id for slide_id in requested if slide_id not in by_id]
    if missing:
        raise SkillInputError(f"Unknown slide IDs: {', '.join(missing)}")
    return [by_id[slide_id] for slide_id in requested]


def render_command(
    *, root: Path, profile: str, selected: list[dict[str, Any]], slides_folder: Path
) -> list[str]:
    config = PROFILE_CONFIG[profile]
    source_file = root / "src" / "slides.py"
    media_dir = root / "build" / profile / "media"
    return [
        "manim-slides",
        "render",
        f"--quality={config['quality']}",
        f"--fps={config['fps']}",
        f"--media_dir={media_dir}",
        str(source_file),
        *[slide["scene_class"] for slide in selected],
    ]


def convert_command(
    *,
    output_type: str,
    output_path: Path,
    selected: list[dict[str, Any]],
    slides_folder: Path,
) -> list[str]:
    command = [
        "manim-slides",
        "convert",
        *[slide["scene_class"] for slide in selected],
        str(output_path),
        f"--to={output_type}",
        "--folder",
        str(slides_folder),
    ]
    if output_type == "html":
        command.extend(
            [
                "--one-file",
                "--offline",
                "-ccontrols=true",
                "-cprogress=true",
                "-cslide_number=true",
                "-ctransition=fade",
            ]
        )
    return command


def run(
    command: list[str],
    *,
    cwd: Path,
    dry_run: bool,
    environment: dict[str, str] | None = None,
) -> int:
    print("$ " + " ".join(shlex.quote(item) for item in command))
    if dry_run:
        return 0
    process_environment = os.environ.copy()
    if environment:
        process_environment.update(environment)
    return subprocess.run(
        command,
        cwd=cwd,
        env=process_environment,
        check=False,
    ).returncode


def parse_outputs(value: str) -> list[str]:
    outputs = [item.strip() for item in value.split(",") if item.strip()]
    invalid = sorted(set(outputs) - OUTPUT_TYPES)
    if invalid:
        raise argparse.ArgumentTypeError(f"unknown outputs: {', '.join(invalid)}")
    if not outputs:
        raise argparse.ArgumentTypeError("select at least one output")
    return outputs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILE_CONFIG), default="draft")
    parser.add_argument("--slides", help="Comma-separated slide IDs, for example s02,s03")
    parser.add_argument(
        "--outputs", type=parse_outputs, default=parse_outputs("html,pptx,pdf,speech")
    )
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        data = load_structured_file(args.deck)
        findings = validate_deck(data, deck_path=args.deck, check_paths=False)
        errors = [finding for finding in findings if finding.severity == "error"]
        if errors:
            message = "; ".join(f"{item.path}: {item.message}" for item in errors)
            raise SkillInputError(f"Invalid deck specification: {message}")
        selected = parse_selection(data, args.slides)
    except SkillInputError as exc:
        print(exc, file=sys.stderr)
        return 1

    root = project_root_for(args.deck)
    source_file = root / "src" / "slides.py"
    if not source_file.is_file():
        print(f"Missing Manim entrypoint: {source_file}", file=sys.stderr)
        return 1

    build_root = root / "build" / args.profile
    slides_folder = build_root / "slides"
    build_root.mkdir(parents=True, exist_ok=True)
    slides_folder.mkdir(parents=True, exist_ok=True)

    if not args.skip_render:
        code = run(
            render_command(
                root=root,
                profile=args.profile,
                selected=selected,
                slides_folder=slides_folder,
            ),
            cwd=root,
            dry_run=args.dry_run,
            environment={
                "BUILD_MANIM_SLIDES_FOLDER": str(slides_folder),
                "BUILD_MANIM_DECK_SPEC": str(args.deck.resolve()),
            },
        )
        if code:
            print(f"Render failed with exit code {code}.", file=sys.stderr)
            return code

    partial = len(selected) != len(data["slides"])
    for output_type in args.outputs:
        if output_type == "speech":
            if partial:
                partial_project = {
                    **data["project"],
                    "duration_minutes": sum(
                        float(slide["duration_seconds"]) for slide in selected
                    )
                    / 60.0,
                }
                partial_data = {**data, "project": partial_project, "slides": selected}
                speech_path = build_root / "preview-speech.md"
                content, warnings = build_speech(partial_data)
            else:
                speech_path = root / data["outputs"]["speech"]
                content, warnings = build_speech(data)
            print(f"$ write speech manuscript -> {speech_path}")
            if not args.dry_run:
                speech_path.parent.mkdir(parents=True, exist_ok=True)
                speech_path.write_text(content + "\n", encoding="utf-8")
            for warning in warnings:
                print(f"[WARNING] {warning}")
            continue

        if partial:
            output_path = build_root / f"preview.{output_type}"
        else:
            output_path = root / data["outputs"][output_type]
        if not args.dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_type == "html":
            print(f"$ write self-contained HTML player -> {output_path}")
            if not args.dry_run:
                try:
                    count = export_html(
                        title=str(data["project"]["title"]),
                        scene_names=[slide["scene_class"] for slide in selected],
                        slides_folder=slides_folder,
                        output_path=output_path,
                    )
                except (OSError, SkillInputError) as exc:
                    print(f"html export failed: {exc}", file=sys.stderr)
                    return 1
                print(f"Embedded {count} slide segment(s).")
            continue
        code = run(
            convert_command(
                output_type=output_type,
                output_path=output_path,
                selected=selected,
                slides_folder=slides_folder,
            ),
            cwd=root,
            dry_run=args.dry_run,
        )
        if code:
            print(f"{output_type} export failed with exit code {code}.", file=sys.stderr)
            return code
        if output_type == "pptx" and not args.dry_run:
            try:
                count = replace_posters(output_path)
            except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
                print(f"pptx poster replacement failed: {exc}", file=sys.stderr)
                return 1
            print(
                f"Added {count} stable final-frame PPTX poster(s) with static fallbacks."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

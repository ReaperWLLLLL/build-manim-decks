#!/usr/bin/env python3
"""Generate the per-slide speech manuscript from an approved deck specification."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from common import SkillInputError, load_structured_file, project_root_for
from validate_deck import validate_deck


def estimate_minutes(text: str, language: str) -> float:
    if language.lower().startswith("zh"):
        count = len(re.findall(r"[\u3400-\u9fff]", text))
        return count / 240.0
    words = len(re.findall(r"\b\w+[\w'-]*\b", text))
    return words / 130.0


def build_speech(data: dict[str, Any]) -> tuple[str, list[str]]:
    project = data["project"]
    language = project["language"]
    title = project["title"]
    lines = [f"# Speech manuscript — {title}", ""]
    warnings: list[str] = []
    target_total = float(project["duration_minutes"])
    estimated_total = 0.0

    for slide in data["slides"]:
        notes = slide["notes"].strip()
        estimate = estimate_minutes(notes, language)
        estimated_total += estimate
        target_seconds = float(slide["duration_seconds"])
        actual_seconds = estimate * 60.0
        if notes and target_seconds and abs(actual_seconds - target_seconds) / target_seconds > 0.35:
            warnings.append(
                f"{slide['id']}: manuscript estimate {actual_seconds:.0f}s differs from target "
                f"{target_seconds:.0f}s by more than 35%"
            )

        refs = "; ".join(slide.get("source_refs", [])) or "None"
        cue = slide.get("advance_cue") or "Advance after completing the slide claim."
        lines.extend(
            [
                f"## {slide['id']} — {slide['title']}",
                "",
                f"**Target time:** {target_seconds:g} seconds  ",
                f"**Estimated manuscript time:** {actual_seconds:.0f} seconds",
                "",
                notes,
                "",
                f"**Advance cue:** {cue}  ",
                f"**Evidence:** {refs}",
                "",
            ]
        )

    lines.extend(
        [
            "## Timing summary",
            "",
            f"- Requested duration: {target_total:g} minutes",
            f"- Estimated manuscript duration: {estimated_total:.1f} minutes",
            "",
        ]
    )
    if target_total and abs(estimated_total - target_total) / target_total > 0.10:
        warnings.append("total manuscript estimate is outside 10% of the requested duration")
    return "\n".join(lines), warnings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        data = load_structured_file(args.deck)
    except SkillInputError as exc:
        print(exc, file=sys.stderr)
        return 1

    findings = validate_deck(data, deck_path=args.deck, check_paths=False)
    errors = [finding for finding in findings if finding.severity == "error"]
    if errors:
        for finding in errors:
            print(f"{finding.path}: {finding.message}", file=sys.stderr)
        return 1

    root = project_root_for(args.deck)
    configured = Path(data["outputs"]["speech"])
    output = args.output.resolve() if args.output else (root / configured).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    content, warnings = build_speech(data)
    output.write_text(content + "\n", encoding="utf-8")
    print(f"Wrote speech manuscript: {output}")
    for warning in warnings:
        print(f"[WARNING] {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

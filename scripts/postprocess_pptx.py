#!/usr/bin/env python3
"""Add stable final-frame posters to video-based PPTX files."""

from __future__ import annotations

import argparse
import copy
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_TAG = f"{{{REL_NS}}}Relationship"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

ET.register_namespace("a", A_NS)
ET.register_namespace("p", P_NS)
ET.register_namespace(
    "r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)


def slide_number(path: str) -> int:
    match = re.search(r"slide(\d+)\.xml\.rels$", path)
    if not match:
        raise ValueError(f"Not a slide relationship path: {path}")
    return int(match.group(1))


def resolve_target(rel_path: str, target: str) -> str:
    """Resolve an OPC relationship target relative to its source slide."""
    source_dir = posixpath.dirname(posixpath.dirname(rel_path))
    return posixpath.normpath(posixpath.join(source_dir, target))


def update_relationship_xml(
    payload: bytes, *, rel_path: str, poster_number: int
) -> tuple[bytes, str, str]:
    """Point one slide at a unique poster and return video/poster archive members."""
    root = ET.fromstring(payload)
    video_target: str | None = None
    image_relationship: ET.Element | None = None
    for relationship in root.findall(REL_TAG):
        relation_type = relationship.get("Type", "")
        if relation_type.endswith("/video"):
            video_target = relationship.get("Target")
        elif relation_type.endswith("/image"):
            image_relationship = relationship
    if not video_target:
        raise ValueError(f"No video relationship found in {rel_path}")
    if image_relationship is None:
        raise ValueError(f"No poster image relationship found in {rel_path}")

    poster_name = f"manim-poster-{poster_number}.png"
    poster_target = f"../media/{poster_name}"
    image_relationship.set("Target", poster_target)
    ET.register_namespace("", REL_NS)
    rendered = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return (
        rendered,
        resolve_target(rel_path, video_target),
        resolve_target(rel_path, poster_target),
    )


def has_video_relationship(payload: bytes) -> bool:
    root = ET.fromstring(payload)
    return any(
        relationship.get("Type", "").endswith("/video")
        for relationship in root.findall(REL_TAG)
    )


def add_static_fallback(payload: bytes, *, slide_number: int) -> tuple[bytes, int]:
    """Place an image-only copy behind a video for media-unaware renderers."""
    root = ET.fromstring(payload)
    shape_tree = root.find(f".//{{{P_NS}}}spTree")
    if shape_tree is None:
        raise ValueError(f"Slide {slide_number} has no shape tree")

    fallback_name = f"manim-static-poster-{slide_number}"
    for node in shape_tree.findall(f"{{{P_NS}}}pic"):
        properties = node.find(f".//{{{P_NS}}}cNvPr")
        if properties is not None and properties.get("name") == fallback_name:
            return payload, 0

    object_ids = [
        int(node.get("id", "0"))
        for node in shape_tree.findall(f".//{{{P_NS}}}cNvPr")
        if node.get("id", "").isdigit()
    ]
    next_id = max(object_ids, default=1) + 1

    for index, node in enumerate(list(shape_tree)):
        if node.tag != f"{{{P_NS}}}pic":
            continue
        if node.find(f".//{{{A_NS}}}videoFile") is None:
            continue

        fallback = copy.deepcopy(node)
        properties = fallback.find(f".//{{{P_NS}}}cNvPr")
        if properties is not None:
            properties.set("id", str(next_id))
            properties.set("name", fallback_name)
            for child in list(properties):
                properties.remove(child)
        nonvisual = fallback.find(f".//{{{P_NS}}}nvPr")
        if nonvisual is not None:
            for child in list(nonvisual):
                nonvisual.remove(child)
        shape_tree.insert(index, fallback)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True), 1

    raise ValueError(f"Slide {slide_number} has a video relationship but no video picture")


def extract_final_frame(video_path: Path, output_path: Path) -> None:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-sseof",
            "-0.10",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-y",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or not output_path.is_file():
        raise RuntimeError((result.stderr or "could not extract final video frame").strip())


def replace_posters(pptx_path: Path) -> int:
    pptx_path = pptx_path.resolve()
    if not pptx_path.is_file():
        raise FileNotFoundError(pptx_path)

    replacements: dict[str, bytes] = {}
    posters: dict[str, bytes] = {}
    with zipfile.ZipFile(pptx_path) as source, tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        rel_paths = sorted(
            (
                name
                for name in source.namelist()
                if re.fullmatch(r"ppt/slides/_rels/slide\d+\.xml\.rels", name)
            ),
            key=slide_number,
        )
        if not rel_paths:
            raise RuntimeError("PPTX contains no slide relationships")

        for poster_number, rel_path in enumerate(rel_paths, start=1):
            relationship_payload = source.read(rel_path)
            if not has_video_relationship(relationship_payload):
                continue
            updated, video_member, poster_member = update_relationship_xml(
                relationship_payload, rel_path=rel_path, poster_number=poster_number
            )
            if video_member not in source.namelist():
                raise RuntimeError(f"Embedded video is missing: {video_member}")
            video_path = temp_dir / f"video-{poster_number}{Path(video_member).suffix}"
            poster_path = temp_dir / f"poster-{poster_number}.png"
            video_path.write_bytes(source.read(video_member))
            extract_final_frame(video_path, poster_path)
            replacements[rel_path] = updated
            posters[poster_member] = poster_path.read_bytes()
            slide_path = rel_path.replace("/_rels/", "/").removesuffix(".rels")
            slide_payload, _ = add_static_fallback(
                source.read(slide_path), slide_number=poster_number
            )
            replacements[slide_path] = slide_payload

        temporary = tempfile.NamedTemporaryFile(
            dir=pptx_path.parent, prefix=f".{pptx_path.name}.", suffix=".tmp", delete=False
        )
        temporary_path = Path(temporary.name)
        temporary.close()
        try:
            with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for info in source.infolist():
                    if info.filename in posters:
                        continue
                    target.writestr(info, replacements.get(info.filename, source.read(info.filename)))
                for member, content in posters.items():
                    target.writestr(member, content, compress_type=zipfile.ZIP_DEFLATED)
            with zipfile.ZipFile(temporary_path) as check:
                corrupt = check.testzip()
                if corrupt:
                    raise RuntimeError(f"postprocessed PPTX is corrupt at {corrupt}")
            os.replace(temporary_path, pptx_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    return len(posters)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        count = replace_posters(args.pptx)
    except (FileNotFoundError, OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"PPTX poster replacement failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Added {count} stable final-frame PPTX poster(s) with static fallbacks: "
        f"{args.pptx}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

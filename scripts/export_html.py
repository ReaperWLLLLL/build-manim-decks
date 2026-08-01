#!/usr/bin/env python3
"""Build a self-contained, dependency-free HTML player from Manim Slides media."""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

from common import SkillInputError


def _media_path(value: str, *, config_path: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = config_path.parent / path
    return path.resolve()


def collect_slides(scene_names: list[str], slides_folder: Path) -> list[dict[str, Any]]:
    """Read scene manifests in requested order and embed every media segment."""
    entries: list[dict[str, Any]] = []
    for scene_name in scene_names:
        config_path = slides_folder / f"{scene_name}.json"
        if not config_path.is_file():
            raise SkillInputError(f"Missing rendered slide manifest: {config_path}")
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SkillInputError(f"Invalid slide manifest {config_path}: {exc}") from exc
        segments = config.get("slides")
        if not isinstance(segments, list) or not segments:
            raise SkillInputError(f"No slide segments found in {config_path}")

        for segment_number, segment in enumerate(segments, start=1):
            if not isinstance(segment, dict) or not isinstance(segment.get("file"), str):
                raise SkillInputError(
                    f"Invalid segment {segment_number} in {config_path}: missing media file"
                )
            media_path = _media_path(segment["file"], config_path=config_path)
            if not media_path.is_file():
                raise SkillInputError(f"Missing rendered media: {media_path}")
            mime = mimetypes.guess_type(media_path.name)[0] or "video/mp4"
            encoded = base64.b64encode(media_path.read_bytes()).decode("ascii")
            entries.append(
                {
                    "scene": scene_name,
                    "segment": segment_number,
                    "src": f"data:{mime};base64,{encoded}",
                    "notes": str(segment.get("notes") or ""),
                    "loop": bool(segment.get("loop", False)),
                    "playbackRate": float(segment.get("playback_rate", 1.0)),
                }
            )
    return entries


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<style>
:root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
* { box-sizing: border-box; }
html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; background: #05070b; }
body { display: grid; place-items: center; }
#stage { position: relative; width: min(100vw, calc(100vh * 16 / 9)); aspect-ratio: 16 / 9; background: #000; box-shadow: 0 0 4rem #000; }
video { display: block; width: 100%; height: 100%; object-fit: contain; background: #000; cursor: pointer; }
#chrome { position: absolute; inset: auto 0 0; padding: 2.5rem 1rem .7rem; background: linear-gradient(transparent, rgba(0,0,0,.78)); opacity: 0; transition: opacity .2s; }
#stage:hover #chrome, #chrome:focus-within { opacity: 1; }
#controls { display: flex; align-items: center; justify-content: space-between; gap: .7rem; }
#controls button { border: 1px solid #ffffff55; border-radius: .4rem; padding: .45rem .75rem; color: white; background: #111827cc; cursor: pointer; }
#controls button:hover { background: #26324acc; }
#counter { min-width: 7rem; text-align: center; font-variant-numeric: tabular-nums; }
#progress-track { height: .28rem; margin-top: .6rem; border-radius: 1rem; overflow: hidden; background: #ffffff33; }
#progress { height: 100%; width: 0; background: #66d9ef; transition: width .08s linear; }
#notes { position: absolute; inset: 1rem 1rem auto auto; display: none; width: min(36rem, 82%); max-height: 45%; overflow: auto; padding: 1rem; white-space: pre-wrap; color: #f5f7fb; background: #111827ee; border: 1px solid #ffffff33; border-radius: .5rem; }
#notes.visible { display: block; }
#help { position: absolute; inset: auto auto 1rem 1rem; padding: .35rem .55rem; color: #ffffff99; background: #0008; border-radius: .3rem; font-size: .78rem; }
@media (pointer: coarse) { #chrome { opacity: 1; } #help { display: none; } }
</style>
</head>
<body>
<main id="stage" aria-label="__TITLE__ — offline animated presentation">
  <video id="player" playsinline preload="auto"></video>
  <aside id="notes" aria-live="polite"></aside>
  <div id="chrome">
    <div id="controls">
      <button id="previous" type="button" aria-label="Previous slide">← Previous</button>
      <button id="play" type="button" aria-label="Play or pause">Play / Pause</button>
      <span id="counter">1 / __COUNT__</span>
      <button id="fullscreen" type="button" aria-label="Toggle fullscreen">Fullscreen</button>
      <button id="next" type="button" aria-label="Next slide">Next →</button>
    </div>
    <div id="progress-track" aria-hidden="true"><div id="progress"></div></div>
  </div>
  <div id="help">←/→ slides · Space play/pause · N notes · F fullscreen</div>
</main>
<script id="deck-data" type="application/json">__DECK_DATA__</script>
<script>
(() => {
  const deck = JSON.parse(document.getElementById('deck-data').textContent);
  const player = document.getElementById('player');
  const counter = document.getElementById('counter');
  const notes = document.getElementById('notes');
  const progress = document.getElementById('progress');
  const stage = document.getElementById('stage');
  let index = 0;

  function updateProgress() {
    const within = Number.isFinite(player.duration) && player.duration > 0
      ? player.currentTime / player.duration : 0;
    progress.style.width = `${((index + within) / deck.length) * 100}%`;
  }
  function load(nextIndex, autoplay = true) {
    index = Math.max(0, Math.min(deck.length - 1, nextIndex));
    const slide = deck[index];
    player.src = slide.src;
    player.loop = slide.loop;
    player.playbackRate = slide.playbackRate;
    counter.textContent = `${index + 1} / ${deck.length} · ${slide.scene}`;
    notes.textContent = slide.notes || 'No speaker notes for this slide.';
    updateProgress();
    if (autoplay) player.play().catch(() => {});
  }
  function togglePlayback() { player.paused ? player.play() : player.pause(); }
  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else stage.requestFullscreen().catch(() => {});
  }

  document.getElementById('previous').addEventListener('click', () => load(index - 1));
  document.getElementById('next').addEventListener('click', () => load(index + 1));
  document.getElementById('play').addEventListener('click', togglePlayback);
  document.getElementById('fullscreen').addEventListener('click', toggleFullscreen);
  player.addEventListener('click', togglePlayback);
  player.addEventListener('timeupdate', updateProgress);
  player.addEventListener('ended', updateProgress);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowRight' || event.key === 'PageDown') load(index + 1);
    else if (event.key === 'ArrowLeft' || event.key === 'PageUp') load(index - 1);
    else if (event.key === 'Home') load(0);
    else if (event.key === 'End') load(deck.length - 1);
    else if (event.key === ' ') { event.preventDefault(); togglePlayback(); }
    else if (event.key.toLowerCase() === 'n') notes.classList.toggle('visible');
    else if (event.key.toLowerCase() === 'f') toggleFullscreen();
  });
  load(0, false);
})();
</script>
</body>
</html>
"""


def export_html(
    *, title: str, scene_names: list[str], slides_folder: Path, output_path: Path
) -> int:
    entries = collect_slides(scene_names, slides_folder)
    if not entries:
        raise SkillInputError("No rendered slide segments are available for HTML export")
    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    content = (
        HTML_TEMPLATE.replace("__TITLE__", html.escape(title))
        .replace("__COUNT__", str(len(entries)))
        .replace("__DECK_DATA__", payload)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return len(entries)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("scenes", nargs="+")
    parser.add_argument("--folder", type=Path, default=Path("slides"))
    parser.add_argument("--title", default="Manim presentation")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        count = export_html(
            title=args.title,
            scene_names=args.scenes,
            slides_folder=args.folder,
            output_path=args.output,
        )
    except (OSError, SkillInputError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Wrote self-contained HTML with {count} slide segment(s): {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

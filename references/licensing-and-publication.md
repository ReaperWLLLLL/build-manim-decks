# Licensing and publication

Use this checklist before publishing the skill or a generated example. It is an
engineering release check, not a substitute for legal advice.

## Separate working evidence from public artifacts

- Put third-party originals under `.private/sources/` and extraction output under
  `.private/extracted/`. Keep `.private/` out of Git and release archives.
- Track a small citation record instead: title, authors, venue, year, official URL,
  content hash when useful, page or section locators, and an independently written
  evidence summary.
- Do not publish a downloaded paper, extracted full text, page screenshots, tables,
  or original figures merely because the source is publicly readable.
- Keep user-owned or permissively licensed sources in `source/` only when their
  provenance and redistribution terms are recorded.

## Transform with attribution

- Prefer original Manim diagrams that explain relationships in a new visual grammar.
- Cite the source and locator on the slide and in `planning/evidence-map.md`.
- Label a recreated architecture or chart as an explanatory redraw. Do not reproduce
  distinctive artwork pixel for pixel unless the license permits it.
- Quote only the minimum needed. Preserve authorship and license notices for copied
  material; facts and equations still need scholarly attribution even when copyright
  does not protect the underlying idea.

## Review software and assets

- Keep the repository's `LICENSE` separate from dependency licenses. Preserve
  `THIRD_PARTY_NOTICES.md` in releases.
- Do not vendor Python packages, FFmpeg, TeX, fonts, or their binaries without a
  component-level license review. A requirements file is not permission to relicense
  dependencies under the project license.
- Reference proprietary fonts by family name only. Require the user to supply a
  licensed local installation; never copy font files into the project.
- If creating a Docker image, standalone installer, or hosted service, generate a
  complete dependency inventory and re-audit transitive and system components.

## Release scan

Before publishing, inspect tracked and packaged files for `.pdf`, `.docx`, `.pptx`,
font files, extracted Markdown, page images, archives, media copied from sources, and
absolute local paths. Confirm that every retained third-party artifact has a recorded
license or permission. Remove ignored working material from any staging archive.

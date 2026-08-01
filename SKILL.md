---
name: build-manim-decks
description: Build, revise, and visually QA animated scientific presentations with Manim CE and manim-slides. Use when turning a research paper, PDF, Markdown, LaTeX source, or outline into a research talk, thesis defense, or technical lesson; when repairing an existing Manim deck; or when exporting and verifying self-contained offline HTML, video-based PPTX, static PDF, and a timed speech manuscript.
---

# Build Manim Decks

Create an evidence-backed narrative, generate maintainable Manim source, review rendered frames rather than trusting code alone, and verify every requested deliverable. Preserve intermediate planning and QA artifacts so a single slide can be revised independently.

## Resolve the skill and project

Treat the directory containing this `SKILL.md` as `SKILL_DIR`. Keep the presentation project outside the skill directory. Use project-relative paths in all delivered rebuild instructions.

For a new project, run:

```bash
python "$SKILL_DIR/scripts/scaffold_project.py" PROJECT_DIR --title "Talk title"
```

Never overwrite user source files. Refuse non-empty project directories unless the user explicitly authorizes `--force`.

## Route the request

- **New deck from sources:** follow the complete workflow below.
- **Revise an existing deck:** read `planning/deck.yaml`, source evidence, current QA reports, and affected scene code; update the specification first, then re-render selected slide IDs.
- **Visual review only:** run automated QA, inspect the contact sheet and full-resolution evidence frames, and write repair findings without changing code unless the user requests fixes.
- **Repair an output:** verify deliverables, rebuild only the failing format, and re-run its verification.
- **Outline or planning only:** stop after the requested planning artifact; do not imply that rendered deliverables exist.

## Follow the production workflow

Read `references/workflow.md` for the authoritative sequence and approval gates.

1. Run preflight for the requested inputs and outputs.
2. Normalize sources and create an evidence map.
3. Write and, by default, obtain approval for the design brief and outline.
4. Write and validate `planning/deck.yaml`.
5. Implement and review a representative sample before full production.
6. Generate scenes and render a low-quality draft.
7. Run automated and visual QA; repair only affected slides.
8. Render final media and export requested outputs.
9. Verify HTML, PPTX, PDF, speech, sources, and rebuild commands.

Skip approval gates only when the user explicitly requests autonomous execution. Even then, preserve the brief, outline, deck specification, and QA evidence.

## Run preflight

```bash
python "$SKILL_DIR/scripts/preflight.py" \
  --need-pdf-input --need-latex --need-pptx
```

Treat missing Manim, manim-slides, FFmpeg, or required Python modules as blocking. Do not install system dependencies or change global environments without user authorization; prefer a project-local virtual environment.
Read `references/troubleshooting.md` when dependency installation, fonts, LaTeX, conversion, or cached media fail.

## Ingest evidence

Read `references/source-ingestion.md`. Normalize supported files with:

```bash
python "$SKILL_DIR/scripts/extract_source.py" SOURCE... \
  --output-dir PROJECT_DIR/planning/extracted --extract-images
```

Use stable evidence IDs in `planning/evidence-map.md`. Never invent numeric results, citations, figures, equations, or experimental conditions.

## Design the narrative

Read `references/scientific-storytelling.md`. Match the story to a research talk, thesis defense, or technical lesson. Use action titles and one primary claim per slide. Budget every slide in seconds and keep the total within 10% of the requested duration.

Write `planning/deck.yaml` using `references/deck-spec.md`, then run:

```bash
python "$SKILL_DIR/scripts/validate_deck.py" PROJECT_DIR/planning/deck.yaml --check-paths
```

Do not generate Manim scenes from an invalid specification.

## Author Manim scenes

Read `references/manim-authoring.md`. Prefer one stable `Slide` subclass per logical slide. Keep class names aligned with `scene_class` in `deck.yaml`, centralize the theme, reuse semantic object identity, and use motion only to explain relationships or direct attention.

Render a selected sample at draft quality:

```bash
python "$SKILL_DIR/scripts/render_deck.py" PROJECT_DIR/planning/deck.yaml \
  --profile draft --slides s02 --outputs html,speech
```

After the sample is approved, render the complete draft. Use `--dry-run` to inspect commands and `--skip-render` only when cached scene manifests are known to be current.

## Perform visual QA

Read `references/visual-qa.md`, then run:

```bash
python "$SKILL_DIR/scripts/visual_qa.py" PROJECT_DIR/planning/deck.yaml --profile draft
```

Open `qa/<profile>/contact-sheet.png` and inspect it visually. Inspect full-resolution first, middle, maximum-density, and final frames for slides with equations, dense labels, charts, or reported QA findings. Automated checks do not approve composition, pacing, or scientific accuracy.

Record findings with slide ID, severity, evidence frame, repair, and status. Block final export on unresolved blockers; require explicit user acceptance for unresolved major findings.

## Build final outputs

Read `references/output-contract.md`. When the draft passes QA, run:

```bash
python "$SKILL_DIR/scripts/render_deck.py" PROJECT_DIR/planning/deck.yaml \
  --profile final --outputs html,pptx,pdf,speech
```

Run final-profile QA after the high-resolution render:

```bash
python "$SKILL_DIR/scripts/visual_qa.py" PROJECT_DIR/planning/deck.yaml --profile final
```

Inspect `qa/final/contact-sheet.png`, every final frame at full size, and dense intermediate states. Update `qa/report.md` with findings and repairs. Set `Final visual approval: approved` only after that inspection; output verification rejects `pending`.

The PPTX is intentionally video-based. Do not promise native editability of Manim objects.

Verify outputs:

```bash
python "$SKILL_DIR/scripts/verify_outputs.py" PROJECT_DIR/planning/deck.yaml
```

File existence is insufficient. Verify final visual-approval evidence; HTML media and navigation; PPTX archive, slides, media, stable nonblank poster frames, static fallbacks behind videos, automatic playback, and notes; PDF page count, 16:9 dimensions, and previews; speech slide mapping and timing; source paths and evidence IDs; and exact rebuild commands.

## Deliver transparently

Hand off the complete project layout defined in `references/output-contract.md`. Report final artifact paths, passed and unresolved QA findings, source limitations, timing variance, the command to revise one slide, and whether each format was opened or structurally verified.

Never claim completion when only a dry run, partial scene, placeholder, or unreviewed render exists.

## Resource map

- `references/workflow.md`: production sequence and approval gates.
- `references/source-ingestion.md`: supported sources and evidence integrity.
- `references/deck-spec.md`: required `deck.yaml` schema and timing rules.
- `references/scientific-storytelling.md`: research and teaching narrative design.
- `references/manim-authoring.md`: scene, layout, animation, and typography rules.
- `references/visual-qa.md`: automated and visual review gates.
- `references/output-contract.md`: project layout and deliverable verification.
- `references/troubleshooting.md`: environment, rendering, font, cache, and export failures.
- `assets/project-template/`: deterministic starter project copied by the scaffolder.

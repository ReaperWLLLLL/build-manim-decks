# Text humanization and spoken-copy QA

Humanize audience-facing copy after `deck.yaml` is valid and before implementing
the representative sample. Treat wording changes as layout changes.

## Review scope

Review the project title, thesis, takeaways, slide titles, claims, speaker notes,
beat narration, and every visible string in the Manim scenes. Internal animation
instructions and code comments do not need literary editing.

Do not rewrite equations, reported values, citations, proper names, quoted paper
language, or standard technical terms merely to vary the wording. Keep the
evidence map open during the review.

## Apply two passes

1. Run a general humanizer pass. Remove promotional language, vague authority,
   formulaic signposting, forced groups of three, negative parallelisms, generic
   conclusions, and slogan-like closing lines. Prefer direct statements.
2. Run a locale-specific pass. For Chinese decks, invoke `humanizer-zh` after the
   general `humanizer` pass when those skills are available. Use natural spoken
   Chinese, keep established English technical terms, and avoid translation-like
   abstractions. Technical talks should remain neutral; do not add personality or
   first person where it distracts from the evidence.
3. Ask what still sounds machine-written, then revise once more. Preserve useful
   repetition of technical terms instead of cycling through synonyms.

For other languages, use the best available locale-specific editor after the
general pass. When no external humanizer skill is installed, apply the same rules
manually; this reference is the acceptance contract.

## Audit and synchronize

Run the mechanical audit:

```bash
python "$SKILL_DIR/scripts/audit_text.py" PROJECT_DIR/planning/deck.yaml
```

The command writes `qa/text-review.md`. Hard findings such as em/en dashes and
chat-assistant artifacts return a nonzero status. Review candidates are prompts
for judgment, not automatic failures.

After editing `deck.yaml`, synchronize all visible strings in `src/`. Read the
speaker notes aloud, regenerate `deliverables/speech.md`, and confirm that its
estimated duration remains within 10% of the requested time. Mark `Text review:
approved` only after checking facts, terminology, spoken rhythm, and scene-copy
consistency.

## Re-render gate

Any wording change can alter width, wrapping, timing, and animation density.
Re-render every affected slide, run text-fit assertions where available, inspect
full-resolution dense and final frames, and repeat visual QA. A prior visual
approval does not survive a change to visible text.

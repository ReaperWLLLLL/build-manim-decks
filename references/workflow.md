# End-to-end workflow

Use this workflow for every new research talk, thesis defense, or technical lesson. Preserve intermediate artifacts so a later run can revise one slide without rebuilding the entire deck.

## 1. Establish the brief

Read the source material before proposing visuals. Create `planning/design-brief.md` with:

- audience and assumed prior knowledge;
- talk type and exact time budget;
- one-sentence thesis;
- three to five audience takeaways;
- evidence that must appear;
- content that may be omitted;
- language, notation, citation, and accessibility constraints;
- requested deliverables.

Ask the user to approve the brief unless they explicitly request an autonomous run.

## 2. Build the evidence map

Create `planning/evidence-map.md`. Give every reusable source item a stable ID such as `src-paper-p4`, `fig-02`, or `eq-03`. Record the original file and page, section, figure, table, or equation location. Never invent a citation or experimental value.

## 3. Plan the narrative

Create `planning/outline.md` before writing Manim code. Use action titles: each slide title should state the point the audience should understand, not merely name a topic. Budget time by slide and reserve time for the opening, transitions, conclusion, and questions.

Recommended arcs:

- Research talk: problem -> gap -> insight -> method -> evidence -> implications.
- Thesis defense: motivation -> research questions -> contributions -> methods -> results -> limitations -> conclusion.
- Technical lesson: prerequisite -> intuition -> construction -> worked example -> failure mode -> exercise or recap.

Ask the user to approve the outline unless autonomous mode was requested.

## 4. Write `deck.yaml`

Convert the approved outline into the schema in `deck-spec.md`. Run:

```bash
python scripts/validate_deck.py path/to/deck.yaml
```

Do not generate scenes from an invalid specification.

## 5. Implement one representative sample

Implement a title/transition slide and one technically difficult explanatory slide. Render at draft quality. This sample must establish typography, palette, notation, animation pacing, and visual density.

Ask the user to approve the sample unless autonomous mode was requested.

## 6. Implement in sections

Prefer one Manim `Slide` subclass per logical slide so HTML, PPTX, PDF, notes, and QA evidence stay aligned. Use a tightly coupled multi-slide class only when object continuity cannot be preserved otherwise. Keep reusable visual primitives in `src/components/` and theme constants in `src/theme.py`. Use stable scene names from `deck.yaml` so individual slides or sections can be rebuilt independently.

## 7. Render a draft

Render at 854x480 or 1280x720 and reduced frame rate. Export poster frames and a contact sheet. Do not spend time on 1080p or 4K until the structure and timing pass QA.

## 8. Run visual QA

Apply all automated and human-review gates in `visual-qa.md`. Write findings to `qa/report.md`, including slide ID, severity, evidence, and proposed repair. Re-render only affected sections.

## 9. Build final deliverables

After the draft passes QA, render the final resolution and package outputs according to `output-contract.md`. Verify every deliverable by opening or parsing it; file existence alone is insufficient.

## 10. Handoff

Provide:

- final deliverables;
- source project and `deck.yaml`;
- the QA report;
- unresolved limitations;
- exact commands for rebuilding and revising one section.

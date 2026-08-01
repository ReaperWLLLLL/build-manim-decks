# Source ingestion and evidence mapping

## Supported inputs

Use the bundled extractor for PDF papers and reports, Markdown, LaTeX source, and plain-text outlines:

```bash
python scripts/extract_source.py SOURCE... --output-dir PROJECT/planning/extracted
```

Add `--extract-images` for PDF figures. The script preserves originals, records SHA-256 hashes, writes page-delimited Markdown, and creates `source-manifest.json`.

## Reading strategy

Do not summarize the whole source indiscriminately. Extract the research question or teaching objective, gap, mechanism, key definitions, experimental setup, strongest result, uncertainty, limitation, and reusable visual evidence. For long papers, read the abstract, introduction, method overview, figure captions, central results, and conclusion first. Return to detailed sections only when a planned slide needs them.

## Evidence map

Create stable IDs before planning slides:

| ID pattern | Use |
|---|---|
| `src-paper-p12` | page-level source text |
| `fig-03` | paper or generated figure |
| `tbl-02` | result table |
| `eq-04` | equation or formal definition |
| `claim-05` | source-backed textual claim |

Record original file, page or section, original caption, and allowed transformation. If a figure is redrawn with Manim, cite the original evidence and mark the new visual as an explanatory reconstruction.
Keep each ID in backticks in the first column of the Markdown table. `validate_deck.py` reads this column and rejects duplicate or unregistered slide references.

## Scientific integrity

- Preserve units, denominators, baselines, confidence intervals, and experimental conditions.
- Do not infer causality from correlation unless the source supports it.
- Do not turn a qualitative statement into a fabricated numeric result.
- Separate source claims, presenter interpretation, and pedagogical analogy.
- Surface conflicting evidence instead of silently selecting the convenient result.
- Mark unavailable or ambiguous evidence as unresolved in the planning artifacts.

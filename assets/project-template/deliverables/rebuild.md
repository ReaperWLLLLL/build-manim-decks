# Rebuild {{PROJECT_TITLE}}

Run from the project root with `SKILL_DIR` set to the installed `build-manim-decks`
directory and its Python environment activated.

```bash
: "${SKILL_DIR:?Set SKILL_DIR to the build-manim-decks skill directory}"

python "$SKILL_DIR/scripts/preflight.py" --need-pdf-input --need-latex --need-pptx
python "$SKILL_DIR/scripts/validate_deck.py" planning/deck.yaml --check-paths

# Representative draft sample; replace s02 when another slide is more demanding.
python "$SKILL_DIR/scripts/render_deck.py" planning/deck.yaml \
  --profile draft --slides s02 --outputs html,speech

python "$SKILL_DIR/scripts/render_deck.py" planning/deck.yaml \
  --profile draft --outputs html,pptx,pdf,speech
python "$SKILL_DIR/scripts/visual_qa.py" planning/deck.yaml --profile draft

python "$SKILL_DIR/scripts/render_deck.py" planning/deck.yaml \
  --profile final --outputs html,pptx,pdf,speech
python "$SKILL_DIR/scripts/visual_qa.py" planning/deck.yaml --profile final
python "$SKILL_DIR/scripts/verify_outputs.py" planning/deck.yaml

# Rebuild one cached output without rerendering scenes.
python "$SKILL_DIR/scripts/render_deck.py" planning/deck.yaml \
  --profile final --outputs html --skip-render
```

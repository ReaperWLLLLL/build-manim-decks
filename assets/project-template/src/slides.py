"""Starter scenes for {{PROJECT_TITLE}}.

Replace placeholder visuals only after the design brief, outline, and deck.yaml
are approved. Keep class names aligned with deck.yaml.
"""

from manim import *
from manim_slides import Slide
import os
from pathlib import Path
import yaml

from src.theme import (
    ACCENT,
    BACKGROUND,
    BODY_SIZE,
    FOREGROUND,
    MUTED,
    PRIMARY,
    SAFE_MARGIN,
    TITLE_SIZE,
)


class DeckSlide(Slide):
    """Shared 16:9 styling and helpers."""

    # HTML, PPTX, and PDF never use reverse playback. Avoid rendering duplicate media.
    skip_reversing = True

    def __init__(self, *args, **kwargs):
        """Keep generated slide metadata inside the selected build profile."""
        output_folder = Path(os.environ.get("BUILD_MANIM_SLIDES_FOLDER", "slides"))
        super().__init__(*args, output_folder=output_folder, **kwargs)

    def setup(self):
        self.camera.background_color = BACKGROUND
        notes = self._speaker_notes()
        if notes:
            # Calling next_slide before the first animation assigns these notes
            # to the scene's single logical slide without creating an empty slide.
            self.next_slide(notes=notes)

    def _speaker_notes(self) -> str:
        deck_path = Path(
            os.environ.get(
                "BUILD_MANIM_DECK_SPEC",
                Path(__file__).resolve().parents[1] / "planning" / "deck.yaml",
            )
        )
        try:
            data = yaml.safe_load(deck_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return ""
        for slide in data.get("slides", []) if isinstance(data, dict) else []:
            if slide.get("scene_class") == self.__class__.__name__:
                return str(slide.get("notes") or "")
        return ""

    def fit_to_safe_width(self, mobject: Mobject) -> Mobject:
        max_width = config.frame_width - 2 * SAFE_MARGIN
        if mobject.width > max_width:
            mobject.scale_to_fit_width(max_width)
        return mobject

    def title(self, text: str) -> Text:
        heading = Text(text, font_size=TITLE_SIZE, color=FOREGROUND)
        return self.fit_to_safe_width(heading).to_edge(UP)


class Opening(DeckSlide):
    def construct(self):
        title = self.fit_to_safe_width(
            Text("{{PROJECT_TITLE}}", font_size=TITLE_SIZE, color=FOREGROUND)
        )
        thesis = Text(
            "Replace this line with the approved one-sentence thesis",
            font_size=BODY_SIZE,
            color=MUTED,
        )
        self.fit_to_safe_width(thesis).next_to(title, DOWN, buff=0.5)
        self.play(Write(title))
        self.play(FadeIn(thesis, shift=0.2 * UP))
        self.wait(1)


class CoreMechanism(DeckSlide):
    def construct(self):
        heading = self.title("One mechanism connects the question to an observable result")
        left = RoundedRectangle(width=3.0, height=1.8, color=PRIMARY)
        right = RoundedRectangle(width=3.0, height=1.8, color=ACCENT)
        group = VGroup(left, right).arrange(RIGHT, buff=2.0).shift(DOWN * 0.3)
        left_label = Text("Initial state", font_size=BODY_SIZE).move_to(left)
        right_label = Text("Result", font_size=BODY_SIZE).move_to(right)
        arrow = Arrow(left.get_right(), right.get_left(), color=MUTED)
        mechanism = Text("Mechanism", font_size=BODY_SIZE, color=ACCENT).next_to(arrow, UP)

        self.play(Write(heading), Create(left), FadeIn(left_label))
        self.play(GrowArrow(arrow), FadeIn(mechanism, shift=UP * 0.15))
        self.play(Create(right), FadeIn(right_label))
        self.wait(1)


class Closing(DeckSlide):
    def construct(self):
        heading = self.title("The conclusion is useful only within its evidence boundary")
        lines = VGroup(
            Text("Contribution", font_size=BODY_SIZE, color=PRIMARY),
            Text("Evidence", font_size=BODY_SIZE, color=FOREGROUND),
            Text("Limitation", font_size=BODY_SIZE, color=ACCENT),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.45)
        self.play(Write(heading))
        self.play(LaggedStart(*(FadeIn(line, shift=RIGHT * 0.2) for line in lines), lag_ratio=0.25))
        self.wait(1)

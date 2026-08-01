from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import render_deck
import scaffold_project
import validate_deck
import write_speech
from export_html import export_html
from common import load_structured_file, to_project_slug, to_python_class


class HelpersTest(unittest.TestCase):
    def test_class_and_slug_normalization(self) -> None:
        self.assertEqual(to_python_class("2026 research talk"), "Scene2026ResearchTalk")
        self.assertEqual(to_project_slug("Research Talk 2026"), "research-talk-2026")
        self.assertEqual(to_project_slug("科研演讲"), "manim-deck")


class ScaffoldAndValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "demo"
        code = scaffold_project.main([str(self.root), "--title", "Research Demo"])
        self.assertEqual(code, 0)
        self.deck_path = self.root / "planning" / "deck.yaml"
        self.data = load_structured_file(self.deck_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_starter_validates(self) -> None:
        findings = validate_deck.validate_deck(
            self.data, deck_path=self.deck_path, check_paths=True
        )
        self.assertFalse([item for item in findings if item.severity == "error"])

    def test_duplicate_slide_and_scene_fail(self) -> None:
        invalid = copy.deepcopy(self.data)
        invalid["slides"][1]["id"] = invalid["slides"][0]["id"]
        invalid["slides"][1]["scene_class"] = invalid["slides"][0]["scene_class"]
        findings = validate_deck.validate_deck(
            invalid, deck_path=self.deck_path, check_paths=False
        )
        messages = "\n".join(item.message for item in findings)
        self.assertIn("duplicate slide id", messages)
        self.assertIn("must be unique", messages)

    def test_output_escape_fails(self) -> None:
        invalid = copy.deepcopy(self.data)
        invalid["outputs"]["html"] = "../presentation.html"
        findings = validate_deck.validate_deck(
            invalid, deck_path=self.deck_path, check_paths=False
        )
        self.assertTrue(any(item.path == "outputs.html" for item in findings))

    def test_output_suffix_and_external_source_fail(self) -> None:
        invalid = copy.deepcopy(self.data)
        invalid["outputs"]["pptx"] = "deliverables/presentation.zip"
        invalid["project"]["source_files"] = ["../paper.pdf"]
        findings = validate_deck.validate_deck(
            invalid, deck_path=self.deck_path, check_paths=False
        )
        paths = {item.path for item in findings if item.severity == "error"}
        self.assertIn("outputs.pptx", paths)
        self.assertIn("project.source_files[0]", paths)

    def test_partial_render_uses_preview_outputs(self) -> None:
        selected = render_deck.parse_selection(self.data, "s02")
        command = render_deck.convert_command(
            output_type="html",
            output_path=self.root / "build" / "draft" / "preview.html",
            selected=selected,
            slides_folder=self.root / "build" / "draft" / "slides",
        )
        self.assertIn("CoreMechanism", command)
        self.assertIn("--one-file", command)
        self.assertNotIn("Opening", command)

    def test_final_render_uses_unambiguous_quality_flag(self) -> None:
        selected = render_deck.parse_selection(self.data, None)
        command = render_deck.render_command(
            root=self.root,
            profile="final",
            selected=selected,
            slides_folder=self.root / "build" / "final" / "slides",
        )
        self.assertIn("--quality=h", command)
        self.assertNotIn("-qh", command)

    def test_speech_contains_all_slide_sections(self) -> None:
        manuscript, _warnings = write_speech.build_speech(self.data)
        self.assertEqual(manuscript.count("\n## s"), len(self.data["slides"]))
        self.assertIn("## Timing summary", manuscript)

    def test_html_export_is_self_contained(self) -> None:
        slides_folder = self.root / "build" / "draft" / "slides"
        media = slides_folder / "files" / "Opening" / "opening.mp4"
        media.parent.mkdir(parents=True)
        media.write_bytes(b"fake-mp4-for-structural-test")
        manifest = {
            "slides": [
                {
                    "file": str(media),
                    "notes": "Opening notes",
                    "loop": False,
                    "playback_rate": 1.0,
                }
            ]
        }
        import json

        (slides_folder / "Opening.json").write_text(json.dumps(manifest), encoding="utf-8")
        output = self.root / "deliverables" / "presentation.html"
        count = export_html(
            title="Research Demo",
            scene_names=["Opening"],
            slides_folder=slides_folder,
            output_path=output,
        )
        text = output.read_text(encoding="utf-8")
        self.assertEqual(count, 1)
        self.assertIn("data:video/mp4;base64,", text)
        self.assertNotIn('src="https://', text)


if __name__ == "__main__":
    unittest.main()

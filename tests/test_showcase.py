#!/usr/bin/env python3
"""Regression tests for the public deterministic showcase."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "showcase" / "build_showcase.py"
FIXTURE = ROOT / "showcase" / "fixture" / "course.json"
OUTPUT = ROOT / "showcase" / "output"


class ShowcaseTests(unittest.TestCase):
    def run_builder(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUILDER), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def setUp(self) -> None:
        self.original_fixture = FIXTURE.read_bytes()

    def tearDown(self) -> None:
        # The builder owns generated output; tests leave a successful showcase
        # available for the optional browser check and for manual inspection.
        pass

    def test_builds_three_safe_artifacts(self) -> None:
        result = self.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = {
            "outline.html": ("关系模型", "details", "自测"),
            "quiz.html": ("第 1 题", "原题", "解析"),
            "graph.html": ("<svg", "<path", "★"),
        }
        for name, markers in expected.items():
            path = OUTPUT / name
            self.assertTrue(path.is_file(), name)
            text = path.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", text)
            for marker in markers:
                self.assertIn(marker, text)
            self.assertNotRegex(text, r"<script\s+[^>]*\bsrc\s*=|\bfetch\s*\(")
            self.assertNotRegex(text, r"[A-Za-z]:\\|(?<![A-Za-z0-9])/(?:home|Users|tmp)/")

        report = json.loads((ROOT / "showcase" / "verification.json").read_text(encoding="utf-8"))
        self.assertEqual(report["static_check"], "passed")
        self.assertEqual(report["browser_check"], "unavailable")
        self.assertEqual({item["name"] for item in report["artifacts"]}, set(expected))
        self.assertEqual(report["counts"], {"chapters": 2, "knowledge_points": 10, "questions": 10})
        self.assertEqual(set(report["artifacts"][i]["name"] for i in range(3)), set(expected))
        self.assertEqual(FIXTURE.read_bytes(), self.original_fixture)

    def test_rebuild_is_deterministic(self) -> None:
        first = self.run_builder()
        self.assertEqual(first.returncode, 0, first.stderr)
        first_hashes = {
            name: hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest()
            for name in ("outline.html", "quiz.html", "graph.html")
        }
        second = self.run_builder()
        self.assertEqual(second.returncode, 0, second.stderr)
        second_hashes = {
            name: hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest()
            for name in first_hashes
        }
        self.assertEqual(first_hashes, second_hashes)

    def test_rejects_extra_input_path(self) -> None:
        result = self.run_builder("private-course")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized arguments", result.stderr)

    def test_rejects_invalid_fixture_without_success_report(self) -> None:
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data["skeleton"]["chapters"] = []
        with tempfile.TemporaryDirectory() as temp:
            # Exercise the validator without changing the checked-in fixture.
            altered = Path(temp) / "course.json"
            altered.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            helper = (
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "from showcase.build_showcase import load_fixture; "
                "load_fixture(__import__('pathlib').Path(sys.argv[2]))"
            )
            result = subprocess.run(
                [sys.executable, "-c", helper, str(ROOT), str(altered)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not be empty", result.stderr)
        self.assertEqual(FIXTURE.read_bytes(), self.original_fixture)

    def test_rejects_wrong_typed_enum_values(self) -> None:
        helper = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from showcase.build_showcase import load_fixture; "
            "load_fixture(__import__('pathlib').Path(sys.argv[2]))"
        )
        cases = [("importance", []), ("type", {}), ("source", [])]
        with tempfile.TemporaryDirectory() as temp:
            for field, value in cases:
                data = json.loads(FIXTURE.read_text(encoding="utf-8"))
                if field == "importance":
                    data["skeleton"]["chapters"][0]["kcs"][0][field] = value
                else:
                    data["quiz"]["chapters"][0]["questions"][0][field] = value
                altered = Path(temp) / f"{field}.json"
                altered.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, "-c", helper, str(ROOT), str(altered)],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(field, result.stderr)

    def test_rejects_missing_fixture(self) -> None:
        helper = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from showcase.build_showcase import load_fixture; "
            "load_fixture(__import__('pathlib').Path(sys.argv[2]))"
        )
        missing = ROOT / "showcase" / "fixture" / "missing-course.json"
        result = subprocess.run(
            [sys.executable, "-c", helper, str(ROOT), str(missing)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fixture not found", result.stderr)

    def test_rejects_missing_json_section_and_illegal_field(self) -> None:
        helper = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from showcase.build_showcase import load_fixture; "
            "load_fixture(__import__('pathlib').Path(sys.argv[2]))"
        )
        cases = []
        missing_section = json.loads(FIXTURE.read_text(encoding="utf-8"))
        del missing_section["quiz"]
        cases.append(("missing field(s): quiz", missing_section))
        illegal_identifier = json.loads(FIXTURE.read_text(encoding="utf-8"))
        illegal_identifier["quiz"]["chapters"][0]["questions"][0]["id"] = 'bad"id'
        cases.append(("must contain only ASCII", illegal_identifier))
        with tempfile.TemporaryDirectory() as temp:
            for index, (expected, data) in enumerate(cases):
                altered = Path(temp) / f"case-{index}.json"
                altered.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, "-c", helper, str(ROOT), str(altered)],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
        self.assertEqual(FIXTURE.read_bytes(), self.original_fixture)


if __name__ == "__main__":
    unittest.main()

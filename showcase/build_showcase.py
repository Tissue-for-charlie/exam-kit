#!/usr/bin/env python3
"""Build the public, deterministic exam-kit showcase.

This command deliberately accepts no input path.  It renders only the checked-in
synthetic fixture, so a public demo cannot accidentally read a private course.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ARTIFACTS = {
    "outline.html": "复习提纲",
    "quiz.html": "复习题",
    "graph.html": "知识图谱",
}
IMPORTANCE = {"must", "key", "freq", "info"}
QUESTION_TYPES = {"choice", "multi", "tf", "fill", "short", "calc", "essay"}
SOURCES = {"original", "generated"}
DIFFICULTIES = {"easy", "medium", "hard"}

# These patterns are intentionally conservative: they catch common accidental
# leaks without treating ordinary HTML paths such as url(#arr) as file paths.
PII_PATTERNS = (
    ("email", re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)),
    ("phone", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")),
    ("windows path", re.compile(r"(?<![A-Za-z])[A-Za-z]:\\")),
    ("unc path", re.compile(r"\\\\[^\\\r\n]+")),
    ("unix path", re.compile(r"(?<![A-Za-z0-9])/(?:home|Users|tmp|var|etc|mnt|opt)/")),
    ("secret-like field", re.compile(r"\b(?:api[_-]?key|access[_-]?token|secret|password|cookie)\b", re.I)),
    ("external URL", re.compile(r"\b(?:https?|ftp)://|\bwww\.", re.I)),
)


def fail(message: str) -> None:
    raise ValueError(message)


def expect_dict(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{where} must be an object")
    return value


def expect_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{where} must be an array")
    return value


def expect_string(value: Any, where: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        fail(f"{where} must be a non-empty string")
    return value


def check_keys(obj: dict[str, Any], allowed: set[str], required: set[str], where: str) -> None:
    unknown = sorted(set(obj) - allowed)
    missing = sorted(required - set(obj))
    if unknown:
        fail(f"{where} has unsupported field(s): {', '.join(unknown)}")
    if missing:
        fail(f"{where} is missing field(s): {', '.join(missing)}")


def validate_safe_identifier(value: Any, where: str) -> str:
    identifier = expect_string(value, where)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", identifier):
        fail(f"{where} must contain only ASCII letters, digits, dot, underscore, or hyphen")
    return identifier


def validate_safe_display_text(value: Any, where: str) -> str:
    text = expect_string(value, where)
    if any(char in text for char in "<>&\\\"'"):
        fail(f"{where} must not contain HTML-significant characters")
    return text


def validate_skeleton(skeleton: Any) -> tuple[int, int, set[str]]:
    root = expect_dict(skeleton, "skeleton")
    check_keys(root, {"course", "chapters"}, {"course", "chapters"}, "skeleton")
    validate_safe_display_text(root["course"], "skeleton.course")
    chapters = expect_list(root["chapters"], "skeleton.chapters")
    if not chapters:
        fail("skeleton.chapters must not be empty")

    chapter_ids: set[str] = set()
    kc_ids: set[str] = set()
    kc_count = 0
    for ci, raw_chapter in enumerate(chapters):
        where = f"skeleton.chapters[{ci}]"
        chapter = expect_dict(raw_chapter, where)
        check_keys(chapter, {"id", "label", "summary", "kcs", "selftests"},
                   {"id", "label", "summary", "kcs", "selftests"}, where)
        chapter_id = validate_safe_identifier(chapter["id"], f"{where}.id")
        if chapter_id in chapter_ids:
            fail(f"duplicate chapter id: {chapter_id}")
        chapter_ids.add(chapter_id)
        validate_safe_display_text(chapter["label"], f"{where}.label")
        validate_safe_display_text(chapter["summary"], f"{where}.summary")
        kcs = expect_list(chapter["kcs"], f"{where}.kcs")
        if not kcs:
            fail(f"{where}.kcs must not be empty")
        for ki, raw_kc in enumerate(kcs):
            kc_where = f"{where}.kcs[{ki}]"
            kc = expect_dict(raw_kc, kc_where)
            check_keys(kc, {"id", "label", "importance", "content", "deps", "is_hub"},
                       {"id", "label", "importance", "content", "deps", "is_hub"}, kc_where)
            kc_id = validate_safe_identifier(kc["id"], f"{kc_where}.id")
            if kc_id in kc_ids:
                fail(f"duplicate knowledge-point id: {kc_id}")
            kc_ids.add(kc_id)
            validate_safe_display_text(kc["label"], f"{kc_where}.label")
            importance = kc["importance"]
            if not isinstance(importance, str) or importance not in IMPORTANCE:
                fail(f"{kc_where}.importance must be one of {sorted(IMPORTANCE)}")
            validate_safe_display_text(kc["content"], f"{kc_where}.content")
            deps = expect_list(kc["deps"], f"{kc_where}.deps")
            if not all(isinstance(dep, str) and re.fullmatch(r"[A-Za-z0-9._-]+", dep) for dep in deps):
                fail(f"{kc_where}.deps must contain safe knowledge-point identifiers")
            if not isinstance(kc["is_hub"], bool):
                fail(f"{kc_where}.is_hub must be boolean")
            kc_count += 1
        selftests = expect_list(chapter["selftests"], f"{where}.selftests")
        if not selftests:
            fail(f"{where}.selftests must not be empty")
        for si, raw_test in enumerate(selftests):
            st_where = f"{where}.selftests[{si}]"
            st = expect_dict(raw_test, st_where)
            check_keys(st, {"q", "a"}, {"q", "a"}, st_where)
            validate_safe_display_text(st["q"], f"{st_where}.q")
            validate_safe_display_text(st["a"], f"{st_where}.a")

    for chapter in chapters:
        for kc in chapter["kcs"]:
            for dep in kc["deps"]:
                if dep not in kc_ids:
                    fail(f"{kc['id']} refers to missing dependency: {dep}")
    return len(chapters), kc_count, kc_ids


def validate_answer(question: dict[str, Any], where: str) -> None:
    question_type = question["type"]
    answer = question["answer"]
    options = question.get("options")
    if question_type == "choice":
        if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < len(options):
            fail(f"{where}.answer must be a valid choice option index")
    elif question_type == "multi":
        if (not isinstance(answer, list) or not answer or any(not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(options) for i in answer)
                or len(set(answer)) != len(answer)):
            fail(f"{where}.answer must be unique valid multi-select option indexes")
    elif question_type == "tf":
        if not isinstance(answer, bool):
            fail(f"{where}.answer must be boolean for a true/false question")
    elif question_type == "fill":
        if not isinstance(answer, list) or not answer or not all(isinstance(item, str) and item.strip() for item in answer):
            fail(f"{where}.answer must be a non-empty string array for a fill question")
        if question["question"].count("___") < len(answer):
            fail(f"{where}.question must contain enough blanks for its fill answers")
    elif not isinstance(answer, str) or not answer.strip():
        fail(f"{where}.answer must be a non-empty string for a subjective question")


def validate_quiz(quiz: Any, chapter_ids: set[str], kc_ids: set[str]) -> int:
    root = expect_dict(quiz, "quiz")
    check_keys(root, {"course", "chapters"}, {"course", "chapters"}, "quiz")
    validate_safe_display_text(root["course"], "quiz.course")
    chapters = expect_list(root["chapters"], "quiz.chapters")
    if not chapters:
        fail("quiz.chapters must not be empty")
    seen_questions: set[str] = set()
    count = 0
    seen_sources: set[str] = set()
    for ci, raw_chapter in enumerate(chapters):
        where = f"quiz.chapters[{ci}]"
        chapter = expect_dict(raw_chapter, where)
        check_keys(chapter, {"id", "label", "questions"}, {"id", "label", "questions"}, where)
        chapter_id = validate_safe_identifier(chapter["id"], f"{where}.id")
        if chapter_id not in chapter_ids:
            fail(f"{where}.id does not match skeleton: {chapter_id}")
        validate_safe_display_text(chapter["label"], f"{where}.label")
        questions = expect_list(chapter["questions"], f"{where}.questions")
        if not questions:
            fail(f"{where}.questions must not be empty")
        for qi, raw_question in enumerate(questions):
            q_where = f"{where}.questions[{qi}]"
            q = expect_dict(raw_question, q_where)
            allowed = {"id", "type", "source", "source_ref", "kc_id", "difficulty", "points", "question", "options", "answer", "explanation", "pitfall"}
            required = {"id", "type", "source", "source_ref", "kc_id", "difficulty", "points", "question", "answer", "explanation", "pitfall"}
            check_keys(q, allowed, required, q_where)
            qid = validate_safe_identifier(q["id"], f"{q_where}.id")
            if qid in seen_questions:
                fail(f"duplicate question id: {qid}")
            seen_questions.add(qid)
            question_type = q["type"]
            if not isinstance(question_type, str) or question_type not in QUESTION_TYPES:
                fail(f"{q_where}.type must be one of {sorted(QUESTION_TYPES)}")
            source = q["source"]
            if not isinstance(source, str) or source not in SOURCES:
                fail(f"{q_where}.source must be one of {sorted(SOURCES)}")
            seen_sources.add(source)
            validate_safe_display_text(q["source_ref"], f"{q_where}.source_ref") if q["source_ref"] else None
            if source == "original" and not q["source_ref"].strip():
                fail(f"{q_where}.source_ref is required for original questions")
            if not isinstance(q["kc_id"], str) or q["kc_id"] not in kc_ids:
                fail(f"{q_where}.kc_id does not match skeleton: {q['kc_id']}")
            difficulty = q["difficulty"]
            if not isinstance(difficulty, str) or difficulty not in DIFFICULTIES:
                fail(f"{q_where}.difficulty must be one of {sorted(DIFFICULTIES)}")
            if not isinstance(q["points"], int) or isinstance(q["points"], bool) or q["points"] <= 0:
                fail(f"{q_where}.points must be a positive integer")
            for field in ("question", "explanation", "pitfall"):
                validate_safe_display_text(q[field], f"{q_where}.{field}")
            if q["type"] in {"choice", "multi"}:
                options = expect_list(q.get("options"), f"{q_where}.options")
                if len(options) < 2 or not all(isinstance(o, str) and o.strip() for o in options):
                    fail(f"{q_where}.options must contain at least two non-empty strings")
                for oi, option in enumerate(options):
                    validate_safe_display_text(option, f"{q_where}.options[{oi}]")
            elif "options" in q:
                fail(f"{q_where}.options is only allowed for choice and multi questions")
            validate_answer(q, q_where)
            count += 1
    if not {"original", "generated"}.issubset(seen_sources):
        fail("quiz must include both original and generated questions")
    return count


def scan_public_text(text: str, label: str) -> None:
    lines = text.splitlines()
    for name, pattern in PII_PATTERNS:
        for line_number, line in enumerate(lines, 1):
            if pattern.search(line):
                fail(f"{label}:{line_number} contains a prohibited {name} pattern")


def validate_report(report: dict[str, Any]) -> None:
    expect_dict(report, "verification")
    check_keys(report, {"version", "artifacts", "counts", "static_check", "browser_check"},
               {"version", "artifacts", "counts", "static_check", "browser_check"}, "verification")
    if report["version"] != "1":
        fail("verification.version must be '1'")
    artifacts = expect_list(report["artifacts"], "verification.artifacts")
    if len(artifacts) != 3:
        fail("verification.artifacts must contain exactly three items")
    names = set()
    for i, raw_artifact in enumerate(artifacts):
        where = f"verification.artifacts[{i}]"
        artifact = expect_dict(raw_artifact, where)
        check_keys(artifact, {"name", "size_bytes", "sha256"}, {"name", "size_bytes", "sha256"}, where)
        if artifact["name"] not in ARTIFACTS or artifact["name"] in names:
            fail(f"{where}.name must be a unique known artifact name")
        names.add(artifact["name"])
        if not isinstance(artifact["size_bytes"], int) or artifact["size_bytes"] < 1:
            fail(f"{where}.size_bytes must be a positive integer")
        if not isinstance(artifact["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]):
            fail(f"{where}.sha256 must be a lowercase SHA-256 digest")
    counts = expect_dict(report["counts"], "verification.counts")
    check_keys(counts, {"chapters", "knowledge_points", "questions"},
               {"chapters", "knowledge_points", "questions"}, "verification.counts")
    for key in counts:
        if not isinstance(counts[key], int) or counts[key] < 1:
            fail(f"verification.counts.{key} must be a positive integer")
    if report["static_check"] != "passed":
        fail("verification.static_check must be 'passed'")
    if report["browser_check"] not in {"passed", "unavailable"}:
        fail("verification.browser_check must be 'passed' or 'unavailable'")


def load_fixture(path: Path) -> tuple[dict[str, Any], dict[str, Any], int, int, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"fixture not found: {path.as_posix()}")
    except json.JSONDecodeError as exc:
        fail(f"fixture is not valid JSON: line {exc.lineno}, column {exc.colno}")
    root = expect_dict(data, "fixture")
    check_keys(root, {"course", "skeleton", "quiz"}, {"course", "skeleton", "quiz"}, "fixture")
    expect_string(root["course"], "fixture.course")
    # Scan before rendering so the public input is safe by construction.
    scan_public_text(path.read_text(encoding="utf-8"), "fixture")
    skeleton = expect_dict(root["skeleton"], "fixture.skeleton")
    quiz = expect_dict(root["quiz"], "fixture.quiz")
    chapter_count, kc_count, kc_ids = validate_skeleton(skeleton)
    chapter_ids = {ch["id"] for ch in skeleton["chapters"]}
    question_count = validate_quiz(quiz, chapter_ids, kc_ids)
    return skeleton, quiz, chapter_count, kc_count, question_count


def renderer_output(work: Path, course: str, suffix: str) -> Path:
    safe = re.sub(r'[\\/:*?"<>|]', "_", course)
    return work / f"{safe}-{suffix}.html"


def run_renderer(script: Path, work: Path, label: str) -> None:
    try:
        result = subprocess.run(
            [sys.executable, str(script), str(work)],
            cwd=str(script.parent.parent),
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"{label} failed to run: {exc}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        fail(f"{label} failed with exit code {result.returncode}: {detail[-1200:]}")


def check_artifact(path: Path, required: tuple[str, ...], label: str) -> bytes:
    if not path.is_file():
        fail(f"missing renderer output: {path.name}")
    raw = path.read_bytes()
    if not raw.strip():
        fail(f"renderer output is empty: {path.name}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        fail(f"renderer output is not UTF-8: {path.name}")
    if "<!DOCTYPE html>" not in text or "<html" not in text:
        fail(f"{label} is not a complete HTML document")
    for marker in required:
        if marker not in text:
            fail(f"{label} is missing required marker: {marker}")
    scan_public_text(text, label)
    if re.search(
        r"<script\s+[^>]*\bsrc\s*=|<(?:link|img|iframe|audio|video|source)\b[^>]*\b(?:src|href)\s*=|"
        r"\b(?:cdn|unpkg|jsdelivr)\b|\bfetch\s*\(|@import\s+|url\(\s*[^#'\"\s)]",
        text,
        re.I,
    ):
        fail(f"{label} contains an external or network dependency")
    return raw


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build() -> dict[str, Any]:
    root = Path(__file__).resolve().parent.parent
    fixture_path = root / "showcase" / "fixture" / "course.json"
    output = root / "showcase" / "output"
    scripts = root / "scripts"
    report_path = output.parent / "verification.json"
    output.mkdir(parents=True, exist_ok=True)
    skeleton, quiz, chapters, knowledge_points, questions = load_fixture(fixture_path)
    course = skeleton["course"]
    if quiz["course"] != course:
        fail("fixture.skeleton.course and fixture.quiz.course must match")

    with tempfile.TemporaryDirectory(prefix="exam-kit-showcase-") as tmp:
        work = Path(tmp)
        prep = work / ".final_prep"
        prep.mkdir()
        (prep / "knowledge_skeleton.json").write_text(
            json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (prep / "questions.json").write_text(
            json.dumps(quiz, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run_renderer(scripts / "render_outline.py", work, "outline renderer")
        run_renderer(scripts / "render_quiz.py", work, "quiz renderer")
        run_renderer(scripts / "render_graph.py", work, "graph renderer")

        sources = {
            "outline.html": (renderer_output(work, course, "复习提纲"),
                             ("MySQL Study Demo", "关系模型", "details", "自测")),
            "quiz.html": (renderer_output(work, course, "复习题"),
                          ("MySQL Study Demo", "第 1 题", "原题", "解析")),
            "graph.html": (renderer_output(work, course, "知识图谱"),
                           ("MySQL Study Demo", "<svg", "<path", "★")),
        }
        raw_artifacts: dict[str, bytes] = {}
        for name, (path, markers) in sources.items():
            raw_artifacts[name] = check_artifact(path, markers, name)

        # Stage only after all renderers and checks succeed.  Replacing fixed
        # names prevents stale names generated from a fixture edit.
        with tempfile.TemporaryDirectory(prefix="exam-kit-output-", dir=str(output)) as stage_name:
            stage = Path(stage_name)
            for name, (source, _) in sources.items():
                staged = stage / name
                shutil.copyfile(source, staged)
                staged.replace(output / name)

    artifacts = [
        {"name": name, "size_bytes": len(raw), "sha256": sha256(raw)}
        for name, raw in raw_artifacts.items()
    ]
    report = {
        "version": "1",
        "artifacts": artifacts,
        "counts": {
            "chapters": chapters,
            "knowledge_points": knowledge_points,
            "questions": questions,
        },
        "static_check": "passed",
        "browser_check": "unavailable",
    }
    validate_report(report)
    # The report contains only fixed artifact names and aggregate metadata.
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic public showcase")
    parser.parse_args()
    try:
        report = build()
    except (OSError, ValueError) as exc:
        print(f"showcase build failed: {exc}", file=sys.stderr)
        return 1
    print(f"showcase build passed: {len(report['artifacts'])} artifacts")
    for artifact in report["artifacts"]:
        print(f"  {artifact['name']} ({artifact['size_bytes']} bytes)")
    print("  browser_check: unavailable (no browser check requested by builder)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

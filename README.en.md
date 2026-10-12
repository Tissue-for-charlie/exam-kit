# exam-kit

[中文](README.md) · **English**

[![license: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](requirements.txt)
[![check](https://github.com/Tissue-for-charlie/exam-kit/actions/workflows/verify.yml/badge.svg)](https://github.com/Tissue-for-charlie/exam-kit/actions/workflows/verify.yml)

See [CHANGELOG.md](CHANGELOG.md) for release notes: latest **V1.1.0** (2026.10.12), previous V1.0.0 (2026.9.16).

> Turn scattered course slides into three offline review tools — printable, no CDN, no API.

`exam-kit` reads your PPT / Word / PDF / slide photos and produces three **self-contained HTML files** you can open anywhere, print to PDF, and keep offline.

| Output | What you do with it | Preview |
|---|---|---|
| **Study outline** | Memorize chapter by chapter: magazine-style chapter cards, four-colour importance tags on every knowledge point, and `content` that automatically renders comparisons and parallel points as **comparison tables, flows and categories** (no walls of text); a collapsible self-test at the end of each chapter | [![Study outline preview](showcase/preview/outline-thumb.png)](showcase/preview/outline.png) |
| **Quiz** | Answer question by question with instant auto-grading and per-question explanations; **speed run** lists the whole filtered set for scrolling practice; **mock exam** (custom duration, graded on submit); **wrong-answer book + export wrong answers as HTML / print two papers / export to Word**; **question navigator** renumbered by the current filter with click-to-jump; **search**, **star** and **lucky-guess** flags | [![Quiz preview](showcase/preview/quiz-thumb.png)](showcase/preview/quiz.png) |
| **Quiz · wrong-answer export** | A standalone offline HTML generated from the quiz in one click: wrong answers only, answers expanded, printable (follows the "hide AI questions" toggle; includes no question navigator or redo button) | [![Wrong-answer export preview](showcase/preview/wrong-thumb.png)](showcase/preview/wrong.png) |
| **Knowledge graph** | **Radial overview** (course → one ring of chapters); click a chapter to expand its knowledge points outwards, click a bubble for structured details; full-screen mode | [![Knowledge graph preview](showcase/preview/graph-thumb.png)](showcase/preview/graph.png) |

<sub>All three are single-file, openable offline and printable; desktop and mobile are adapted separately (mobile tables and font sizes are handled). Thumbnails are small desktop shots — click them for the full size.</sub>

## See results in 3 minutes

Run the deterministic demo first (no network, no model calls, never touches your course directory — it only renders the public demo data in this repo):

```bash
python -m pip install -r requirements.txt
python showcase/build_showcase.py
```

Open the three HTML files under `showcase/output/` in a browser to try every interaction. The verification summary is written to `showcase/verification.json` (artifact sizes + SHA-256 + counts); its schema lives in `showcase/expected/`.

## Install as an Agent Skill

This repo follows the [Agent Skills open specification](https://agentskills.io/specification): `SKILL.md` sits at the repo root and `name: exam-kit` matches the directory name.

**Option 1 · one command with skills.sh** (works with Claude Code / Codex / Cursor / OpenClaw and more):

```bash
npx skills add Tissue-for-charlie/exam-kit
```

**Option 2 · place it manually**: put the whole repo into your agent's skill directory, keeping `SKILL.md` and `scripts/` side by side.

- Claude Code: `~/.claude/skills/exam-kit/` (global) or `.claude/skills/exam-kit/` inside a project
- Codex / OpenClaw / others: follow that agent's own skill-directory convention

Once installed, say:

```text
Use exam-kit on this course's PPT, PDF and Word materials: scan them and group by chapter first, then extract the text; next build the knowledge skeleton and the original-question list; finally render the study outline, the quiz and the knowledge graph as three offline HTML files. Keep the source of every original question, and clearly flag anything the materials cannot confirm.
```

Or simply say:

- "Help me put together revision materials for this course."
- "Generate a study outline and self-test questions from these slides."
- "Organise these PDFs, slides and whiteboard photos chapter by chapter."
- "Mark the must-know exam points and give each one a question."
- "Draw a dependency map of this course."

## How it differs from similar tools

| | Typical "slides to notes" tools | **exam-kit** |
|---|---|---|
| Output | One notes file / document | **Three forms**: an outline for memorizing + an interactive graded question bank + a dependency graph, all printable offline HTML |
| Where questions come from | The model makes them up | Reuses the questions already in your materials (examples / homework / past papers); every question is tagged `original` or `generated` with its source — **never invents a source** |
| Verifiability | Run it and hope | The public demo rebuilds deterministically: artifact SHA, PII scan, schema checks, and the three README previews can be re-recorded |

It splits the work: scripts do the mechanical extraction and rendering, the agent does the understanding and question writing. Reading images and synthesising whole documents is up to the agent, but the steps, intermediate artifacts and contracts are explicit and checkable.

## How it actually works

```text
course materials
  → scan.py: scan and group by chapter
  → extract.py: extract text, record images for the multimodal agent
  → Agent: build the knowledge skeleton, extract original questions, fill the gaps, label sources
  → render_outline.py / render_quiz.py / render_graph.py
  → three single-file HTML outputs
```

Images are not OCR'd: images and images embedded in slides are recorded by path and read directly by a vision-capable agent.

## Boundaries between the public demo and real courses

`showcase/fixture/course.json` is an independently worded **derived demo**, not a copy of any real course. It contains no real slides, images, continuous source text, teacher/school/student information or local paths.

The public build only proves the deterministic rendering chain "prepared skeleton + question bank → three offline HTML files". The full real-course flow is driven by the agent on the materials you provide; `showcase/build_showcase.py` accepts no arbitrary input path, never reads a real course directory, and never publishes materials after auto-redacting them.

## Working with real materials

For real course materials the agent follows this path:

```bash
python <skill-dir>/scripts/scan.py "<course-dir>"
python <skill-dir>/scripts/extract.py "<course-dir>"
# The agent reads the .final_prep intermediates and writes knowledge_skeleton.json / questions.json
python <skill-dir>/scripts/render_outline.py "<course-dir>"
python <skill-dir>/scripts/render_quiz.py "<course-dir>"
python <skill-dir>/scripts/render_graph.py "<course-dir>"
```

Install dependencies on first use:

```bash
python -m pip install -r requirements.txt
```

Legacy binary `.ppt` files may not be readable by `python-pptx` — convert them to `.pptx` first. Scanned PDFs have no text layer and must be read by the agent directly. A failing step does not stop the flow: the agent falls back to reading the files with its own tools.

## Safety boundaries

- Course materials are never uploaded automatically and no external API is called.
- Real material files are never deleted or overwritten automatically.
- The public showcase accepts no arbitrary input paths, so it cannot read private directories by accident.
- `original` is only used for questions that really exist in the materials and can be answered on their own.
- Public fixtures and generated HTML are checked for common emails, phone numbers, absolute paths, secret fields and external network dependencies.
- Automated checks are not a substitute for copyright permission; whether real slides may be published is still for the user to confirm.

## Repository layout

```text
SKILL.md                         # agent workflow, JSON contracts, trigger description
scripts/                         # scanning, extraction and the three HTML renderers
showcase/
├── fixture/course.json          # independently worded public demo data (skeleton + question-bank schema sample)
├── build_showcase.py            # deterministic build + PII/static safety checks → showcase/output
├── screenshot_showcase.py       # re-record the README previews (three products + wrong-answer export) → showcase/preview
├── preview/*.png                # README previews (checked in)
├── expected/                    # verification.json schema contract
└── output/                      # build artifacts (gitignored, not committed)
tests/                           # build regression + optional browser acceptance
```

## Verification

```bash
python -m py_compile showcase/*.py scripts/*.py tests/*.py
python showcase/build_showcase.py
python -m unittest discover -s tests -v
python -m json.tool showcase/fixture/course.json
python tests/browser_showcase.py          # optional: local Playwright + Chromium
python showcase/screenshot_showcase.py    # optional: re-record README previews
```

Browser/screenshot acceptance only uses a Playwright/Chromium that is already installed locally; it never downloads a browser and honestly reports `unavailable` when none is usable. CI (`.github/workflows/verify.yml`) runs compilation, the build and the full test suite on Ubuntu and Windows. If some commands print garbled text on Windows, set `PYTHONUTF8=1` first.

## License

[MIT](LICENSE)

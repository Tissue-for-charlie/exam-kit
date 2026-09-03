#!/usr/bin/env python3
"""Regenerate the committed README preview images.

Captures the three deterministic showcase HTML products into
``showcase/preview/{outline,quiz,graph}.png`` so the GitHub README shows
real results without linking to gitignored build output.

Requirements: a local Playwright plus a browser it can launch. The script
prefers a system Chrome/Edge (channel="chrome" / "msedge"), then falls back
to the Playwright-bundled Chromium. When no browser is usable it reports
``unavailable`` and exits 0, leaving any existing previews untouched, so CI
and fresh clones are never blocked.

The capture is deterministic for a given fixture and renderer: fixed
viewport, no animations to wait on, and the quiz preview clicks the first
option of question 1 (a correct choice) to show auto-grading plus the
explanation panel.

Usage:
    python showcase/screenshot_showcase.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "showcase" / "build_showcase.py"
OUTPUT = ROOT / "showcase" / "output"
PREVIEW = ROOT / "showcase" / "preview"

# (preview name, product file, click first option?, full-page capture?)
TARGETS = (
    ("outline", "outline.html", False, False),
    ("quiz", "quiz.html", True, False),      # click first option (a correct one)
    ("graph", "graph.html", False, True),    # whole-graph tall canvas
)


def build() -> None:
    """Ensure fresh outputs; deterministic and fast."""
    subprocess.run(
        [sys.executable, str(BUILDER)],
        cwd=str(ROOT), check=True,
    )


def capture(browser) -> dict[str, int]:
    sizes: dict[str, int] = {}
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for name, fname, click, full_page in TARGETS:
        viewport = {"width": 780, "height": 1000}
        page = browser.new_page(viewport=viewport, device_scale_factor=1)
        try:
            page.goto((OUTPUT / fname).as_uri(), wait_until="load")
            page.wait_for_timeout(400)
            if click:
                page.evaluate(
                    "document.querySelector('.options .option')?.click()")
                page.wait_for_timeout(250)
            page.screenshot(path=str(PREVIEW / f"{name}.png"),
                            full_page=full_page)
            sizes[name] = (PREVIEW / f"{name}.png").stat().st_size
        finally:
            page.close()
    return sizes


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("preview: unavailable (playwright not installed)")
        return 0
    build()
    with sync_playwright() as p:
        browser = None
        for channel in ("chrome", "msedge"):
            try:
                browser = p.chromium.launch(channel=channel, headless=True)
                break
            except Exception:
                continue
        if browser is None:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception:
                print("preview: unavailable (no usable chromium/chrome/edge)")
                return 0
        try:
            sizes = capture(browser)
        finally:
            browser.close()
    for name, size in sizes.items():
        print(f"  preview/{name}.png ({size} bytes)")
    print("preview: regenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regenerate the committed README preview images.

Captures the three deterministic showcase HTML products at a desktop-viewport
aspect into ``showcase/preview/{outline,quiz,graph}.png`` (full size), and
writes small equal-ratio thumbnails ``*-thumb.png`` alongside. The README
displays a thumbnail and links to the full-size image, so a click opens the
real desktop-resolution screenshot.

Requirements: a local Playwright plus a browser it can launch. The script
prefers a system Chrome/Edge (channel="chrome" / "msedge"), then falls back to
the Playwright-bundled Chromium. When no browser is usable it reports
``unavailable`` and exits 0, leaving any existing previews untouched, so CI
and fresh clones are never blocked. Thumbnailing uses Pillow; when Pillow is
missing the full-size captures are still produced and the thumb step is
skipped with a note.

The capture is deterministic for a given fixture and renderer: fixed desktop
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

# (preview name, product file, click first option?, viewport width, height)
# One desktop window per product; the two-column outline, the single-screen
# quiz app, and the graph hero each get enough room to read as themselves.
TARGETS = (
    ("outline", "outline.html", False, 1280, 820),
    ("quiz", "quiz.html", True, 1280, 920),  # click first option (a correct one)
    ("graph", "graph.html", False, 1280, 880),
)

# Display width of the README thumbnails; full-size images keep their own px.
THUMB_WIDTH = 340


def build() -> None:
    """Ensure fresh outputs; deterministic and fast."""
    subprocess.run(
        [sys.executable, str(BUILDER)],
        cwd=str(ROOT), check=True,
    )


def capture(browser) -> dict[str, int]:
    sizes: dict[str, int] = {}
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for name, fname, click, width, height in TARGETS:
        page = browser.new_page(viewport={"width": width, "height": height},
                                device_scale_factor=1)
        try:
            page.goto((OUTPUT / fname).as_uri(), wait_until="load")
            page.wait_for_timeout(400)
            if click:
                page.evaluate(
                    "document.querySelector('.options .option')?.click()")
                page.wait_for_timeout(250)
            page.screenshot(path=str(PREVIEW / f"{name}.png"))
            sizes[name] = (PREVIEW / f"{name}.png").stat().st_size
        finally:
            page.close()
    return sizes


def make_thumbnails(sizes: dict[str, int]) -> dict[str, int]:
    """Downscale each full capture to a small README thumbnail (Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        print("  thumbnails: skipped (Pillow not installed)")
        return {}
    thumbs: dict[str, int] = {}
    for name in sizes:
        src = PREVIEW / f"{name}.png"
        im = Image.open(src)
        ratio = THUMB_WIDTH / im.width
        im = im.resize((THUMB_WIDTH, max(1, round(im.height * ratio))),
                       Image.LANCZOS)
        out = PREVIEW / f"{name}-thumb.png"
        im.save(out)
        thumbs[name] = out.stat().st_size
    return thumbs


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
    thumbs = make_thumbnails(sizes)
    for name, size in sizes.items():
        note = f"  thumb {thumbs[name]} bytes" if name in thumbs else "  no thumb"
        print(f"  preview/{name}.png ({size} bytes), {note}")
    print("preview: regenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

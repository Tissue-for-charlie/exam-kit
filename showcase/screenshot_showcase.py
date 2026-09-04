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


def capture_export_wrong(browser) -> dict[str, int]:
    """答错一道题后点「导出错题」，把导出的离线 HTML 也截成一张预览。"""
    sizes: dict[str, int] = {}
    page = browser.new_page(viewport={"width": 1280, "height": 920},
                            accept_downloads=True, device_scale_factor=1)
    try:
        page.goto((OUTPUT / "quiz.html").as_uri(), wait_until="load")
        page.wait_for_timeout(350)
        # 进入极速刷题，给第一道单选题答一个错误选项
        pick = page.evaluate("""() => {
            document.querySelector(".mode-btn[data-mode='fast']")?.click();
            return new Promise(function(res){ setTimeout(function(){
                var card = document.querySelector(".q-card.fastShow[data-type='choice']");
                if(!card){ res(null); return; }
                var qid = card.getAttribute('data-qid');
                var m = {}; QUIZ.chapters.forEach(function(ch){ (ch.questions||[]).forEach(function(q){ m[q.id]=q; }); });
                var q = m[qid];
                var opts = card.querySelectorAll('.option');
                var wrong = (q.answer + 1) % opts.length;
                opts[wrong].click();
                res({qid:qid, n:opts.length});
            }, 120); });
        }""")
        page.wait_for_timeout(250)
        if pick is None:
            print("  wrong-export: skipped (no choice found)")
            return sizes
        # 点「导出错题」并把下载的文件落到 showcase/output/wrong-quiz.html
        out = OUTPUT / "wrong-quiz.html"
        with page.expect_download() as dl:
            page.evaluate("document.getElementById('exportWrongBtn')?.click()")
        dl.value.save_as(str(out))
        page.close()

        view = browser.new_page(viewport={"width": 1280, "height": 920},
                                device_scale_factor=1)
        try:
            view.goto(out.as_uri(), wait_until="load")
            view.wait_for_timeout(300)
            view.screenshot(path=str(PREVIEW / "wrong.png"))
            sizes["wrong"] = (PREVIEW / "wrong.png").stat().st_size
        finally:
            view.close()
    except Exception as exc:  # noqa: BLE001 — preview must never break CI
        print(f"  wrong-export: skipped ({exc})")
        try:
            page.close()
        except Exception:
            pass
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
            sizes.update(capture_export_wrong(browser))
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

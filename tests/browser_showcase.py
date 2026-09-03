#!/usr/bin/env python3
"""Optional browser acceptance check for exam-kit's public showcase.

The script never downloads a browser.  It uses Playwright only when it is
already installed and has an available Chromium executable; otherwise it
reports browser_check: unavailable and exits successfully.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "showcase" / "output"


def update_report_status(status: str) -> None:
    report_path = ROOT / "showcase" / "verification.json"
    if not report_path.is_file():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["browser_check"] = status
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(report_path)


def unavailable(reason: str) -> int:
    update_report_status("unavailable")
    print(f"browser_check: unavailable ({reason})")
    return 0


def ensure_showcase() -> bool:
    return all((OUTPUT / name).is_file() for name in ("outline.html", "quiz.html", "graph.html"))


def run() -> int:
    if not ensure_showcase():
        return unavailable("run showcase/build_showcase.py first")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return unavailable("Playwright is not installed")

    try:
        with sync_playwright() as playwright:
            executable = playwright.chromium.executable_path
            if not Path(executable).is_file():
                return unavailable("Chromium executable is not installed")
            browser = playwright.chromium.launch(headless=True)
            try:
                desktop = browser.new_page(viewport={"width": 1440, "height": 900})
                mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
                cases = {
                    "outline.html": [".sidebar", "details.selftest", ".course-title"],
                    "quiz.html": [".q-card", ".option", ".answer-static"],
                    "graph.html": ["svg#g", ".graph-stage", ".node"],
                }
                for name, selectors in cases.items():
                    url = (OUTPUT / name).resolve().as_uri()
                    desktop.goto(url, wait_until="load")
                    desktop.wait_for_timeout(100)
                    for selector in selectors:
                        if desktop.locator(selector).count() < 1:
                            raise RuntimeError(f"{name} is missing {selector}")
                    title = desktop.title()
                    if "MySQL Study Demo" not in title:
                        raise RuntimeError(f"{name} has unexpected title: {title}")
                    desktop.emulate_media(media="print")
                    if name == "quiz.html":
                        if desktop.locator(".answer-static").count() < 1:
                            raise RuntimeError("quiz print view is missing answers")
                        if desktop.locator(".q-stem").count() < 1 or desktop.locator(".as-exp").count() < 1:
                            raise RuntimeError("quiz print view is missing question or explanation")
                    desktop.emulate_media(media="screen")

                    if name == "quiz.html":
                        first_option = desktop.locator(".q-card.active .option").first
                        first_option.click()
                        if not first_option.evaluate("el => el.classList.contains('selected')"):
                            raise RuntimeError("quiz option click did not select an answer")
                        if desktop.locator(".q-card.active.answered").count() != 1:
                            raise RuntimeError("quiz choice click did not auto-submit")
                    elif name == "graph.html":
                        svg = desktop.locator("svg#g")
                        before = svg.get_attribute("style") or ""
                        svg.hover()
                        desktop.mouse.wheel(0, -100)
                        desktop.wait_for_timeout(50)
                        after = svg.get_attribute("style") or ""
                        if before == after:
                            raise RuntimeError("graph zoom interaction did not change SVG transform")

                    mobile.goto(url, wait_until="load")
                    overflow = mobile.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
                    if overflow:
                        raise RuntimeError(f"{name} has horizontal overflow at mobile width")
                    if name == "outline.html":
                        mobile.locator("#sb-toggle").click()
                        if mobile.locator("body.sb-open, body.sb-collapsed").count() != 1:
                            raise RuntimeError("outline mobile navigation did not change state")
                    if name == "quiz.html":
                        nav = mobile.locator(".nav-fixed")
                        if nav.count() < 1:
                            raise RuntimeError("quiz mobile view is missing fixed navigation")
                        obscures_content = mobile.evaluate(
                            """() => {
                                const nav = document.querySelector('.nav-fixed');
                                const card = document.querySelector('.q-card.active');
                                if (!nav || !card) return true;
                                const navBox = nav.getBoundingClientRect();
                                const cardBox = card.getBoundingClientRect();
                                return cardBox.bottom > navBox.top && cardBox.bottom < navBox.bottom;
                            }"""
                        )
                        if obscures_content:
                            raise RuntimeError("quiz mobile navigation obscures active content")
            finally:
                browser.close()
    except Exception as exc:
        print(f"browser_check: failed ({exc})", file=sys.stderr)
        return 1

    update_report_status("passed")
    print("browser_check: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

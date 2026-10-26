#!/usr/bin/env python3
"""Static contracts for the interactive wrong-question HTML exporter."""
from __future__ import annotations

import unittest

from scripts import wrong_export


class WrongExportStaticTests(unittest.TestCase):
    def test_export_assets_are_self_contained(self) -> None:
        css = wrong_export.WRONG_EXPORT_CSS
        body = wrong_export.WRONG_EXPORT_BODY
        runtime = wrong_export.WRONG_EXPORT_RUNTIME
        combined = "\n".join((css, body, runtime, wrong_export.WRONG_EXPORT_CLIENT_JS))

        self.assertIn("--wx-accent: #1a1a2e", css)
        self.assertIn("--wx-accent-2: #1565c0", css)
        self.assertIn("--wx-correct: #2e7d32", css)
        self.assertIn("--wx-wrong: #c62828", css)
        self.assertIn("--wx-partial: #b26a00", css)
        self.assertIn('id="wxData"', body)
        self.assertIn('id="wxPrintRoot"', body)
        self.assertNotIn("<script src=", combined)
        self.assertNotIn("https://", combined)
        self.assertNotIn("http://", combined)
        self.assertNotIn("fetch(", combined)
        self.assertNotIn("@import", combined)

    def test_runtime_owns_interactive_state(self) -> None:
        runtime = wrong_export.WRONG_EXPORT_RUNTIME
        for marker in (
            "STORAGE_KEY",
            "localStorage",
            "restoreState",
            "filteredIds",
            "toggleRandom",
            "toggleReveal",
            "submitQuestion",
            "preparePrint",
            "window.WrongExport",
        ):
            self.assertIn(marker, runtime)

    def test_browser_builder_uses_dedicated_page_instead_of_cloned_quiz_dom(self) -> None:
        client = wrong_export.WRONG_EXPORT_CLIENT_JS
        self.assertIn("buildWrongExportHtml", client)
        self.assertIn("wrongExportPayload", client)
        self.assertIn("exportDate", client)
        self.assertIn("WRONG_EXPORT_ASSETS", client)
        self.assertIn("createObjectURL", client)
        self.assertIn(".replace('__WRONG_EXPORT_DATA__', function()", client)
        self.assertNotIn("cloneNode(true)", client)
        self.assertNotIn("document.querySelectorAll('style')", client)

    def test_export_page_has_pc_mobile_and_print_contracts(self) -> None:
        css = wrong_export.WRONG_EXPORT_CSS
        body = wrong_export.WRONG_EXPORT_BODY
        self.assertIn("@media (max-width: 860px)", css)
        self.assertIn("@media print", css)
        self.assertIn("env(safe-area-inset-bottom", css)
        self.assertIn("wx-print-write", css)
        self.assertIn('id="wxMore"', body)
        self.assertIn('id="wxSheetDrill"', body)
        self.assertIn('id="wxSheetReview"', body)
        self.assertIn('data-wx-print="answers"', body)
        self.assertIn('data-wx-print="blank"', body)
        self.assertIn(".wx-option.is-missed {", css)
        self.assertIn("border-style: dashed;", css)
        self.assertIn("wx-result-your", wrong_export.WRONG_EXPORT_RUNTIME)
        self.assertIn("wx-result-counts", wrong_export.WRONG_EXPORT_RUNTIME)

    def test_scrollbar_sidebar_and_keyboard_swipe_contracts(self) -> None:
        css = wrong_export.WRONG_EXPORT_CSS
        runtime = wrong_export.WRONG_EXPORT_RUNTIME
        self.assertIn("scrollbar-width: none", css)
        self.assertIn("::-webkit-scrollbar", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", css)
        self.assertIn("flex: 1 1 auto;", css)
        for marker in (
            "optionValueForKey",
            "ArrowLeft",
            "ArrowUp",
            "ArrowRight",
            "ArrowDown",
            "touchstart",
            "touchmove",
            "touchend",
            "swipeBlocked",
        ):
            self.assertIn(marker, runtime)


if __name__ == "__main__":
    unittest.main()

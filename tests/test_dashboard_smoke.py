"""Headless smoke test: run every dashboard page via Streamlit's AppTest.

Run:  python tests/test_dashboard_smoke.py
Fails loudly if any page raises a runtime exception.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest

PAGES = [
    "pages/overview.py",
    "pages/explorer.py",
    "pages/calculator.py",
    "pages/data_quality.py",
]


def run_page(rel_path: str) -> None:
    at = AppTest.from_file(str(ROOT / rel_path), default_timeout=90)
    at.run()
    if at.exception:
        msgs = "\n".join(f"  - {getattr(e, 'value', e)}" for e in at.exception)
        raise AssertionError(f"Page {rel_path} raised:\n{msgs}")
    assert at.main is not None, f"{rel_path} produced no content"
    print(f"[ok] {rel_path}")


def test_app_boots() -> None:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    assert not at.exception, f"app.py raised: {[getattr(e,'value',e) for e in at.exception]}"
    print("[ok] app.py (navigation + default page)")


if __name__ == "__main__":
    test_app_boots()
    for p in PAGES:
        run_page(p)
    print("\nDASHBOARD SMOKE TEST PASSED ✅")

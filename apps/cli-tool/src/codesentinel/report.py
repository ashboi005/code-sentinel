from __future__ import annotations

from pathlib import Path


REPORT_NAME = "codesentinel-report.md"
FIX_REPORT_NAME = "fix.md"


def write_report(scan_root: Path, markdown: str) -> Path:
    report_path = scan_root / REPORT_NAME
    report_path.write_text(markdown.strip() + "\n", encoding="utf-8")
    return report_path


def write_fix_report(target_root: Path, markdown: str) -> Path:
    fix_report_path = target_root / FIX_REPORT_NAME
    fix_report_path.write_text(markdown.strip() + "\n", encoding="utf-8")
    return fix_report_path

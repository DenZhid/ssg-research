"""Append the build stamp and cache summary to every page."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_INFO_PATH = ROOT / "output" / "build-info.json"
REPORT_PATH = ROOT / "output" / "cache-report.json"


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _seconds(value: object) -> str:
    try:
        return f"{float(value):.3f} с"
    except (TypeError, ValueError):
        return "—"


def _cell(value: object) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def _stamp_markdown() -> str:
    info = _load(BUILD_INFO_PATH)
    report = _load(REPORT_PATH)
    if info is None and report is None:
        return ""

    rows: list[str] = []
    if info is not None:
        rows.extend(
            [
                f"| Хеш коммита | `{_cell(info.get('commit'))}` |",
                f"| Дата сборки | `{_cell(info.get('built_at'))}` |",
                f"| Версия набора данных | `{_cell(info.get('dataset_version'))}` |",
            ]
        )
    if report is not None:
        rows.extend(
            [
                f"| Попаданий в кэш | {_cell(report.get('hits'))} |",
                f"| Промахов | {_cell(report.get('misses'))} |",
                f"| Холодный пересчёт | {_seconds(report.get('cold_elapsed_s'))} |",
                f"| Этот проход | {_seconds(report.get('elapsed_s'))} |",
                f"| Выигрыш | {_seconds(report.get('saved_s'))} |",
            ]
        )

    lines = ["## Сборка", "", "| | |", "|---|---|", *rows, ""]
    passes = report.get("passes") if report is not None else None
    if isinstance(passes, list):
        bits = [
            f"проход {item.get('name', '—')} — {_seconds(item.get('elapsed_s'))}"
            for item in passes
            if isinstance(item, dict)
        ]
        if bits:
            lines.append("Замер двух проходов: " + ", ".join(bits) + ".")
            lines.append("")
    return "\n".join(lines).rstrip()


def on_page_markdown(markdown, page, config, files, **_kwargs):
    block = _stamp_markdown()
    if not block:
        return markdown
    return markdown.rstrip() + "\n\n" + block + "\n"

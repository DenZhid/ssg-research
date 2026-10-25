"""Shared helpers for loading and parsing PWA e2e metrics reports."""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INPUT_DIR = PROJECT_ROOT / 'input'
OUTPUT_DIR = PROJECT_ROOT / 'output'
REPORTS_DIR = INPUT_DIR

METRIC_FULL_NAMES = [
    'First Contentful Paint',
    'Time to Interactive',
    'First Input Delay',
    'Total Blocking Time',
    'Largest Contentful Paint',
    'Cumulative Layout Shift',
]

METRIC_SHORT = {
    'First Contentful Paint': 'FCP',
    'Time to Interactive': 'TTI',
    'First Input Delay': 'FID',
    'Total Blocking Time': 'TBT',
    'Largest Contentful Paint': 'LCP',
    'Cumulative Layout Shift': 'CLS',
}

PROFILE_ALIASES = {
    'desktop3g': 'desktop-slow3g',
    'mobile3g': 'mobile-slow3g',
}

PROFILE_PREFIXES = (
    'desktop-slow3g',
    'mobile-slow3g',
    'desktop3g',
    'mobile3g',
    'desktop',
    'mobile',
)

METRICS_FILE_RE = re.compile(r'^flow-.+_metrics\.json$')

# First run(s) are treated as cache warmup and excluded from analysis.
WARMUP_RUNS = 1


@dataclass(frozen=True)
class MetricsReport:
    strategy: str
    condition: str
    path: pathlib.Path
    base_url: str
    finished_at: str
    runs: list[dict]

    @property
    def label(self) -> str:
        return f'{self.strategy} / {self.condition}'


def parse_profile_from_filename(filename: str) -> str | None:
    stem = filename.removesuffix('_metrics.json')
    if not stem.startswith('flow-'):
        return None

    remainder = stem.removeprefix('flow-')
    for prefix in PROFILE_PREFIXES:
        if remainder == prefix or remainder.startswith(f'{prefix}-'):
            return PROFILE_ALIASES.get(prefix, prefix)

    return None


def discover_reports(reports_dir: pathlib.Path = REPORTS_DIR) -> list[MetricsReport]:
    reports: list[MetricsReport] = []

    for strategy_dir in sorted(reports_dir.iterdir()):
        if not strategy_dir.is_dir():
            continue

        strategy = strategy_dir.name
        for json_path in sorted(strategy_dir.glob('flow-*_metrics.json')):
            condition = parse_profile_from_filename(json_path.name)
            if condition is None:
                continue

            with json_path.open(encoding='utf-8') as handle:
                payload = json.load(handle)

            reports.append(
                MetricsReport(
                    strategy=strategy,
                    condition=condition,
                    path=json_path,
                    base_url=payload.get('baseUrl', ''),
                    finished_at=payload.get('finishedAt', ''),
                    runs=payload.get('runs', []),
                )
            )

    return reports


def get_analysis_runs(report: MetricsReport) -> list[dict]:
    runs = sorted(report.runs, key=lambda item: item.get('run', 0))
    return runs[WARMUP_RUNS:]


def extract_metric_series(report: MetricsReport, metric_full_name: str) -> list[float]:
    values: list[float] = []
    for run in get_analysis_runs(report):
        for step_metrics in run.get('metrics', []):
            value = step_metrics.get(metric_full_name)
            if value is not None:
                values.append(float(value))
    return values


def extract_all_metric_series(report: MetricsReport) -> dict[str, list[float]]:
    return {
        short: extract_metric_series(report, full_name)
        for full_name, short in METRIC_SHORT.items()
    }


def group_reports_by_condition(
    reports: list[MetricsReport],
) -> dict[str, list[MetricsReport]]:
    grouped: dict[str, list[MetricsReport]] = {}
    for report in reports:
        grouped.setdefault(report.condition, []).append(report)
    for condition in grouped:
        grouped[condition].sort(key=lambda item: item.strategy)
    return grouped

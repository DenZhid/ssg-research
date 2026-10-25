"""Единый CLI для анализа и визуализации PWA e2e метрик.

Объединяет логику report_utils, compare, plot_metrics и plot_bars.
Те же пути input/ и output/ используют compare.py, plot_metrics.py и plot_bars.py.

Исходные JSON: <корень проекта>/input/<strategy>/flow-*_metrics.json
Результаты: <корень проекта>/output/comparisons, output/charts, output/compare.log

Примеры:
  python analyze_reports.py compare --condition desktop
  python analyze_reports.py plot-metrics --condition mobile
  python analyze_reports.py plot-bars --stat median
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Shared constants & helpers (from report_utils.py)
# ---------------------------------------------------------------------------

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INPUT_DIR = PROJECT_ROOT / 'input'
OUTPUT_DIR = PROJECT_ROOT / 'output'

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

CONDITIONS = ('desktop', 'mobile', 'desktop-slow3g', 'mobile-slow3g')

CONDITION_TITLES = {
    'desktop': 'Desktop',
    'mobile': 'Mobile',
    'desktop-slow3g': 'Desktop-slow3g',
    'mobile-slow3g': 'Mobile-slow3g',
}

COMPARISONS_DIR = OUTPUT_DIR / 'comparisons'
COMPARE_LOG_FILE = OUTPUT_DIR / 'compare.log'
CHARTS_DIR = OUTPUT_DIR / 'charts'
BARS_DIR = CHARTS_DIR / 'bars'

STAT_PARAMS = {
    'median': ('Median', lambda values: float(np.median(values))),
    'p95': ('P95', lambda values: float(np.percentile(values, 95))),
    'p99': ('P99', lambda values: float(np.percentile(values, 99))),
}


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


def discover_reports(reports_dir: pathlib.Path = INPUT_DIR) -> list[MetricsReport]:
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


# ---------------------------------------------------------------------------
# Statistical comparison (from compare.py)
# ---------------------------------------------------------------------------

def setup_compare_logging(log_path: pathlib.Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('compare')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def descriptive_stats(values: list[float]) -> dict:
    series = np.asarray(values, dtype=float)
    return {
        'median': float(np.median(series)),
        'p95': float(np.percentile(series, 95)),
        'p99': float(np.percentile(series, 99)),
        'n': int(series.size),
    }


def mann_whitney_test(a: list[float], b: list[float]) -> dict | None:
    if len(set(a)) <= 1 and len(set(b)) <= 1 and np.median(a) == np.median(b):
        return None

    statistic, p_value = stats.mannwhitneyu(a, b, alternative='two-sided')
    effect_size = 1 - (2 * statistic) / (len(a) * len(b))
    return {
        'u_statistic': float(statistic),
        'p_value': float(p_value),
        'effect_size_r': float(effect_size),
    }


def bootstrap_median_diff_ci(a: list[float], b: list[float], n_resamples: int = 1000) -> dict:
    rng = np.random.default_rng(42)
    result = stats.bootstrap(
        (np.asarray(a, dtype=float), np.asarray(b, dtype=float)),
        statistic=lambda x, y, axis: np.median(x, axis=axis) - np.median(y, axis=axis),
        n_resamples=n_resamples,
        method='percentile',
        random_state=rng,
    )
    return {
        'low': float(result.confidence_interval.low),
        'high': float(result.confidence_interval.high),
    }


def compare_pair(
    strategy_a: str,
    strategy_b: str,
    metric_short: str,
    metric_full: str,
    report_a: MetricsReport,
    report_b: MetricsReport,
    logger: logging.Logger,
) -> dict:
    values_a = extract_metric_series(report_a, metric_full)
    values_b = extract_metric_series(report_b, metric_full)

    pair_label = f'{strategy_a} vs {strategy_b}'
    logger.info('Сравнение пары [%s], метрика %s', pair_label, metric_short)

    mw = mann_whitney_test(values_a, values_b)
    if mw is None:
        logger.info('  Mann-Whitney (%s): пропущен (распределения идентичны)', metric_short)
    else:
        logger.info(
            '  Mann-Whitney (%s): p=%.4f, effect size r=%.3f',
            metric_short,
            mw['p_value'],
            mw['effect_size_r'],
        )

    ci = bootstrap_median_diff_ci(values_a, values_b)
    logger.info(
        '  Bootstrap CI медианы (%s): [%.1f, %.1f]',
        metric_short,
        ci['low'],
        ci['high'],
    )

    return {
        'pair': [strategy_a, strategy_b],
        'metric': metric_short,
        'mann_whitney': mw,
        'bootstrap_median_diff_ci': ci,
    }


def analyze_condition(condition: str, reports: list[MetricsReport], logger: logging.Logger) -> dict:
    logger.info('=== Условие: %s ===', condition)
    logger.info('Исключено прогонов разогрева кэша: %d', WARMUP_RUNS)

    descriptive: dict[str, dict[str, dict]] = {}
    for report in reports:
        logger.info('Описательная статистика: %s (%s)', report.strategy, condition)
        descriptive[report.strategy] = {}

        for full_name, short_name in METRIC_SHORT.items():
            values = extract_metric_series(report, full_name)
            stats_payload = descriptive_stats(values)
            descriptive[report.strategy][short_name] = stats_payload
            logger.info(
                '  %s: median=%.1f P95=%.1f P99=%.1f n=%d',
                short_name,
                stats_payload['median'],
                stats_payload['p95'],
                stats_payload['p99'],
                stats_payload['n'],
            )

    pairwise: list[dict] = []
    if len(reports) >= 2:
        logger.info('Попарные сравнения стратегий в условии %s', condition)
        reports_by_strategy = {report.strategy: report for report in reports}

        for strategy_a, strategy_b in combinations(sorted(reports_by_strategy), 2):
            report_a = reports_by_strategy[strategy_a]
            report_b = reports_by_strategy[strategy_b]

            for full_name, short_name in METRIC_SHORT.items():
                pairwise.append(
                    compare_pair(
                        strategy_a,
                        strategy_b,
                        short_name,
                        full_name,
                        report_a,
                        report_b,
                        logger,
                    )
                )

    return {
        'condition': condition,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'warmup_runs_excluded': WARMUP_RUNS,
        'strategies': sorted(report.strategy for report in reports),
        'descriptive': descriptive,
        'pairwise': pairwise,
    }


def save_comparison(result: dict, output_dir: pathlib.Path) -> pathlib.Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'{result["condition"]}.json'
    with output_path.open('w', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    return output_path


def cmd_compare(args: argparse.Namespace) -> None:
    logger = setup_compare_logging(args.log_file)
    grouped = group_reports_by_condition(discover_reports())

    if args.condition not in grouped:
        available = ', '.join(sorted(grouped)) or 'нет данных'
        raise SystemExit(
            f'Для условия "{args.condition}" нет отчётов. Доступные условия: {available}',
        )

    result = analyze_condition(args.condition, grouped[args.condition], logger)
    output_path = save_comparison(result, args.output_dir)
    logger.info('Результаты сохранены: %s', output_path)


# ---------------------------------------------------------------------------
# Line charts per strategy/condition (from plot_metrics.py)
# ---------------------------------------------------------------------------

def plot_report(report: MetricsReport, output_dir: pathlib.Path) -> pathlib.Path:
    runs = get_analysis_runs(report)
    run_numbers = [run.get('run', index + 1) for index, run in enumerate(runs)]

    fig, ax = plt.subplots(figsize=(12, 6))

    for full_name, short_name in METRIC_SHORT.items():
        values = []
        for run in runs:
            run_values = [
                step.get(full_name)
                for step in run.get('metrics', [])
                if step.get(full_name) is not None
            ]
            values.append(sum(run_values) / len(run_values) if run_values else float('nan'))

        ax.plot(run_numbers, values, marker='o', markersize=3, linewidth=1.5, label=short_name)

    ax.set_title(f'{report.strategy} — {report.condition}')
    ax.set_xlabel('Прогон')
    ax.set_ylabel('Значение метрики')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', ncol=3)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'{report.strategy}__{report.condition}.png'
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def cmd_plot_metrics(args: argparse.Namespace) -> None:
    reports = discover_reports()
    if args.condition:
        reports = [report for report in reports if report.condition == args.condition]
    if args.strategy:
        reports = [report for report in reports if report.strategy == args.strategy]

    if not reports:
        raise SystemExit('Не найдено отчётов по заданным фильтрам.')

    for report in reports:
        output_path = plot_report(report, args.output_dir)
        print(f'Сохранён график: {output_path}')


# ---------------------------------------------------------------------------
# Grouped bar charts (from plot_bars.py)
# ---------------------------------------------------------------------------

def compute_stat(values: list[float], stat_key: str) -> float:
    _, calculator = STAT_PARAMS[stat_key]
    if not values:
        return float('nan')
    return calculator(values)


def build_chart_data(
    reports: list[MetricsReport],
    stat_key: str,
) -> tuple[list[str], list[str], list[list[float]]]:
    strategies = [report.strategy for report in reports]
    metrics = list(METRIC_SHORT.values())

    values_by_strategy: dict[str, dict[str, float]] = {}
    for report in reports:
        values_by_strategy[report.strategy] = {}
        for full_name, short_name in METRIC_SHORT.items():
            series = extract_metric_series(report, full_name)
            values_by_strategy[report.strategy][short_name] = compute_stat(series, stat_key)

    matrix = [
        [values_by_strategy[strategy][metric] for strategy in strategies]
        for metric in metrics
    ]
    return strategies, metrics, matrix


def plot_condition_stat(
    condition: str,
    reports: list[MetricsReport],
    stat_key: str,
    output_dir: pathlib.Path,
) -> pathlib.Path:
    strategies, metrics, matrix = build_chart_data(reports, stat_key)
    stat_title = STAT_PARAMS[stat_key][0]
    condition_title = CONDITION_TITLES.get(condition, condition)

    x = np.arange(len(metrics))
    bar_count = len(strategies)
    bar_width = 0.8 / bar_count

    fig, ax = plt.subplots(figsize=(12, 6))

    for index, strategy in enumerate(strategies):
        offsets = x - 0.4 + bar_width / 2 + index * bar_width
        values = [row[index] for row in matrix]
        ax.bar(offsets, values, width=bar_width, label=strategy)

    ax.set_title(f'{condition_title}-{stat_title}')
    ax.set_xlabel('Метрика')
    ax.set_ylabel(stat_title)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.grid(True, axis='y', alpha=0.3)
    ax.legend(loc='best', fontsize=9)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'{condition_title}-{stat_title}.png'
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def cmd_plot_bars(args: argparse.Namespace) -> None:
    grouped = group_reports_by_condition(discover_reports())
    if args.condition:
        grouped = {args.condition: grouped[args.condition]} if args.condition in grouped else {}

    if not grouped:
        raise SystemExit('Не найдено отчётов по заданным фильтрам.')

    stat_keys = [args.stat] if args.stat else list(STAT_PARAMS)

    for condition, reports in sorted(grouped.items()):
        for stat_key in stat_keys:
            output_path = plot_condition_stat(condition, reports, stat_key, args.output_dir)
            print(f'Сохранена диаграмма: {output_path}')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Анализ и визуализация PWA e2e метрик (compare / plot-metrics / plot-bars).',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    compare_parser = subparsers.add_parser(
        'compare',
        help='Сравнить стратегии кэширования в рамках условия эксперимента.',
    )
    compare_parser.add_argument(
        '--condition',
        required=True,
        choices=list(CONDITIONS),
        help='Условие эксперимента для сравнения стратегий.',
    )
    compare_parser.add_argument(
        '--output-dir',
        type=pathlib.Path,
        default=COMPARISONS_DIR,
        help=f'Каталог для JSON-результатов (по умолчанию: {COMPARISONS_DIR}).',
    )
    compare_parser.add_argument(
        '--log-file',
        type=pathlib.Path,
        default=COMPARE_LOG_FILE,
        help=f'Файл лога (по умолчанию: {COMPARE_LOG_FILE}).',
    )
    compare_parser.set_defaults(func=cmd_compare)

    metrics_parser = subparsers.add_parser(
        'plot-metrics',
        help='Построить линейные графики метрик по прогонам.',
    )
    metrics_parser.add_argument(
        '--condition',
        choices=list(CONDITIONS),
        help='Фильтр по условию эксперимента.',
    )
    metrics_parser.add_argument(
        '--strategy',
        help='Фильтр по стратегии кэширования (имя папки, например cache-first).',
    )
    metrics_parser.add_argument(
        '--output-dir',
        type=pathlib.Path,
        default=CHARTS_DIR,
        help=f'Каталог для PNG-графиков (по умолчанию: {CHARTS_DIR}).',
    )
    metrics_parser.set_defaults(func=cmd_plot_metrics)

    bars_parser = subparsers.add_parser(
        'plot-bars',
        help='Построить столбчатые диаграммы стратегий по условиям.',
    )
    bars_parser.add_argument(
        '--condition',
        choices=list(CONDITIONS),
        help='Фильтр по условию эксперимента.',
    )
    bars_parser.add_argument(
        '--stat',
        choices=list(STAT_PARAMS),
        help='Статистический параметр (median, p95, p99). По умолчанию — все.',
    )
    bars_parser.add_argument(
        '--output-dir',
        type=pathlib.Path,
        default=BARS_DIR,
        help=f'Каталог для PNG-диаграмм (по умолчанию: {BARS_DIR}).',
    )
    bars_parser.set_defaults(func=cmd_plot_bars)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()

"""Generate grouped bar charts comparing caching strategies per condition."""

from __future__ import annotations

import argparse
import pathlib

import matplotlib.pyplot as plt
import numpy as np

from report_utils import METRIC_SHORT, OUTPUT_DIR, discover_reports, extract_metric_series, group_reports_by_condition

BARS_DIR = OUTPUT_DIR / 'charts' / 'bars'

CONDITION_TITLES = {
    'desktop': 'Desktop',
    'mobile': 'Mobile',
    'desktop-slow3g': 'Desktop-slow3g',
    'mobile-slow3g': 'Mobile-slow3g',
}

STAT_PARAMS = {
    'median': ('Median', lambda values: float(np.median(values))),
    'p95': ('P95', lambda values: float(np.percentile(values, 95))),
    'p99': ('P99', lambda values: float(np.percentile(values, 99))),
}


def compute_stat(values: list[float], stat_key: str) -> float:
    _, calculator = STAT_PARAMS[stat_key]
    if not values:
        return float('nan')
    return calculator(values)


def build_chart_data(reports: list, stat_key: str) -> tuple[list[str], list[str], list[list[float]]]:
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
    reports: list,
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Построить столбчатые диаграммы стратегий по условиям эксперимента.',
    )
    parser.add_argument(
        '--condition',
        choices=list(CONDITION_TITLES),
        help='Фильтр по условию эксперимента.',
    )
    parser.add_argument(
        '--stat',
        choices=list(STAT_PARAMS),
        help='Статистический параметр (median, p95, p99). По умолчанию — все.',
    )
    parser.add_argument(
        '--output-dir',
        type=pathlib.Path,
        default=BARS_DIR,
        help=f'Каталог для PNG-диаграмм (по умолчанию: {BARS_DIR}).',
    )
    args = parser.parse_args()

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


if __name__ == '__main__':
    main()

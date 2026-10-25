"""Единый CLI для анализа и визуализации PWA e2e метрик.

Расчёт живёт в report_utils, compare, plot_metrics и plot_bars.
Этот модуль только разбирает аргументы и вызывает их.

Примеры:
  python analyze_reports.py compare --condition desktop
  python analyze_reports.py plot-metrics --condition mobile
  python analyze_reports.py plot-bars --stat median
"""

from __future__ import annotations

import argparse
import pathlib

from compare import (
    COMPARISONS_DIR,
    LOG_FILE,
    analyze_condition,
    save_comparison,
    setup_logging,
)
from plot_bars import BARS_DIR, CONDITION_TITLES, STAT_PARAMS, plot_condition_stat
from plot_metrics import CHARTS_DIR, plot_report
from report_utils import discover_reports, group_reports_by_condition

CONDITIONS = tuple(CONDITION_TITLES)


def cmd_compare(args: argparse.Namespace) -> None:
    logger = setup_logging(args.log_file)
    grouped = group_reports_by_condition(discover_reports())

    if args.condition not in grouped:
        available = ', '.join(sorted(grouped)) or 'нет данных'
        raise SystemExit(
            f'Для условия "{args.condition}" нет отчётов. Доступные условия: {available}',
        )

    result = analyze_condition(args.condition, grouped[args.condition], logger)
    output_path = save_comparison(result, args.output_dir)
    logger.info('Результаты сохранены: %s', output_path)


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
        default=LOG_FILE,
        help=f'Файл лога (по умолчанию: {LOG_FILE}).',
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

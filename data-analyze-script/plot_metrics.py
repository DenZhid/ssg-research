"""Generate line charts for each strategy/condition metrics report."""

from __future__ import annotations

import argparse
import pathlib

import matplotlib.pyplot as plt

from report_utils import METRIC_SHORT, OUTPUT_DIR, discover_reports, get_analysis_runs

CHARTS_DIR = OUTPUT_DIR / 'charts'


def plot_report(report, output_dir: pathlib.Path) -> pathlib.Path:
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


def main() -> None:
    parser = argparse.ArgumentParser(description='Построить графики метрик PWA e2e.')
    parser.add_argument(
        '--condition',
        help='Фильтр по условию эксперимента (desktop, mobile, desktop-slow3g, mobile-slow3g).',
    )
    parser.add_argument(
        '--strategy',
        help='Фильтр по стратегии кэширования (имя папки, например cache-first).',
    )
    parser.add_argument(
        '--output-dir',
        type=pathlib.Path,
        default=CHARTS_DIR,
        help=f'Каталог для PNG-графиков (по умолчанию: {CHARTS_DIR}).',
    )
    args = parser.parse_args()

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


if __name__ == '__main__':
    main()

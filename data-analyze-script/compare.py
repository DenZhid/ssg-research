"""Statistical comparison of caching strategies within experiment conditions."""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
from datetime import datetime, timezone
from itertools import combinations

import numpy as np
from scipy import stats

from report_utils import METRIC_SHORT, OUTPUT_DIR, WARMUP_RUNS, discover_reports, extract_metric_series, group_reports_by_condition

COMPARISONS_DIR = OUTPUT_DIR / 'comparisons'
LOG_FILE = OUTPUT_DIR / 'compare.log'


def setup_logging(log_path: pathlib.Path) -> logging.Logger:
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
    report_a,
    report_b,
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


def analyze_condition(condition: str, reports: list, logger: logging.Logger) -> dict:
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Сравнить стратегии кэширования в рамках условия эксперимента.',
    )
    parser.add_argument(
        '--condition',
        required=True,
        choices=['desktop', 'mobile', 'desktop-slow3g', 'mobile-slow3g'],
        help='Условие эксперимента для сравнения стратегий.',
    )
    parser.add_argument(
        '--output-dir',
        type=pathlib.Path,
        default=COMPARISONS_DIR,
        help=f'Каталог для JSON-результатов (по умолчанию: {COMPARISONS_DIR}).',
    )
    parser.add_argument(
        '--log-file',
        type=pathlib.Path,
        default=LOG_FILE,
        help=f'Файл лога (по умолчанию: {LOG_FILE}).',
    )
    args = parser.parse_args()

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


if __name__ == '__main__':
    main()

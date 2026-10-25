# Методика

## Источник данных

Прогоны Playwright / LHCI-подобных flow-тестов сохраняются как `flow-<profile>-*_metrics.json` в `input/<стратегия>/`. Имя файла задаёт условие эксперимента, имя папки — стратегию кэширования.

| Префикс в имени файла | Условие |
|-----------------------|---------|
| `desktop` | `desktop` |
| `mobile` | `mobile` |
| `desktop3g` / `desktop-slow3g` | `desktop-slow3g` |
| `mobile3g` / `mobile-slow3g` | `mobile-slow3g` |

## Warmup

Первый прогон (`WARMUP_RUNS = 1`) считается разогревом кэша и **исключается** из анализа. В отчётах это отражено полем `warmup_runs_excluded`.

## Метрики Web Vitals

| Сокращение | Метрика |
|------------|---------|
| FCP | First Contentful Paint |
| TTI | Time to Interactive |
| FID | First Input Delay |
| TBT | Total Blocking Time |
| LCP | Largest Contentful Paint |
| CLS | Cumulative Layout Shift |

Все временные метрики — в миллисекундах; CLS — безразмерный.

## Описательная статистика

По каждой стратегии и метрике (без warmup) считаются:

- **median** — медиана
- **p95** / **p99** — 95-й и 99-й перцентили
- **n** — число наблюдений

## Попарные сравнения

Внутри одного условия стратегии сравниваются попарно:

1. **Mann–Whitney U** (двусторонний) — `u_statistic`, `p_value`, effect size `r`
2. **Bootstrap CI** разности медиан (percentile, 1000 ресемплов) — интервал `[low, high]`

На страницах условий показываются пары с `p_value < 0.05`. Полные результаты — в JSON:

`assets/comparisons/<condition>.json`

## Визуализации

| Тип | Путь | Содержание |
|-----|------|------------|
| Сводные бары | `assets/charts/bars/<Condition>-<Stat>.png` | Стратегии × метрики (median / P95 / P99) |
| Линейные графики | `assets/charts/<strategy>__<condition>.png` | Динамика метрик по прогонам |

## Пайплайн

Сборка сайта — `nox -s site`. Она читает `input/`, пересчитывает только те сравнения и графики, у которых изменился SHA-256 исходных JSON, и в том же запуске делает второй проход. Второй проход попадает в кэш и показывает выигрыш по времени относительно холодного пересчёта.

```text
nox -s site
    │
    ▼
pipeline.py
    input/**/*.json → кэш по SHA-256 → output/charts/ + output/comparisons/
    output/cache-report.json + output/build-info.json
    │
    ▼
sync_docs_assets.py → docs/assets/
    │
    ▼
generate_docs.py → conditions/*.md
    │
    ▼
mkdocs build
    хук дописывает хеш коммита, дату сборки, версию набора данных и сводку кэша
```

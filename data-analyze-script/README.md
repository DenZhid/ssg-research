# Анализ отчётов PWA e2e

Скрипты в этой папке читают JSON-метрики прогонов Playwright/LHCI-подобных flow-тестов и строят статистику и графики по стратегиям кэширования.

Исходные модули (`report_utils.py`, `compare.py`, `plot_metrics.py`, `plot_bars.py`) сохранены. Единая точка входа — `analyze_reports.py`.

## Зависимости

```bash
pip install -r requirements.txt
```

Нужны: `matplotlib`, `numpy`, `scipy`.

## Структура входных данных

Отчёты лежат в `input/` в корне проекта. Результаты анализа — в `output/`:

```text
input/
├── cache-first/
│   └── flow-desktop-cache_first_metrics.json
├── cache-only/
├── network-first/
├── network-only/
└── stale-while-revalidate/

output/
├── comparisons/          # JSON результатов сравнения
├── charts/               # PNG-графики
│   └── bars/
└── compare.log
```

Имя файла `flow-<profile>-*_metrics.json` определяет **условие** эксперимента:

| Префикс в имени файла | Нормализованное условие |
|-----------------------|-------------------------|
| `desktop`             | `desktop`               |
| `mobile`              | `mobile`                |
| `desktop3g` / `desktop-slow3g` | `desktop-slow3g` |
| `mobile3g` / `mobile-slow3g`   | `mobile-slow3g`  |

Имя **папки** — стратегия кэширования (`cache-first`, `network-only` и т.д.).

Внутри JSON: `baseUrl`, `finishedAt`, массив `runs` с шагами и метриками Web Vitals:

- FCP, TTI, FID, TBT, LCP, CLS

Первый прогон (`WARMUP_RUNS = 1`) считается разогревом кэша и **исключается** из анализа.

## Общий флоу

```text
JSON-отчёты (strategy/flow-*_metrics.json)
        │
        ▼
  discover_reports()     — обход папок, парсинг профиля из имени файла
        │
        ├─ get_analysis_runs() / extract_metric_series()
        │         (без warmup-прогона)
        │
        ├──► compare        → descriptive + Mann–Whitney + bootstrap CI
        │                   → output/comparisons/<condition>.json
        │
        ├──► plot-metrics   → линейные графики метрик по прогонам
        │                   → output/charts/<strategy>__<condition>.png
        │
        └──► plot-bars      → столбчатые диаграммы стратегий
                            → output/charts/bars/<Condition>-<Stat>.png
```

1. **Загрузка** — `discover_reports()` находит все `flow-*_metrics.json`, нормализует условие и собирает `MetricsReport`.
2. **Подготовка рядов** — из каждого отчёта берутся значения метрик по шагам, без warmup.
3. **Сравнение** — внутри одного условия стратегии сравниваются попарно (Mann–Whitney U, bootstrap CI разности медиан) и считается описательная статистика (median / P95 / P99).
4. **Визуализация** — либо динамика метрик по прогонам (`plot-metrics`), либо сводные бары стратегий по метрикам (`plot-bars`).

Типичный порядок работы после прогона e2e:

1. Убедиться, что в папках стратегий есть свежие `*_metrics.json`.
2. Посмотреть динамику: `plot-metrics`.
3. Сравнить стратегии в нужном условии: `compare`.
4. Построить сводные бары: `plot-bars`.

## Единый CLI: `analyze_reports.py`

Пути `input/` и `output/` считаются от корня проекта, поэтому команды можно запускать из любого каталога.

### Сравнение стратегий

```bash
python data-analyze-script/analyze_reports.py compare --condition desktop
python data-analyze-script/analyze_reports.py compare --condition mobile-slow3g
```

Результат: `output/comparisons/<condition>.json` и лог `output/compare.log`.

### Линейные графики метрик

```bash
python data-analyze-script/analyze_reports.py plot-metrics
python data-analyze-script/analyze_reports.py plot-metrics --condition mobile --strategy cache-first
```

Результат: `output/charts/<strategy>__<condition>.png`.

### Столбчатые диаграммы

```bash
python data-analyze-script/analyze_reports.py plot-bars
python data-analyze-script/analyze_reports.py plot-bars --condition desktop --stat median
```

Без `--stat` строятся все три параметра: median, p95, p99.  
Результат: `output/charts/bars/<Condition>-<Stat>.png`.

## Исходные скрипты (эквивалентны subcommands)

| Файл | Эквивалент в `analyze_reports.py` |
|------|-----------------------------------|
| `report_utils.py` | общие хелперы (встроено) |
| `compare.py` | `compare` |
| `plot_metrics.py` | `plot-metrics` |
| `plot_bars.py` | `plot-bars` |

Старые скрипты по-прежнему можно вызывать напрямую, например:

```bash
python compare.py --condition desktop
python plot_metrics.py --condition mobile
python plot_bars.py --stat p95
```

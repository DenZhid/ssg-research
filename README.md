# Анализ стратегий кэширования PWA

JSON-метрики прогонов Playwright / LHCI-подобных flow-тестов сравниваются по стратегиям Service Worker и публикуются сайтом MkDocs.

Исходные данные — `input/`. Расчёт — модули в `data-analyze-script/`. Сборка сайта — `nox -s site`.

## Зависимости

Python 3.13+. Пакеты перечислены в `pyproject.toml`: `matplotlib`, `numpy`, `scipy`, `mkdocs`.

```bash
poetry install
```

Сборка сайта ставит то же самое внутрь сессии nox и дополнительно требует пакет `nox`.

## Входные данные

```text
input/
├── cache-first/
│   └── flow-desktop-cache_first_metrics.json
├── cache-only/
├── network-first/
├── network-only/
└── stale-while-revalidate/
```

Имя папки — стратегия. Префикс в `flow-<profile>-*_metrics.json` — условие эксперимента:

| Префикс в имени файла | Условие |
|-----------------------|---------|
| `desktop` | `desktop` |
| `mobile` | `mobile` |
| `desktop3g` / `desktop-slow3g` | `desktop-slow3g` |
| `mobile3g` / `mobile-slow3g` | `mobile-slow3g` |

В JSON: `baseUrl`, `finishedAt` и массив `runs` с шагами и метриками FCP, TTI, FID, TBT, LCP, CLS. Первый прогон (`WARMUP_RUNS = 1`) — разогрев кэша, из анализа он исключается.

## Расчёт

Логика разложена по модулям. `analyze_reports.py` только вызывает их из командной строки.

| Модуль | Что делает |
|--------|------------|
| `report_utils.py` | Поиск JSON, разбор условия, ряды метрик без warmup |
| `compare.py` | Median / P95 / P99, Mann–Whitney U, bootstrap CI |
| `plot_metrics.py` | Линейные графики по прогонам |
| `plot_bars.py` | Столбчатые диаграммы стратегий |
| `analyze_reports.py` | Подкоманды `compare`, `plot-metrics`, `plot-bars` |

```bash
python data-analyze-script/analyze_reports.py compare --condition desktop
python data-analyze-script/analyze_reports.py plot-metrics --condition mobile --strategy cache-first
python data-analyze-script/analyze_reports.py plot-bars --condition desktop --stat median
```

Без `--stat` строятся median, p95 и p99. Те же команды есть у `compare.py`, `plot_metrics.py` и `plot_bars.py`.

Результаты пишутся в `output/` (каталог в `.gitignore`):

```text
output/
├── comparisons/<condition>.json
├── charts/<strategy>__<condition>.png
├── charts/bars/<Condition>-<Stat>.png
├── compare.log
├── .cache/manifest.json    # хеши входов и холодное время
├── cache-report.json
└── build-info.json         # коммит, дата сборки, версия input/
```

## Сборка сайта

```bash
nox -s site
```

Сессия вызывает `pipeline.py`, затем `sync_docs_assets.py`, `generate_docs.py` и `mkdocs build`.

`pipeline.py` считает SHA-256 исходных JSON. Совпавший хеш не пересчитывается. В одном запуске два прохода: второй попадает в кэш и печатает выигрыш по времени относительно холодного пересчёта. Правка одного файла пересчитывает только сравнение этого условия, его линейный график и бар-графики.

`sync_docs_assets.py` копирует графики и JSON в `docs-site/docs/assets/`. `generate_docs.py` собирает `docs-site/docs/conditions/*.md`. Хук `docs-site/hooks.py` дописывает на каждую страницу хеш коммита, дату сборки UTC, версию набора данных и сводку кэша.

Публикация — `.github/workflows/pages.yml`: push в `master` запускает `nox -s site` и выкладывает сайт на GitHub Pages и Helios.

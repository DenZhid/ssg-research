# Агентам по этому репозиторию

Сайт сравнивает стратегии кэширования Service Worker по Web Vitals. Источник правды — JSON в `input/`. Страницы условий и картинки из них генерируются, руками их не правят.

## Куда класть код

- Загрузка отчётов и ряды метрик — `data-analyze-script/report_utils.py`.
- Статистика — `data-analyze-script/compare.py`.
- Линейные графики — `data-analyze-script/plot_metrics.py`.
- Бар-графики — `data-analyze-script/plot_bars.py`.
- `analyze_reports.py` — только CLI. Новую логику туда не копировать, а импортировать из модуля выше.
- Кэш сборки и метка версии — `pipeline.py`. Ключ кэша — SHA-256 байтов входных JSON, не дата сборки и не хеш коммита.
- Текст страниц условий — `generate_docs.py`. Копирование PNG и JSON — `sync_docs_assets.py`.
- Метка на всех страницах — `docs-site/hooks.py`, данные из `output/build-info.json` и `output/cache-report.json`.

Каталог `data-analyze-script` не пакет: скрипты импортируют соседние модули, потому что каталог скрипта оказывается в `sys.path`. `pipeline.py` добавляет этот каталог в путь сам.

## Сборка

Обычная проверка после изменений расчёта или страниц:

```bash
nox -s site
```

Локально, если зависимости уже стоят через Poetry: `poetry run python pipeline.py`, затем `sync_docs_assets.py`, `generate_docs.py` и `mkdocs build -f docs-site/mkdocs.yml`.

Перед импортом `matplotlib` нужен `MPLBACKEND=Agg`. В `pipeline.py` это уже выставлено.

`output/` и `docs-site/site/` в `.gitignore`. Не коммитить их и не коммитить секреты Helios. В workflow ключ `jobs` стоит в корне файла, без отступа.

## Данные и страницы

Условие эксперимента читается из имени `flow-<profile>-*_metrics.json`, стратегия — из имени папки. Первый прогон исключается (`WARMUP_RUNS = 1`).

Тексты сайта на русском. На странице должны оставаться три поля метки: хеш коммита, дата сборки, версия набора данных — плюс сводка кэша со временем холодного прогона и выигрышем.

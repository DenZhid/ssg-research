# PWA Cache Strategies Performance

Сравнение стратегий кэширования Service Worker в PWA по метрикам Web Vitals.

Эксперимент измеряет, как выбор стратегии влияет на скорость отрисовки и интерактивность при разных профилях устройства и сети.

## Стратегии

| Стратегия | Кратко |
|-----------|--------|
| `cache-first` | Сначала кэш, при промахе — сеть |
| `cache-only` | Только кэш |
| `network-first` | Сначала сеть, при сбое — кэш |
| `network-only` | Только сеть |
| `stale-while-revalidate` | Ответ из кэша + фоновое обновление |

## Условия эксперимента

| Условие | Описание | Страница |
|---------|----------|----------|
| Desktop | Десктоп, обычная сеть | [Desktop](conditions/desktop.md) |
| Mobile | Мобильный профиль, обычная сеть | [Mobile](conditions/mobile.md) |
| Desktop slow 3G | Десктоп + Slow 3G | [Desktop slow 3G](conditions/desktop-slow3g.md) |
| Mobile slow 3G | Мобильный профиль + Slow 3G | [Mobile slow 3G](conditions/mobile-slow3g.md) |

## Метрики

FCP, TTI, FID, TBT, LCP, CLS — см. [Методику](methodology.md).

На страницах условий: сводные бар-графики, описательная статистика (median / P95 / P99), линейные графики по стратегиям и значимые попарные сравнения.

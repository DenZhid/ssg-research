"""Generate MkDocs condition pages from output/comparisons JSON."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
DOCS = ROOT / "docs-site" / "docs"
COMPARISONS_DIR = OUTPUT_DIR / "comparisons"
CONDITIONS_DIR = DOCS / "conditions"

CONDITION_TITLES = {
    "desktop": "Desktop",
    "mobile": "Mobile",
    "desktop-slow3g": "Desktop-slow3g",
    "mobile-slow3g": "Mobile-slow3g",
}

CONDITION_HEADINGS = {
    "desktop": "Desktop",
    "mobile": "Mobile",
    "desktop-slow3g": "Desktop slow 3G",
    "mobile-slow3g": "Mobile slow 3G",
}

STAT_CHARTS = ("Median", "P95", "P99")
METRICS = ("FCP", "TTI", "FID", "TBT", "LCP", "CLS")
P_THRESHOLD = 0.05


def fmt_num(value: float | int | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return str(int(value))
    return f"{value:.3g}"


def fmt_p(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 1e-4:
        return f"{value:.2e}"
    return f"{value:.4f}"


def sample_size(data: dict) -> int | None:
    descriptive = data.get("descriptive") or {}
    for strategy_stats in descriptive.values():
        for metric_stats in strategy_stats.values():
            n = metric_stats.get("n")
            if n is not None:
                return int(n)
    return None


def render_descriptive_table(data: dict) -> str:
    strategies = data.get("strategies") or list((data.get("descriptive") or {}).keys())
    descriptive = data.get("descriptive") or {}

    lines = [
        "| Стратегия | Метрика | Median | P95 | P99 | n |",
        "|-----------|---------|--------|-----|-----|---|",
    ]
    for strategy in strategies:
        metrics = descriptive.get(strategy) or {}
        for metric in METRICS:
            stats = metrics.get(metric) or {}
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{strategy}`" if metric == METRICS[0] else "",
                        metric,
                        fmt_num(stats.get("median")),
                        fmt_num(stats.get("p95")),
                        fmt_num(stats.get("p99")),
                        fmt_num(stats.get("n")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines)


def render_significant_pairs(data: dict) -> str:
    rows: list[str] = []
    for item in data.get("pairwise") or []:
        mw = item.get("mann_whitney")
        if not mw:
            continue
        p_value = mw.get("p_value")
        if p_value is None or p_value >= P_THRESHOLD:
            continue
        pair = item.get("pair") or ["?", "?"]
        ci = item.get("bootstrap_median_diff_ci") or {}
        rows.append(
            "| "
            + " | ".join(
                [
                    f"`{pair[0]}`",
                    f"`{pair[1]}`",
                    item.get("metric", "—"),
                    fmt_p(p_value),
                    fmt_num(mw.get("effect_size_r")),
                    f"[{fmt_num(ci.get('low'))}, {fmt_num(ci.get('high'))}]",
                ]
            )
            + " |"
        )

    if not rows:
        return "_Значимых различий (p < 0.05) не найдено._"

    header = [
        "| Стратегия A | Стратегия B | Метрика | p-value | Effect size r | Bootstrap CI (median A − B) |",
        "|-------------|-------------|---------|---------|---------------|-----------------------------|",
    ]
    return "\n".join(header + rows)


def render_bar_charts(condition: str) -> str:
    title = CONDITION_TITLES[condition]
    lines = ["## Сводные бар-графики", ""]
    for stat in STAT_CHARTS:
        rel = f"../assets/charts/bars/{title}-{stat}.png"
        lines.append(f"### {stat}")
        lines.append("")
        lines.append(f"![{title} {stat}]({rel})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_line_charts(condition: str, strategies: list[str]) -> str:
    lines = ["## Линейные графики по стратегиям", ""]
    for strategy in strategies:
        rel = f"../assets/charts/{strategy}__{condition}.png"
        lines.append(f"### `{strategy}`")
        lines.append("")
        lines.append(f"![{strategy} {condition}]({rel})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_condition_page(condition: str, data: dict) -> str:
    heading = CONDITION_HEADINGS[condition]
    strategies = data.get("strategies") or list((data.get("descriptive") or {}).keys())
    n = sample_size(data)
    generated_at = data.get("generated_at", "—")
    warmup = data.get("warmup_runs_excluded", "—")

    parts = [
        f"# {heading}",
        "",
        "| | |",
        "|---|---|",
        f"| Условие | `{condition}` |",
        f"| Сгенерировано | `{generated_at}` |",
        f"| Warmup прогонов исключено | {warmup} |",
        f"| n (наблюдений) | {n if n is not None else '—'} |",
        "",
        render_bar_charts(condition),
        "## Описательная статистика",
        "",
        render_descriptive_table(data),
        "",
        render_line_charts(condition, strategies),
        "## Значимые попарные сравнения",
        "",
        f"Пары с Mann–Whitney `p_value` < {P_THRESHOLD}.",
        "",
        render_significant_pairs(data),
        "",
        f"Полные данные: [`comparisons/{condition}.json`](../assets/comparisons/{condition}.json).",
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    CONDITIONS_DIR.mkdir(parents=True, exist_ok=True)

    if not COMPARISONS_DIR.is_dir():
        raise SystemExit(f"Comparisons folder not found: {COMPARISONS_DIR}")

    written = 0
    for condition in CONDITION_TITLES:
        src = COMPARISONS_DIR / f"{condition}.json"
        if not src.is_file():
            print(f"Skip (missing): {src.relative_to(ROOT)}")
            continue

        data = json.loads(src.read_text(encoding="utf-8"))
        page = render_condition_page(condition, data)
        dst = CONDITIONS_DIR / f"{condition}.md"
        dst.write_text(page, encoding="utf-8")
        print(f"Wrote {dst.relative_to(ROOT)}")
        written += 1

    if written == 0:
        raise SystemExit("No condition pages generated")


if __name__ == "__main__":
    main()

"""Cached analysis of input JSON and a build stamp for the docs site.

Two passes share output/.cache/manifest.json. A hit skips work whose source
files are unchanged and records the time saved against the last cold run.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ["MPLBACKEND"] = "Agg"

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "data-analyze-script"))

from analyze_reports import (  # noqa: E402
    BARS_DIR,
    CHARTS_DIR,
    COMPARISONS_DIR,
    COMPARE_LOG_FILE,
    CONDITION_TITLES,
    CONDITIONS,
    STAT_PARAMS,
    analyze_condition,
    discover_reports,
    group_reports_by_condition,
    plot_condition_stat,
    plot_report,
    save_comparison,
    setup_compare_logging,
)

OUTPUT_DIR = ROOT / "output"
INPUT_DIR = ROOT / "input"
CACHE_DIR = OUTPUT_DIR / ".cache"
MANIFEST_PATH = CACHE_DIR / "manifest.json"
REPORT_PATH = OUTPUT_DIR / "cache-report.json"
BUILD_INFO_PATH = OUTPUT_DIR / "build-info.json"


def fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(INPUT_DIR).as_posix()):
        digest.update(path.relative_to(INPUT_DIR).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def dataset_version() -> str:
    return fingerprint(list(INPUT_DIR.rglob("*.json")))


def git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    commit = result.stdout.strip()
    return commit or "unknown"


def load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        return {}
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_manifest(manifest: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def cached_compute(
    manifest: dict,
    artifact_key: str,
    input_paths: list[Path],
    compute,
) -> dict:
    started = time.perf_counter()
    digest = fingerprint(input_paths)
    entry = manifest.get(artifact_key)
    output_path = OUTPUT_DIR / artifact_key
    if (
        isinstance(entry, dict)
        and entry.get("input_hash") == digest
        and output_path.is_file()
    ):
        elapsed = time.perf_counter() - started
        cold = float(entry["cold_elapsed_s"])
        item = {
            "artifact": artifact_key,
            "status": "hit",
            "elapsed_s": elapsed,
            "cold_elapsed_s": cold,
            "saved_s": max(cold - elapsed, 0.0),
        }
        print(
            f"hit  {artifact_key}  {elapsed:.3f}s"
            f" (cold {cold:.3f}s, saved {item['saved_s']:.3f}s)"
        )
        return item

    compute_started = time.perf_counter()
    compute()
    elapsed = time.perf_counter() - compute_started
    manifest[artifact_key] = {"input_hash": digest, "cold_elapsed_s": elapsed}
    save_manifest(manifest)
    item = {
        "artifact": artifact_key,
        "status": "miss",
        "elapsed_s": elapsed,
        "cold_elapsed_s": elapsed,
        "saved_s": 0.0,
    }
    print(f"miss {artifact_key}  {elapsed:.3f}s")
    return item


def summarize(name: str, items: list[dict]) -> dict:
    hits = sum(1 for item in items if item["status"] == "hit")
    misses = sum(1 for item in items if item["status"] == "miss")
    elapsed = sum(item["elapsed_s"] for item in items)
    cold = sum(item["cold_elapsed_s"] for item in items)
    saved = sum(item["saved_s"] for item in items)
    summary = {
        "name": name,
        "hits": hits,
        "misses": misses,
        "elapsed_s": elapsed,
        "cold_elapsed_s": cold,
        "saved_s": saved,
        "items": items,
    }
    print(
        f"Проход {name}: hit={hits} miss={misses} "
        f"время={elapsed:.3f} с, холодный пересчёт={cold:.3f} с, "
        f"выигрыш={saved:.3f} с"
    )
    return summary


def run_pass(name: str) -> dict:
    manifest = load_manifest()
    grouped = group_reports_by_condition(discover_reports())
    logger_holder: dict[str, object] = {}
    items: list[dict] = []

    def logger():
        if "logger" not in logger_holder:
            logger_holder["logger"] = setup_compare_logging(COMPARE_LOG_FILE)
        return logger_holder["logger"]

    for condition in CONDITIONS:
        reports = grouped.get(condition, [])
        if not reports:
            continue
        source_paths = [report.path for report in reports]

        def compute_comparison(condition=condition, reports=reports):
            result = analyze_condition(condition, reports, logger())
            save_comparison(result, COMPARISONS_DIR)

        items.append(
            cached_compute(
                manifest,
                f"comparisons/{condition}.json",
                source_paths,
                compute_comparison,
            )
        )

        for report in reports:

            def compute_line(report=report):
                plot_report(report, CHARTS_DIR)

            items.append(
                cached_compute(
                    manifest,
                    f"charts/{report.strategy}__{report.condition}.png",
                    [report.path],
                    compute_line,
                )
            )

        condition_title = CONDITION_TITLES.get(condition, condition)
        for stat_key, (stat_title, _calculator) in STAT_PARAMS.items():

            def compute_bars(condition=condition, reports=reports, stat_key=stat_key):
                plot_condition_stat(condition, reports, stat_key, BARS_DIR)

            items.append(
                cached_compute(
                    manifest,
                    f"charts/bars/{condition_title}-{stat_title}.png",
                    source_paths,
                    compute_bars,
                )
            )

    return summarize(name, items)


def write_build_info(built_at: str) -> None:
    payload = {
        "commit": git_commit(),
        "built_at": built_at,
        "dataset_version": dataset_version(),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_INFO_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Метка сборки: commit={payload['commit']} "
        f"built_at={payload['built_at']} "
        f"dataset={payload['dataset_version']}"
    )


def write_cache_report(passes: list[dict]) -> None:
    warm = passes[-1]
    payload = {
        "passes": [
            {key: value for key, value in item.items() if key != "items"}
            for item in passes
        ],
        "hits": warm["hits"],
        "misses": warm["misses"],
        "elapsed_s": warm["elapsed_s"],
        "cold_elapsed_s": warm["cold_elapsed_s"],
        "saved_s": warm["saved_s"],
        "items": warm["items"],
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    BARS_DIR.mkdir(parents=True, exist_ok=True)
    COMPARISONS_DIR.mkdir(parents=True, exist_ok=True)
    built_at = datetime.now(timezone.utc).isoformat()
    passes = [run_pass("1"), run_pass("2")]
    write_cache_report(passes)
    write_build_info(built_at)


if __name__ == "__main__":
    main()

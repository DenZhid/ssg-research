from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "data-analyze-script"
DST_DIR = ROOT / "docs-site" / "docs" / "assets"
FOLDERS = ("charts", "comparisons")


def main() -> None:
    DST_DIR.mkdir(parents=True, exist_ok=True)

    for name in FOLDERS:
        src = SRC_DIR / name
        dst = DST_DIR / name

        if not src.is_dir():
            raise SystemExit(f"Source folder not found: {src}")

        if dst.exists():
            shutil.rmtree(dst)

        shutil.copytree(src, dst)
        print(f"Copied {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

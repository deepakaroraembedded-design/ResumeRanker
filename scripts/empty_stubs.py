#!/usr/bin/env python3
"""Convert all module-level NotImplementedError stubs into empty modules."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def is_stub(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return "raise NotImplementedError" in text and "from __future__ import annotations" in text


def main() -> None:
    count = 0
    for root, _dirs, files in os.walk(ROOT / "src"):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = Path(root) / fname
            if not is_stub(path):
                continue
            path.write_text("from __future__ import annotations\n", encoding="utf-8")
            count += 1
    print(f"Emptied {count} component stubs.")


if __name__ == "__main__":
    main()

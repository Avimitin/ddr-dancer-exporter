"""Locate local source code without requiring an editable install."""
from pathlib import Path
import sys
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/ddr_dancer_exporter").is_dir())
for directory in (ROOT / "src", ROOT / "scripts"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

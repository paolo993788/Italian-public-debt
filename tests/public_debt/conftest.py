"""Fall back to the source folder when public_debt is not installed (the C++
extension must still have been built in place)."""

import sys
from pathlib import Path

try:
    import public_debt  # noqa: F401
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "public_debt"))

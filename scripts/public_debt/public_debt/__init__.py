"""Italian public debt and GDP: accounting, fiscal analysis and debt sustainability.

The compiled extension ``public_debt._core`` projects the debt ratio and runs
the stochastic debt sustainability analysis (Monte Carlo fan charts and
fiscal-adjustment grids). The Python modules load official data (Eurostat,
IMF), decompose debt dynamics, estimate cyclically adjusted balances and
fiscal reaction functions, fit the VAR used for the shocks and decompose
GDP growth.
"""

__version__ = "0.1.0"

try:
    from . import _core  # noqa: F401
except ImportError as exc:  # pragma: no cover - depends on the local build
    _core = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

HAS_CPP = _core is not None


def require_cpp():
    """Return the compiled extension or raise an informative error."""
    if _core is None:
        raise ImportError(
            "The C++ extension public_debt._core is not built. From the repository root run "
            "`python -m pip install -e scripts/public_debt` (a C++17 compiler is required)."
        ) from _IMPORT_ERROR
    return _core

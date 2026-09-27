"""C++ debt engine: identity, stabilisation, deterministic limit of the stochastic model."""

import numpy as np

from public_debt import accounting, dsa, require_cpp
from public_debt.var import VAR1

core = require_cpp()


def scenario(pb=0.01):
    return dsa.Scenario.constant(2025, 10, growth=0.008, inflation=0.02, market_rate=0.037, primary_balance=pb, sfa=0.001)


def zero_var():
    return VAR1(["g", "pi", "r"], np.zeros(3), np.zeros((3, 3)), np.zeros((5, 3)), "none")


def test_projection_matches_python_identity():
    s = scenario()
    out = dsa.project(1.35, 0.035, 0.15, s)
    i = [0.035]
    for r in s.market_rate:
        i.append(0.85 * i[-1] + 0.15 * r)
    expected = accounting.replay(1.35, i[1:], s.growth, s.inflation, s.primary_balance, s.sfa)
    np.testing.assert_allclose(out["debt"], expected, rtol=1e-13)
    np.testing.assert_allclose(out["effective_rate"], i[1:], rtol=1e-13)


def test_stabilising_primary_balance_keeps_debt_constant():
    d0, i, g, pi = 1.35, 0.035, 0.008, 0.02
    pb = float(accounting.stabilising_primary_balance(d0, i, g, pi))
    s = dsa.Scenario.constant(2025, 8, g, pi, i, pb, 0.0)
    out = dsa.project(d0, i, 0.0, s)
    np.testing.assert_allclose(out["debt"], d0, rtol=1e-12)


def test_stochastic_without_shocks_equals_deterministic():
    s = scenario()
    det = dsa.project(1.35, 0.035, 0.15, s)["debt"].to_numpy()
    fan = dsa.stochastic(1.35, 0.035, 0.15, s, zero_var(), n_paths=50, seed=1)
    np.testing.assert_allclose(fan["paths"], np.tile(det, (50, 1)), rtol=1e-13)


def test_fiscal_reaction_reduces_dispersion_and_threads_are_irrelevant():
    rng = np.random.default_rng(0)
    var = VAR1(["g", "pi", "r"], np.zeros(3), np.diag([0.3, 0.5, 0.6]), rng.normal(0, [0.015, 0.008, 0.006], (40, 3)), "sim")
    s = scenario()
    loose = dsa.stochastic(1.35, 0.035, 0.15, s, var, rho=0.0, n_paths=20_000, seed=2)["paths"][:, -1]
    tight = dsa.stochastic(1.35, 0.035, 0.15, s, var, rho=0.05, n_paths=20_000, seed=2)["paths"][:, -1]
    assert tight.std() < loose.std()
    a = core.stochastic_dsa(1.35, 0.035, 0.15, *s.arrays(), var.A, var.residuals, np.zeros(3), 0.5, 0.0, 0.0, 500, 3, 1)
    b = core.stochastic_dsa(1.35, 0.035, 0.15, *s.arrays(), var.A, var.residuals, np.zeros(3), 0.5, 0.0, 0.0, 500, 3, 4)
    np.testing.assert_array_equal(a["debt"], b["debt"])


def test_adjustment_grid_is_monotone():
    rng = np.random.default_rng(1)
    var = VAR1(["g", "pi", "r"], np.zeros(3), np.diag([0.3, 0.5, 0.6]), rng.normal(0, [0.015, 0.008, 0.006], (40, 3)), "sim")
    grid = dsa.adjustment_grid(1.35, 0.035, 0.15, scenario(pb=0.0), var, [0.0, 0.004, 0.008], [4, 7], 2028, 2034,
                               n_paths=5000, seed=3)
    assert np.all(np.diff(grid.to_numpy(), axis=0) <= 1e-12)  # more adjustment, lower probability of rising debt

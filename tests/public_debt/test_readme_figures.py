"""The README figures render in both themes on offline placeholder data."""

import matplotlib

matplotlib.use("Agg")

from public_debt import readme_figures  # noqa: E402
from public_debt.figstyle import render  # noqa: E402


def test_all_readme_figures_render_in_both_themes(tmp_path):
    inputs = {"main": readme_figures.load(official=False, n_paths=2_000),
              "spreads": readme_figures.load_spreads(official=False)}
    assert set(inputs) == set(readme_figures.LOADERS)
    for name, (builder, key) in readme_figures.FIGURES.items():
        paths = render(builder, name, tmp_path, inputs[key])
        assert [p.name for p in paths] == [f"{name}-light.png", f"{name}-dark.png"]
        assert all(p.stat().st_size > 10_000 for p in paths)

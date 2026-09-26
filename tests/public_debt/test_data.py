"""Eurostat and IMF parsers and the offline assembly of the fiscal dataset."""

import json

import numpy as np
import pytest

from public_debt import data


def jsonstat(dims, sizes, codes, values):
    return {"version": "2.0", "class": "dataset", "id": dims, "size": sizes,
            "dimension": {d: {"category": {"index": {c: i for i, c in enumerate(cs)}}} for d, cs in zip(dims, codes)},
            "value": {str(k): v for k, v in values.items()}}


def test_parse_and_select():
    doc = jsonstat(["na_item", "time"], [2, 2], [["GD", "B9"], ["2022", "2023"]], {0: 140.0, 1: 135.0, 2: -8.0})
    frame = data.parse_jsonstat(doc)
    assert len(frame) == 3
    with pytest.raises(KeyError, match="available"):
        data.select(frame, na_item="D41PAY")


def test_fiscal_dataset_from_cached_files(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DEBT_DATA_DIR", str(tmp_path))
    years = ["2021", "2022", "2023"]
    edp = jsonstat(["unit", "sector", "na_item", "geo", "time"], [1, 1, 3, 1, 3],
                   [["PC_GDP"], ["S13"], ["GD", "B9", "D41PAY"], ["IT"], years],
                   {0: 150.0, 1: 140.0, 2: 135.0, 3: -9.0, 4: -8.0, 5: -7.0, 6: 3.5, 7: 4.2, 8: 3.8})
    gdp = jsonstat(["unit", "na_item", "geo", "time"], [2, 1, 1, 3], [["CP_MEUR", "CLV_PCH_PRE"], ["B1GQ"], ["IT"], years],
                   {0: 1800000.0, 1: 1950000.0, 2: 2100000.0, 3: 8.0, 4: 4.0, 5: 1.0})
    data.eurostat_cache_path("gov_10dd_edpt1", geo="IT", unit="PC_GDP", sector="S13").write_text(json.dumps(edp))
    data.eurostat_cache_path("nama_10_gdp", geo="IT", na_item="B1GQ").write_text(json.dumps(gdp))
    f = data.fiscal_dataset("IT")
    assert f.loc[2023, "primary_balance"] == pytest.approx(-0.07 + 0.038)
    gamma = 2100000.0 / 1950000.0 - 1
    assert f.loc[2023, "nominal_growth"] == pytest.approx(gamma)
    assert f.loc[2023, "inflation"] == pytest.approx((1 + gamma) / 1.01 - 1)
    assert f.loc[2023, "effective_rate"] == pytest.approx(0.038 * (1 + gamma) / 1.40)


def test_imf_series_from_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_DEBT_DATA_DIR", str(tmp_path))
    payload = {"values": {"GGXWDG_NGDP": {"ITA": {"1980": 55.0, "1981": 58.5}}}, "api": {"version": "1"}}
    (data.cache_dir("imf") / "GGXWDG_NGDP_ITA.json").write_text(json.dumps(payload))
    s = data.imf_series("GGXWDG_NGDP")
    assert list(s.index) == [1980, 1981] and s.loc[1981] == pytest.approx(58.5)

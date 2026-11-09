"""Revision 3: with_baro redirects only data/clean/usgs/ reads, and the corrected files differ only in DO.
Run: python -m pytest -p no:cacheprovider tests/test_revision3_with_baro.py (from Paper2/)."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")


def test_redirect_only_usgs_folder():
    from revision3 import with_baro as W
    a = W._redirect("data/clean/usgs/11509500.csv")
    b = pd.read_csv("data/clean/usgs_baro/11509500.csv")
    assert a.equals(b)
    c = W._redirect("data/clean/usgs_2024/11509500.csv")        # other folders untouched
    assert "p_ratio" not in c.columns


def test_baro_changes_only_do():
    f = pd.read_csv("data/clean/usgs/11509500.csv"); g = pd.read_csv("data/clean/usgs_baro/11509500.csv")
    pr = g.p_ratio.iloc[0]
    assert 0.85 < pr < 0.88                                       # Keno, about 1,200 m
    for c in f.columns:
        if c == "DO":
            assert np.allclose(g.DO, f.DO / pr, equal_nan=True)
        else:
            assert f[c].equals(g[c]), c

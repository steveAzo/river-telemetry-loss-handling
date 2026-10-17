"""Tests for the revision code: deviation D5 (inclusive tolerance), the eligibility rule and the
confirmatory runner's seeds (run from Paper2/: python -m pytest tests -q)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, "src")
from confirm.eligibility import site_row  # noqa: E402
from confirm.run_confirm import site_seed  # noqa: E402
from design.sitedata import make_trigger, within_tol  # noqa: E402


def test_within_tol_counts_decimal_ties_as_within():
    # one recording step of 0.1 is "exactly" the L2 pH tolerance, whatever the float round-off
    assert 7.4 - 7.3 > 0.1 and 7.3 - 7.2 < 0.1                 # the round-off this guards against
    assert within_tol(7.4 - 7.3, 0.1) and within_tol(7.3 - 7.2, 0.1) and within_tol(-(7.4 - 7.3), 0.1)
    assert not within_tol(0.11, 0.1)
    assert list(within_tol(np.array([0.2, 0.2000001, -0.3]), np.array([0.2, 0.2, 0.2]))) == [True, False, False]


@pytest.mark.parametrize("a,b", [(7.3, 7.4), (7.2, 7.3), (8.0, 8.1)])
def test_trigger_does_not_fire_at_exactly_the_tolerance(a, b):
    """A reading one 0.1 step away from what the server shows is within a 0.1 tolerance (D5)."""
    X = np.array([[a], [b]])
    arr = np.array([0.0, np.inf])                               # slot 0 delivered, slot 1 is the new reading
    assert not make_trigger(X, np.array([0.1]), spd=10_000)(1, arr)
    assert make_trigger(X, np.array([0.05]), spd=10_000)(1, arr)


def test_eligibility_reproduces_the_2023_file():
    old = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str}).set_index("site")
    for site in ("01438500", "01473900", "14210000", "01474500", "14206694"):
        r = site_row(f"data/clean/usgs/{site}.csv", 2023)
        assert r["status"] == old.loc[site, "status"]
        if np.isfinite(old.loc[site, "complete_frac_of_year"]):
            assert r["complete_frac_of_year"] == pytest.approx(old.loc[site, "complete_frac_of_year"], abs=1e-12)


def test_confirmatory_seed_differs_from_development_seed():
    assert site_seed("01463500", 0) == int("01463500") % (2 ** 31 - 1)     # development (D3)
    assert site_seed("01463500", 2024) != site_seed("01463500", 0)
    assert site_seed("420853121505500", 2024) < 2 ** 31 - 1

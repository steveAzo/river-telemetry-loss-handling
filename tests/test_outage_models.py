"""Numerical correctness of the outage-length models (run from Paper2/: python -m pytest tests -q)."""
import sys

import numpy as np
import pytest
from scipy import stats

sys.path.insert(0, "src/scoping")
from outage_models import fit_dlnorm, fit_geom, fit_geom2, logpmf_dlnorm, pmf_dlnorm  # noqa: E402


@pytest.mark.parametrize("mu,s", [(0.0, 1.0), (-3.7, 2.8), (2.0, 0.5), (-20.0, 6.0), (-25.0, 0.22)])
def test_dlnorm_pmf_is_a_proper_distribution(mu, s):
    """sum_{k<=K} P(k) + P(X > K + 0.5 | X > 0.5) = 1, with the tail computed analytically,
    including extreme parameters where the old code underflowed."""
    K = 200_000
    k = np.arange(1, K + 1, dtype=float)
    lp = logpmf_dlnorm(k, mu, s)
    assert not np.any(np.isnan(lp))
    tail = np.exp(stats.norm.logsf((np.log(K + 0.5) - mu) / s) - stats.norm.logsf((np.log(0.5) - mu) / s))
    assert np.exp(lp).sum() + tail == pytest.approx(1.0, abs=1e-9)


def test_dlnorm_pmf_matches_direct_formula_in_safe_region():
    k = np.arange(1, 50, dtype=float); mu, s = 1.0, 1.2
    direct = (stats.norm.cdf((np.log(k + .5) - mu) / s) - stats.norm.cdf((np.log(k - .5) - mu) / s)) \
        / (1 - stats.norm.cdf((np.log(.5) - mu) / s))
    assert pmf_dlnorm(k, mu, s) == pytest.approx(direct, rel=1e-9)


def test_dlnorm_fit_recovers_parameters():
    rng = np.random.default_rng(0)
    x = np.rint(rng.lognormal(1.5, 1.0, 20000)); x = x[x >= 1]
    par, ll, _ = fit_dlnorm(x)
    assert par["mu"] == pytest.approx(1.5, abs=0.05) and par["sigma"] == pytest.approx(1.0, abs=0.05)


def test_no_spurious_perfect_fit():
    """The pre-fix code reached log-likelihood ~0 (AIC 4) on real data; a correct fit cannot."""
    rng = np.random.default_rng(1)
    x = np.concatenate([np.ones(9000), rng.integers(2, 400, 1000)]).astype(float)
    _, ll, _ = fit_dlnorm(x)
    assert ll < -1000


def test_geometric_fits():
    rng = np.random.default_rng(2)
    x = rng.geometric(0.3, 50000).astype(float)
    par, _, _ = fit_geom(x)
    assert par["q"] == pytest.approx(0.7, abs=0.01)
    p2, _, _ = fit_geom2(np.concatenate([rng.geometric(0.6, 40000), rng.geometric(0.01, 2000)]).astype(float))
    assert p2["q_short"] == pytest.approx(0.4, abs=0.03) and p2["q_long"] == pytest.approx(0.99, abs=0.005)

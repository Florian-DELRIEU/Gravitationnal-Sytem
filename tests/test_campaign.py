"""T13: injection-recovery campaign (random systems, N-body simulation, noisy irregular observations)."""

import numpy as np
import pytest

from gravsim.analysis.campaign import CampaignSettings, random_system, run_campaign
from gravsim.core.simulation import Simulation


def test_random_systems_are_reasonable():
    st = CampaignSettings()
    rng = np.random.default_rng(3)
    for _ in range(20):
        sc = random_system(rng, st)
        n = len(sc.bodies) - 1
        assert st.n_planets[0] <= n <= st.n_planets[1]
        assert np.hypot(*sc.barycenter()[1]) < 1e-12  # momentum cancelled
        sim = Simulation(sc, "dop853")
        sim.run(0.05)
        assert not sim.trajectory.collisions


@pytest.fixture(scope="module")
def campaign():
    return run_campaign(CampaignSettings(n_systems=10, seed=7))


def test_T13_campaign_metrics(campaign):
    summary = campaign.summary()
    assert summary["systemes"] == 10 and summary["planetes"] >= 10
    assert summary["fausses_detections_par_systeme"] == 0.0  # no invented planet
    assert summary["compte_exact"] >= 0.7
    assert summary["erreur_periode_mediane"] < 5e-3
    assert summary["erreur_amplitude_mediane"] < 0.10  # expected ~ 1 / SNR (10 % at SNR 10)
    for lo, hi, n, found in campaign.completeness_by_snr():
        if lo >= 7 and n:
            assert found == 1.0  # every planet with K / sigma * sqrt(N / 2) >= 7 is found


def test_T13_outcomes_are_consistent(campaign):
    for o in campaign.outcomes:
        found = sum(t.found for t in o.truths)
        assert found + o.spurious == o.detected
        assert o.exact == (found == len(o.truths) and o.spurious == 0)
        for t in o.truths:
            assert (t.period_error is not None) == t.found

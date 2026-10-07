"""Injection-recovery campaign: random systems of known truth, simulated, observed with noise, detected blindly.

Each system is integrated with the full N-body simulator (planet-planet interactions included), observed in
radial velocity on an irregular schedule with seasonal gaps and white noise, then handed to ``detection.detect``
which never sees the truth. The truth is only used to score the result.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from ..core import units
from ..core.body import Body
from ..core.scenario import Scenario
from ..core.simulation import Simulation
from . import observer, orbits
from .detection import DetectionResult, DetectionSettings, detect_observations, match_truth


@dataclass
class CampaignSettings:
    n_systems: int = 60
    seed: int = 2026
    n_planets: tuple[int, int] = (1, 3)  # inclusive range
    star_mass: tuple[float, float] = (0.6, 1.2)  # Msun
    period_range: tuple[float, float] = (0.05, 2.0)  # yr, log-uniform
    mass_range: tuple[float, float] = (0.02, 3.0)  # Mjup, log-uniform
    e_max: float = 0.3
    min_period_ratio: float = 1.6
    min_hill_separation: float = 4.0  # mutual Hill radii between periapsis and apoapsis of neighbours
    baseline: float = 4.0  # yr
    n_obs: int = 100
    season_fraction: float = 0.3
    sigma: float = 3.0  # m/s
    detection: DetectionSettings = field(default_factory=DetectionSettings)


@dataclass
class TruePlanet:
    period: float
    amplitude: float  # K, m/s (Jacobi elements of the simulated system)
    e: float
    mass_mjup: float
    snr: float  # K / sigma * sqrt(N / 2)
    found: bool = False
    period_error: float | None = None  # relative
    amplitude_error: float | None = None  # relative

    @property
    def frequency(self) -> float:
        return 1.0 / self.period


@dataclass
class SystemOutcome:
    index: int
    star_mass: float
    truths: list[TruePlanet]
    detected: int
    possible_counts: list[int]
    spurious: int
    runtime: float
    result: DetectionResult | None = field(default=None, repr=False)

    @property
    def exact(self) -> bool:
        return self.detected == len(self.truths) and self.spurious == 0 and all(t.found for t in self.truths)

    @property
    def count_possible(self) -> bool:
        return len(self.truths) in self.possible_counts


@dataclass
class CampaignResult:
    settings: CampaignSettings
    outcomes: list[SystemOutcome]

    SNR_BINS = (0.0, 5.0, 10.0, 20.0, 50.0, math.inf)

    def planets(self) -> list[TruePlanet]:
        return [p for o in self.outcomes for p in o.truths]

    def completeness_by_snr(self) -> list[tuple[float, float, int, float]]:
        """(low, high, number of planets, fraction found) per SNR bin."""
        rows = []
        planets = self.planets()
        for lo, hi in zip(self.SNR_BINS[:-1], self.SNR_BINS[1:]):
            sel = [p for p in planets if lo <= p.snr < hi]
            rows.append((lo, hi, len(sel), float(np.mean([p.found for p in sel])) if sel else float("nan")))
        return rows

    def summary(self) -> dict:
        planets = self.planets()
        found = [p for p in planets if p.found]
        n = max(len(self.outcomes), 1)
        return {
            "systemes": len(self.outcomes),
            "planetes": len(planets),
            "compte_exact": sum(o.exact for o in self.outcomes) / n,
            "compte_dans_les_possibles": sum(o.count_possible for o in self.outcomes) / n,
            "systemes_ambigus": sum(len(o.possible_counts) > 1 for o in self.outcomes) / n,
            "completude": len(found) / max(len(planets), 1),
            "fausses_detections_par_systeme": sum(o.spurious for o in self.outcomes) / n,
            "systemes_avec_fausse_detection": sum(o.spurious > 0 for o in self.outcomes) / n,
            "erreur_periode_mediane": float(np.median([abs(p.period_error) for p in found])) if found else float("nan"),
            "erreur_amplitude_mediane": float(np.median([abs(p.amplitude_error) for p in found])) if found else float("nan"),
            "duree_moyenne_s": float(np.mean([o.runtime for o in self.outcomes])) if self.outcomes else 0.0,
        }


def _hill_ok(star, planets, minimum):
    """Neighbouring planets separated by at least ``minimum`` mutual Hill radii (periapsis to apoapsis)."""
    for (p1, m1, e1), (p2, m2, e2) in zip(planets[:-1], planets[1:]):
        a1 = (units.G * (star + m1) * p1**2 / (4 * math.pi**2)) ** (1 / 3)
        a2 = (units.G * (star + m2) * p2**2 / (4 * math.pi**2)) ** (1 / 3)
        r_hill = ((m1 + m2) / (3 * star)) ** (1 / 3) * 0.5 * (a1 + a2)
        if a2 * (1 - e2) - a1 * (1 + e1) < minimum * r_hill:
            return False
    return True


def random_system(rng: np.random.Generator, st: CampaignSettings) -> Scenario:
    """A random, dynamically reasonable planetary system (bodies 'star', 'p0', 'p1', ...)."""
    star = float(rng.uniform(*st.star_mass))
    lp = np.log(st.period_range)
    lm = np.log(st.mass_range)
    for _ in range(500):
        n = int(rng.integers(st.n_planets[0], st.n_planets[1] + 1))
        periods = np.sort(np.exp(rng.uniform(*lp, n)))
        if n > 1 and np.min(periods[1:] / periods[:-1]) < st.min_period_ratio:
            continue
        masses = np.exp(rng.uniform(*lm, n)) * units.M_JUP
        ecc = rng.uniform(0.0, st.e_max, n)
        if _hill_ok(star, list(zip(periods, masses, ecc)), st.min_hill_separation):
            break
    else:  # fall back to a single planet if no stable configuration came up
        n, periods = 1, np.exp(rng.uniform(*lp, 1))
        masses, ecc = np.exp(rng.uniform(*lm, 1)) * units.M_JUP, rng.uniform(0.0, st.e_max, 1)
    sc = Scenario(name="système aléatoire")
    sc.add(Body("star", star, radius=units.R_SUN))
    for k in range(n):
        a = (units.G * (star + masses[k]) * periods[k] ** 2 / (4 * math.pi**2)) ** (1 / 3)
        ang = rng.uniform(0, 2 * math.pi)
        r = a * (1 - ecc[k])
        sc.add(Body(f"p{k}", float(masses[k]), [r * math.cos(ang), r * math.sin(ang)]))
        sc.set_orbital_velocity(f"p{k}", "star", e=float(ecc[k]), clockwise=False)
    sc.zero_total_momentum()
    return sc


def run_system(index: int, sc: Scenario, st: CampaignSettings, rng: np.random.Generator,
               keep_result: bool = False) -> SystemOutcome:
    started = time.perf_counter()
    truths_sig = orbits.reflex_signatures(Simulation(sc, "dop853").trajectory, "star")
    p_min = truths_sig[0].period
    sim = Simulation(sc, "dop853", output_dt=p_min / 40.0, rtol=1e-10, atol=1e-12)
    sim.run(st.baseline)
    traj = sim.trajectory
    times = observer.random_schedule(0.0, traj.t[-1], st.n_obs, rng=rng, season_fraction=st.season_fraction)
    obs = observer.observe_rv(traj, "star", times, sigma=st.sigma, rng=rng)
    res = detect_observations(obs, star_mass=sc.masses[0], settings=st.detection)
    match = match_truth(res.planets, truths_sig, res.baseline)
    noise = st.sigma if st.sigma > 0 else 1e-3
    truths = [TruePlanet(t.period, t.rv_semi_amplitude, t.e, sc.body(t.name).mass / units.M_JUP,
                         t.rv_semi_amplitude / noise * math.sqrt(len(times) / 2.0)) for t in truths_sig]
    for i, j in match.matches:
        p = res.planets[i]
        truths[j].found = True
        truths[j].period_error = p.period / truths[j].period - 1.0
        truths[j].amplitude_error = p.amplitude / truths[j].amplitude - 1.0
    return SystemOutcome(index, float(sc.masses[0]), truths, res.count, res.possible_counts, len(match.spurious),
                         time.perf_counter() - started, res if keep_result else None)


def run_campaign(st: CampaignSettings | None = None, progress=None, keep_results: bool = False) -> CampaignResult:
    """Run the whole campaign; ``progress(i, n, outcome)`` is called after each system."""
    st = st or CampaignSettings()
    rng = np.random.default_rng(st.seed)
    outcomes = []
    for i in range(st.n_systems):
        sc = random_system(rng, st)
        outcome = run_system(i, sc, st, rng, keep_results)
        outcomes.append(outcome)
        if progress is not None:
            progress(i + 1, st.n_systems, outcome)
    return CampaignResult(st, outcomes)

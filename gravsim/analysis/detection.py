"""Blind detection of planets in a star's reflex signal (radial velocity or astrometry).

Method: iterative prewhitening with global Keplerian fits.

1. Periodogram of the residuals (windowed FFT on dense regular data, generalised Lomb-Scargle or the
   complex periodogram otherwise). Its highest peak is the candidate.
2. The candidate is kept only if its false-alarm probability is below a threshold, its amplitude is above
   a floor (relative to the strongest planet), and the model with one more component lowers the BIC by more
   than a threshold (10 = very strong evidence).
3. A candidate at a harmonic (2f, 3f, 4f) of a known planet is first explained, if possible, by a better
   eccentricity of that planet. At 2f the alternative "that planet is in fact two circular planets in 2:1
   resonance" is fitted too; the lowest BIC wins.
4. A candidate at a combination of two known frequencies (a f_i + b f_j), within 1/T of a known component,
   or too close to a known planet (period ratio < 1.25), is fitted as a non-planetary component (planet-planet
   interaction, precession of an orbit) and not counted. So is a weak (near-)harmonic of a planet (implied mass
   < 25 % of that planet's; flagged as possibly a small resonant planet) and a period longer than the
   observations (a trend).
5. At the end, every 2:1 pair is compared with a single eccentric planet, and every eccentric planet whose
   2f signal is significant with a circular 2:1 pair. Unless one reading is strongly favoured (BIC difference
   >= 6, Kass & Raftery) the data cannot tell them apart: the result says so (ambiguity) instead of picking.

The detection never sees the true planets: ``match_truth`` uses them afterwards, only to score the result.

Signal models (t_ref = first observation, n = 2 pi / P, mean longitude lambda, e = h^2 + k^2):
    radial velocity  v = K [cos(nu + omega) + e cos omega],   M = n (t - t_ref) + lambda - omega
    astrometry       z = A exp(i varpi) [(cos E - e) + i s sqrt(1 - e^2) sin E],   M = s (lambda - varpi) + n (t - t_ref)
with h = sqrt(e) sin(angle), k = sqrt(e) cos(angle), s = +1 counterclockwise / -1 clockwise. For e = 0 they
reduce to K cos(n (t - t_ref) + lambda) and A exp(i (lambda + s n (t - t_ref))).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np
from scipy.optimize import least_squares, minimize_scalar

from ..core import units
from . import spectral

E_MAX = 0.95  # eccentricities are capped here (Kepler's equation and the fit stay well behaved)
_HK_MAX = math.sqrt(E_MAX)
_KEP, _CIRC, _NUIS = "kep", "circ", "nuis"
CLOSE_RATIO = 1.25  # two planets with closer periods would not be resolved / stable: a modulation instead
HARMONIC_MASS_RATIO = 0.25  # a (near-)harmonic of planet j implying less than this mass ratio is not counted
HARMONIC_TOL = 0.05  # relative distance to n f_j within which a peak is treated as a (near-)harmonic
RESONANCES = ((2, 1), (3, 2), (3, 1), (4, 3))  # p:q mean-motion resonances whose slow terms are recognised
_SIZES = {_KEP: 5, _CIRC: 3, _NUIS: 3}


# --- Kepler ------------------------------------------------------------------------------------------


def solve_kepler(M, e: float, tol: float = 1e-12, max_iter: int = 60) -> np.ndarray:
    """Eccentric anomaly E with E - e sin E = M (Newton; M wrapped to [-pi, pi])."""
    M = np.mod(np.asarray(M, dtype=float) + np.pi, 2.0 * np.pi) - np.pi
    E = M + e * np.sin(M) if e < 0.8 else np.where(M >= 0, np.pi, -np.pi)
    for _ in range(max_iter):
        step = (E - e * np.sin(E) - M) / (1.0 - e * np.cos(E))
        E = E - step
        if np.max(np.abs(step), initial=0.0) < tol:
            break
    return E


def true_anomaly(E: np.ndarray, e: float) -> np.ndarray:
    return 2.0 * np.arctan2(math.sqrt(1.0 + e) * np.sin(0.5 * E), math.sqrt(1.0 - e) * np.cos(0.5 * E))


def _signal(kind: str, p: np.ndarray, sense: int, t: np.ndarray, data: str, t_ref: float) -> np.ndarray:
    """Signal of one component with parameters ``p`` ([P, A, h, k, lambda] or [P, A, lambda])."""
    P, A = p[0], p[1]
    if kind == _KEP:
        h, k, lam = p[2], p[3], p[4]
        e = min(h * h + k * k, E_MAX)
        ang = math.atan2(h, k) if e > 0 else 0.0
    else:
        lam, e, ang = p[2], 0.0, 0.0
    n = 2.0 * math.pi / P
    dt = t - t_ref
    if data == "rv":
        if e == 0.0:
            return A * np.cos(n * dt + lam)
        nu = true_anomaly(solve_kepler(n * dt + lam - ang, e), e)
        return A * (np.cos(nu + ang) + e * math.cos(ang))
    if e == 0.0:
        return A * np.exp(1j * (lam + sense * n * dt))
    E = solve_kepler(sense * (lam - ang) + n * dt, e)
    return A * np.exp(1j * ang) * ((np.cos(E) - e) + 1j * sense * math.sqrt(1.0 - e * e) * np.sin(E))


# --- data structures ------------------------------------------------------------------------------------


@dataclass
class DetectionSettings:
    fap_threshold: float = 1e-3  # a peak is significant below this false-alarm probability
    bic_threshold: float = 10.0  # BIC gain required to add a component ("very strong" evidence)
    ambiguity_margin: float = 6.0  # an alternative reading is ruled out only if its BIC is worse by this ("strong")
    max_planets: int = 6
    max_components: int = 12  # planets + non-planetary components
    min_amplitude_ratio: float = 1e-3  # ignore peaks weaker than this fraction of the strongest planet
    period_min: float | None = None  # search range (default: Nyquist .. observation length)
    period_max: float | None = None
    fit_points: int = 6000  # dense data are fitted on a random subset of this size (search uses all data)
    oversample: float = 5.0
    seed: int = 0


@dataclass
class _Comp:
    kind: str
    params: np.ndarray
    sense: int = 1
    p_bounds: tuple[float, float] = (0.0, math.inf)
    fap: float | None = None
    delta_bic: float | None = None
    note: str = ""

    @property
    def size(self) -> int:
        return _SIZES[self.kind]

    @property
    def period(self) -> float:
        return float(self.params[0])

    @property
    def frequency(self) -> float:
        return 1.0 / float(self.params[0])

    @property
    def amplitude(self) -> float:
        return float(self.params[1])

    @property
    def e(self) -> float:
        return min(float(self.params[2] ** 2 + self.params[3] ** 2), E_MAX) if self.kind == _KEP else 0.0

    @property
    def angle(self) -> float:
        return math.atan2(self.params[2], self.params[3]) if self.kind == _KEP and self.e > 0 else float("nan")

    @property
    def lam(self) -> float:
        return float(self.params[-1])

    @property
    def is_planet(self) -> bool:
        return self.kind in (_KEP, _CIRC)

    def copy(self) -> "_Comp":
        return replace(self, params=np.array(self.params, dtype=float))


@dataclass
class DetectedPlanet:
    period: float  # yr
    amplitude: float  # K in m/s (radial velocity) or semi-major axis of the star's reflex orbit in AU (astrometry)
    e: float
    omega: float  # argument of periastron (rad), nan for a circular fit
    mean_longitude: float  # rad, at the first observation
    sense: int  # +1 counterclockwise, -1 clockwise (astrometry), 0 unknown (radial velocity)
    mass: float | None  # Msun: m sin i for radial velocity, true mass for face-on astrometry
    a: float | None  # AU, planet's semi-major axis (third law)
    fap: float | None
    delta_bic: float | None
    note: str = ""

    @property
    def frequency(self) -> float:
        return 1.0 / self.period

    @property
    def mass_mjup(self) -> float | None:
        return None if self.mass is None else self.mass / units.M_JUP

    @property
    def mass_mearth(self) -> float | None:
        return None if self.mass is None else self.mass / units.M_EARTH


@dataclass
class OtherComponent:
    """A significant periodic signal judged non-planetary (interaction term, precession, modulation)."""

    period: float
    amplitude: float
    reason: str


@dataclass
class Ambiguity:
    text: str
    alternative_count: int
    delta_bic: float  # BIC(alternative) - BIC(retained model): |.| < threshold means undecidable


@dataclass
class DetectionStep:
    index: int
    period: float
    amplitude: float
    power: float
    fap: float
    delta_bic: float | None
    decision: str
    freq: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))  # residual periodogram (decimated)
    spectrum: np.ndarray = field(repr=False, default_factory=lambda: np.empty(0))


@dataclass
class DetectionResult:
    kind: str
    planets: list[DetectedPlanet]
    others: list[OtherComponent]
    ambiguities: list[Ambiguity]
    steps: list[DetectionStep]
    stop_reason: str
    n_obs: int
    baseline: float
    rms_residual: float
    settings: DetectionSettings
    t_ref: float
    _comps: list[_Comp] = field(repr=False, default_factory=list)
    _offset: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(1))

    @property
    def count(self) -> int:
        return len(self.planets)

    @property
    def possible_counts(self) -> list[int]:
        return sorted({self.count} | {a.alternative_count for a in self.ambiguities})

    @property
    def ambiguous(self) -> bool:
        return bool(self.ambiguities)

    def count_text(self) -> str:
        counts = self.possible_counts
        word = "planète" if max(counts) <= 1 else "planètes"
        if len(counts) == 1:
            return f"{counts[0]} {word} détectée{'s' if counts[0] > 1 else ''}"
        return f"{' ou '.join(str(c) for c in counts)} {word} (AMBIGU)"

    def model(self, t) -> np.ndarray:
        """Fitted signal (all components, offset included) at times ``t``."""
        t = np.asarray(t, dtype=float)
        return _model(t, self._comps, self._offset, self.kind, self.t_ref)

    def planet_model(self, t) -> np.ndarray:
        """Fitted signal of the planets only (no offset, no non-planetary component)."""
        t = np.asarray(t, dtype=float)
        out = np.zeros(len(t), dtype=complex if self.kind == "astrometry" else float)
        for c in self._comps:
            if c.is_planet:
                out = out + _signal(c.kind, c.params, c.sense, t, self.kind, self.t_ref)
        return out


def _model(t, comps, offset, data, t_ref) -> np.ndarray:
    base = complex(offset[0], offset[1]) if data == "astrometry" else float(offset[0])
    out = np.full(len(t), base, dtype=complex if data == "astrometry" else float)
    for c in comps:
        out = out + _signal(c.kind, c.params, c.sense, t, data, t_ref)
    return out


# --- fitting context ------------------------------------------------------------------------------------------


class _Ctx:
    def __init__(self, t, y, dy, data: str, st: DetectionSettings):
        order = np.argsort(t)
        self.t = np.asarray(t, dtype=float)[order]
        self.y = np.asarray(y)[order]
        self.data, self.st = data, st
        dy = None if dy is None else np.asarray(dy, dtype=float)[order]
        self.weighted = dy is not None and bool(np.all(dy > 0))
        self.dy = dy if self.weighted else None
        self.w = 1.0 / dy if self.weighted else np.ones(len(self.t))
        self.t_ref = float(self.t[0])
        self.T = float(self.t[-1] - self.t[0])
        diffs = np.diff(self.t)
        self.regular = bool(np.max(np.abs(diffs - diffs.mean())) <= 1e-6 * diffs.mean())
        f_nyquist = 0.5 / float(np.median(diffs))
        self.f_min = 1.0 / st.period_max if st.period_max else 1.0 / self.T
        self.f_max = min(f_nyquist, 1.0 / st.period_min) if st.period_min else f_nyquist
        n = len(self.t)
        if n > st.fit_points:
            idx = np.sort(np.random.default_rng(st.seed).choice(n, st.fit_points, replace=False))
        else:
            idx = np.arange(n)
        self.ft, self.fy, self.fw = self.t[idx], self.y[idx], self.w[idx]
        self.offset_size = 2 if data == "astrometry" else 1
        self.n_eff = len(idx) * self.offset_size
        scale = float(np.sqrt(np.mean(np.abs(self.y - self.y.mean()) ** 2))) or 1.0
        self.rss_floor = self.n_eff * (1e-9 * scale) ** 2
        # No component can be much larger than the data themselves: this ceiling stops two components at
        # nearly the same frequency from cancelling each other with huge amplitudes.
        self.amp_max = 2.5 * float(np.max(np.abs(self.y - self.y.mean()))) or 1.0

    def n_params(self, comps) -> int:
        return sum(c.size for c in comps) + self.offset_size

    def bic(self, rss: float, comps) -> float:
        k = self.n_params(comps)
        if self.weighted:
            return rss + k * math.log(self.n_eff)
        return self.n_eff * math.log(max(rss, self.rss_floor) / self.n_eff) + k * math.log(self.n_eff)

    def initial_offset(self) -> np.ndarray:
        m = np.sum(self.w**2 * self.y) / np.sum(self.w**2)
        return np.array([m.real, m.imag]) if self.data == "astrometry" else np.array([float(m)])

    def p_bounds(self, f0: float, others=()) -> tuple[float, float]:
        """A component may move by one resolution element 1/T around its periodogram peak, and never closer than
        0.5/T to another component: two unresolved components are degenerate (they trade huge amplitudes)."""
        width = max(1.0 / self.T, 0.01 * f0)
        gap = min((abs(f0 - fk) for fk in others), default=math.inf)
        width = max(min(width, gap - 0.5 / self.T), 0.1 / self.T)
        f_lo = max(f0 - width, 0.5 * f0, 0.5 / self.T)  # periods longer than 2 T would mimic the offset
        f_hi = max(min(f0 + width, 2.0 * f0), f_lo * (1.0 + 1e-6))
        return 1.0 / f_hi, 1.0 / f_lo


@dataclass
class _Option:
    comps: list[_Comp]
    offset: np.ndarray
    rss: float
    bic: float
    text: str


def _fit(ctx: _Ctx, comps: list[_Comp], offset: np.ndarray, free=None) -> tuple[list[_Comp], np.ndarray, float]:
    """Least-squares fit of the components in ``free`` (all by default) plus the offset, others held fixed."""
    t, y, w = ctx.ft, ctx.fy, ctx.fw
    free = list(range(len(comps))) if free is None else sorted(free)
    fixed = [i for i in range(len(comps)) if i not in free]
    target = y.copy()
    for i in fixed:
        target = target - _signal(comps[i].kind, comps[i].params, comps[i].sense, t, ctx.data, ctx.t_ref)
    template = [comps[i] for i in free]
    x0 = np.concatenate([c.params for c in template] + [offset])
    lo, hi = [], []
    for i, c in zip(free, template):
        # Keep each free component at least 0.5/T away from every other one (they all move: re-check each fit).
        f_c = c.frequency
        gap = min((abs(f_c - comps[k].frequency) for k in range(len(comps)) if k != i), default=math.inf)
        half = max(gap - 0.5 / ctx.T, 0.05 / ctx.T)
        p_lo = max(c.p_bounds[0], 1.0 / (f_c + half))
        p_hi = min(c.p_bounds[1], 1.0 / max(f_c - half, 1e-12))
        if p_hi <= p_lo:
            p_lo, p_hi = c.period * (1 - 1e-6), c.period * (1 + 1e-6)
        lo += [p_lo, 0.0]
        hi += [p_hi, ctx.amp_max]
        if c.kind == _KEP:
            lo += [-_HK_MAX, -_HK_MAX]
            hi += [_HK_MAX, _HK_MAX]
        lo.append(-np.inf)
        hi.append(np.inf)
    lo += [-np.inf] * ctx.offset_size
    hi += [np.inf] * ctx.offset_size
    lo, hi = np.array(lo), np.array(hi)
    span = np.where(np.isfinite(hi - lo), hi - lo, 1.0)
    x0 = np.clip(x0, lo + 1e-9 * span, hi - 1e-9 * span)

    def residuals(x):
        model = (complex(x[-2], x[-1]) if ctx.data == "astrometry" else x[-1]) + 0 * target
        k = 0
        for c in template:
            model = model + _signal(c.kind, x[k:k + c.size], c.sense, t, ctx.data, ctx.t_ref)
            k += c.size
        r = (target - model) * w
        return np.concatenate([r.real, r.imag]) if ctx.data == "astrometry" else r

    res = least_squares(residuals, x0, bounds=(lo, hi), x_scale="jac", max_nfev=200 * len(x0))
    out = [c.copy() for c in comps]
    k = 0
    for i in free:
        out[i].params = np.array(res.x[k:k + out[i].size])
        out[i].params[-1] = (out[i].params[-1] + math.pi) % (2.0 * math.pi) - math.pi
        k += out[i].size
    return out, np.array(res.x[-ctx.offset_size:]), float(2.0 * res.cost)


def _option(ctx, comps, offset, text, free=None) -> _Option:
    comps, offset, rss = _fit(ctx, comps, offset, free)
    return _Option(comps, offset, rss, ctx.bic(rss, comps), text)


def _hk(e: float, angle: float) -> tuple[float, float]:
    s = math.sqrt(e)
    return s * math.sin(angle), s * math.cos(angle)


def _best_start(ctx, comps, offset, j, starts, text) -> _Option:
    """Screen starting values for component ``j`` (fitted alone), then polish the best one with everything free."""
    best = None
    for params in starts:
        trial = [c.copy() for c in comps]
        trial[j].params = np.array(params, dtype=float)
        opt = _option(ctx, trial, offset, text, free=[j])
        if best is None or opt.rss < best.rss:
            best = opt
    return _option(ctx, best.comps, best.offset, text)


def _eccentric_starts(P, A, lam, es=(0.15, 0.3, 0.45, 0.6), n_angles=4):
    starts = [[P, A, 0.0, 0.0, lam]]
    for e in es:
        for q in range(n_angles):
            h, k = _hk(e, 2.0 * math.pi * q / n_angles + 0.3)
            starts.append([P, A, h, k, lam])
    return starts


# --- search -----------------------------------------------------------------------------------------------------


@dataclass
class _Candidate:
    frequency: float  # > 0
    sense: int
    amplitude: float
    phase: float
    power: float
    fap: float
    freq: np.ndarray
    spectrum: np.ndarray


def _circular_fit_complex(t, z, w, f, t_ref):
    """z ~ z0 + C exp(2 i pi f (t - t_ref)); returns (z0, C, rss_before, rss_after)."""
    basis = np.column_stack([np.ones(len(t)), np.exp(2j * np.pi * f * (t - t_ref))])
    coef, *_ = np.linalg.lstsq(basis * w[:, None], z * w, rcond=None)
    mean = np.sum(w**2 * z) / np.sum(w**2)
    before = float(np.sum(np.abs(w * (z - mean)) ** 2))
    after = float(np.sum(np.abs(w * (z - basis @ coef)) ** 2))
    return coef[0], coef[1], before, after


def _search(ctx: _Ctx, comps, offset) -> _Candidate | None:
    t = ctx.t
    r = ctx.y - _model(t, comps, offset, ctx.data, ctx.t_ref)
    rv = ctx.data == "rv"
    if ctx.regular and len(t) > 2000:
        spec = spectral.fft_spectrum(t, r, window="hann", pad_factor=4)
        score = spec.amplitude
    elif rv:
        spec = spectral.gls(t, r, dy=ctx.dy, f_min=ctx.f_min, f_max=ctx.f_max, oversample=ctx.st.oversample)
        score = spec.power
    else:
        spec = spectral.complex_periodogram(t, r, dy=ctx.dy, f_min=ctx.f_min, f_max=ctx.f_max,
                                            oversample=ctx.st.oversample)
        score = spec.amplitude
    f = spec.freq
    allowed = (np.abs(f) >= ctx.f_min) & (np.abs(f) <= ctx.f_max)
    for c in comps:  # within 1/T of a known component nothing new can be resolved
        allowed &= np.abs(np.abs(f) - c.frequency) >= 1.0 / ctx.T
    sel = np.nonzero(allowed)[0]
    if len(sel) == 0:
        return None
    k = sel[int(np.argmax(score[sel]))]
    df = float(np.median(np.abs(np.diff(f))))
    w = ctx.w

    if rv:
        def neg(x):
            return -float(spectral.gls(t, r, np.array([abs(x)]), ctx.dy).power[0])
    else:
        rc = r - np.sum(w**2 * r) / np.sum(w**2)

        def neg(x):
            return -float(np.abs(np.sum(w**2 * rc * np.exp(-2j * np.pi * x * (t - ctx.t_ref)))))

    lo, hi = f[k] - df, f[k] + df
    if rv:
        lo = max(lo, 1e-12)
    best = minimize_scalar(neg, bounds=(lo, hi), method="bounded", options={"xatol": 1e-4 * df})
    f_best = float(best.x) if -best.fun >= -neg(f[k]) else float(f[k])
    n = len(t)
    if rv:
        power = float(spectral.gls(t, r, np.array([f_best]), ctx.dy).power[0])
        sine = spectral.fit_sinusoid(t, r, f_best, ctx.dy)
        amp, phase, sense = sine["amplitude"], sine["phase"], 0
        fap = spectral.false_alarm_probability(power, n, ctx.f_max, ctx.T)
    else:
        _, C, before, after = _circular_fit_complex(t, r, w, f_best, ctx.t_ref)
        power = max(0.0, 1.0 - after / before) if before > 0 else 0.0
        single = (1.0 - power) ** ((2 * n - 4) / 2.0)
        fap = float(1.0 - (1.0 - single) ** max(1.0, 2.0 * ctx.f_max * ctx.T))
        amp, phase, sense = float(abs(C)), float(np.angle(C)), (1 if f_best > 0 else -1)
    stride = max(1, len(f) // 3000)
    show = (np.abs(f) <= ctx.f_max)
    return _Candidate(abs(f_best), sense, float(amp), float(phase), power, float(fap),
                      f[show][::stride], spec.amplitude[show][::stride])


# --- relations between frequencies -------------------------------------------------------------------------------


def _relation(ctx: _Ctx, f: float, comps: list[_Comp]):
    """How a candidate frequency relates to the known components (None if unrelated)."""
    tol = 1.0 / ctx.T
    for i, c in enumerate(comps):
        fi = c.frequency
        if abs(f - fi) < 1.5 * tol or (c.is_planet and max(f, fi) / min(f, fi) < CLOSE_RATIO):
            return ("close", i)
    planets = [(i, c) for i, c in enumerate(comps) if c.is_planet]
    for i, c in planets:
        fi = c.frequency
        n = int(round(f / fi))
        # Near-harmonics count too: in a resonant system the signals sit at n f_j shifted by the slow precession
        # frequency (e.g. 3 f_c - 2 f_b = 2 f_c + (f_c - 2 f_b)).
        if 2 <= n <= 4 and abs(f - n * fi) < max(tol, HARMONIC_TOL * n * fi):
            return ("harmonic", i, n)
    # Slow terms of a near-resonant pair: multiples of the resonance offset delta = |q f_in - p f_out|
    # (libration of the resonant angle, precession of the orbits).
    for a_idx in range(len(planets)):
        for b_idx in range(len(planets)):
            if a_idx == b_idx:
                continue
            (i, ci), (j, cj) = planets[a_idx], planets[b_idx]
            if ci.frequency <= cj.frequency:
                continue
            for p_res, q_res in RESONANCES:
                delta = abs(q_res * ci.frequency - p_res * cj.frequency)
                if delta > 0.1 * cj.frequency:
                    continue
                for mult in range(1, 5):
                    if abs(f - mult * delta) < 0.5 * tol:
                        return ("libration", i, j, p_res, q_res, mult)
    known = [c.frequency for c in comps]
    for a_idx in range(len(planets)):
        for b_idx in range(a_idx + 1, len(planets)):
            (i, ci), (j, cj) = planets[a_idx], planets[b_idx]
            for a in range(-3, 4):
                for b in range(-3, 4):
                    if a == 0 or b == 0 or abs(a) + abs(b) > 4:
                        continue
                    fc = abs(a * ci.frequency + b * cj.frequency)
                    # In a 2:1 resonance f_c - f_b = f_b: a combination that falls on a known frequency explains nothing.
                    if fc <= 0 or any(abs(fc - fk) < tol for fk in known):
                        continue
                    if abs(f - fc) < 0.5 * tol:
                        return ("combination", i, j, a, b)
    return None


def _implied_mass_ratio(new: _Comp, ref: _Comp, data: str) -> float:
    """Mass of ``new`` over mass of ``ref`` implied by their amplitudes (same star; e and sin i ignored).

    K ~ m P^(-1/3) for radial velocity, A ~ m P^(2/3) for astrometry: comparing masses rather than amplitudes
    treats both signals alike (an inner planet has a small astrometric but a large radial-velocity signal).
    """
    q = new.period / ref.period
    ratio = new.amplitude / ref.amplitude
    return ratio * q ** (1.0 / 3.0) if data == "rv" else ratio / q ** (2.0 / 3.0)


# --- building blocks of the search loop ---------------------------------------------------------------------------


def _add_component(ctx, comps, offset, cand: _Candidate, kind: str, text: str) -> _Option:
    P0 = 1.0 / cand.frequency
    new = _Comp(kind, np.array([P0, cand.amplitude, cand.phase] if kind != _KEP else
                               [P0, cand.amplitude, 0.0, 0.0, cand.phase]),
                cand.sense if ctx.data == "astrometry" else 1,
                ctx.p_bounds(cand.frequency, [c.frequency for c in comps]))
    trial = [c.copy() for c in comps] + [new]
    j = len(trial) - 1
    if kind == _KEP:
        starts = _eccentric_starts(P0, cand.amplitude, cand.phase, es=(0.3, 0.6), n_angles=4)
    else:
        starts = [list(new.params)]
    return _best_start(ctx, trial, offset, j, starts, text)


def _refit_eccentricity(ctx, comps, offset, j, text) -> _Option:
    c = comps[j]
    return _best_start(ctx, comps, offset, j, _eccentric_starts(c.period, c.amplitude, c.lam), text)


def _sinusoid_at(ctx, comps, offset, f, sense):
    """Amplitude and phase of the residual (fit subset) at frequency f."""
    r = ctx.fy - _model(ctx.ft, comps, offset, ctx.data, ctx.t_ref)
    if ctx.data == "rv":
        fit = spectral.fit_sinusoid(ctx.ft, r, f, None if not ctx.weighted else 1.0 / ctx.fw)
        return fit["amplitude"], fit["phase"]
    _, C, _, _ = _circular_fit_complex(ctx.ft, r, ctx.fw, sense * f, ctx.t_ref)
    return float(abs(C)), float(np.angle(C))


def _split_eccentric(ctx, comps, offset, j, text) -> _Option:
    """Replace eccentric planet j by two circular planets at f_j and 2 f_j (the 2:1 resonance reading)."""
    c = comps[j]
    outer = _Comp(_CIRC, np.array([c.period, c.amplitude, c.lam]), c.sense, c.p_bounds)
    rest = [x.copy() for k, x in enumerate(comps) if k != j]
    first = _option(ctx, rest + [outer], offset, text, free=[len(rest)])
    f2 = 2.0 * c.frequency
    amp, phase = _sinusoid_at(ctx, first.comps, first.offset, f2, c.sense)
    inner = _Comp(_CIRC, np.array([1.0 / f2, max(amp, 1e-12), phase]), c.sense,
                  ctx.p_bounds(f2, [x.frequency for x in first.comps]))
    trial = first.comps + [inner]
    both = _option(ctx, trial, first.offset, text, free=[len(trial) - 2, len(trial) - 1])
    return _option(ctx, both.comps, both.offset, text)


def _merge_pair(ctx, comps, offset, inner, outer, text) -> _Option:
    """Drop the inner planet of a 2:1 pair and let the outer one become eccentric (the single-planet reading)."""
    c = comps[outer]
    kept = [x.copy() for k, x in enumerate(comps) if k != inner]
    j = outer if outer < inner else outer - 1
    kept[j] = _Comp(_KEP, np.array([c.period, c.amplitude, 0.0, 0.0, c.lam]), c.sense, c.p_bounds)
    return _best_start(ctx, kept, offset, j, _eccentric_starts(c.period, c.amplitude, c.lam), text)


# --- ambiguity analysis ---------------------------------------------------------------------------------------------


def _amplitude_uncertainty(ctx: _Ctx, opt: _Option) -> float:
    """1-sigma uncertainty on the amplitude of one sinusoid: rms residual x sqrt(2 / N)."""
    resid = ctx.fy - _model(ctx.ft, opt.comps, opt.offset, ctx.data, ctx.t_ref)
    return float(np.sqrt(np.mean(np.abs(resid) ** 2)) * math.sqrt(2.0 / len(ctx.ft)))


def _fmt_p(P: float) -> str:
    return f"{P:.4g} an" if P >= 1 else f"{P / units.DAY_YR:.4g} j"


def _ambiguities(ctx: _Ctx, opt: _Option) -> tuple[_Option, list[Ambiguity], list[str]]:
    thr = ctx.st.ambiguity_margin
    ambiguities, notes = [], []
    tol_ratio = lambda f: max(1.0 / ctx.T, 0.03 * f)  # noqa: E731

    # (a) a 2:1 pair versus one eccentric planet
    planets = [i for i, c in enumerate(opt.comps) if c.is_planet]
    for i in planets:
        for j in planets:
            ci, cj = opt.comps[i], opt.comps[j]
            if i == j or abs(ci.frequency - 2.0 * cj.frequency) >= tol_ratio(ci.frequency):
                continue
            alt = _merge_pair(ctx, opt.comps, opt.offset, i, j, "")
            d = alt.bic - opt.bic
            e_alt = alt.comps[j if j < i else j - 1].e
            if d < -thr:
                notes.append(f"Le couple 2:1 ({_fmt_p(cj.period)} et {_fmt_p(ci.period)}) est mieux décrit par une "
                             f"seule planète excentrique (e = {e_alt:.2f}, ΔBIC = {-d:.1f}) : modèle simplifié.")
                return _ambiguities(ctx, alt)[0], ambiguities, notes
            if abs(d) < thr:
                ambiguities.append(Ambiguity(
                    f"Couple de planètes en résonance 2:1 ({_fmt_p(cj.period)} et {_fmt_p(ci.period)}) "
                    f"OU une seule planète excentrique de période {_fmt_p(cj.period)} (e ≈ {e_alt:.2f}) : "
                    f"ΔBIC = {d:+.1f}, les données ne permettent pas de trancher.",
                    len(planets) - 1, d))
    # (b) one eccentric planet versus a circular 2:1 pair
    for j in planets:
        c = opt.comps[j]
        if c.kind != _KEP or c.e < 0.1:
            continue
        if any(abs(x.frequency - 2.0 * c.frequency) < max(1.5 / ctx.T, 0.03 * 2.0 * c.frequency)
               for k, x in enumerate(opt.comps) if k != j):
            continue  # 2 f_j is already taken by another component
        alt = _split_eccentric(ctx, opt.comps, opt.offset, j, "")
        # The question only makes sense if the 2f signal is significant: otherwise neither the eccentricity
        # nor an inner planet is measured, and there is nothing to choose between.
        inner_amp = alt.comps[-1].amplitude
        if inner_amp < 4.0 * _amplitude_uncertainty(ctx, opt):
            continue
        d = alt.bic - opt.bic
        if d < -thr:
            notes.append(f"La planète excentrique de période {_fmt_p(c.period)} (e = {c.e:.2f}) est mieux décrite par "
                         f"deux planètes circulaires en résonance 2:1 (ΔBIC = {-d:.1f}) : modèle à deux planètes retenu.")
            return _ambiguities(ctx, alt)[0], ambiguities, notes
        if abs(d) < thr:
            ambiguities.append(Ambiguity(
                f"Une planète excentrique de période {_fmt_p(c.period)} (e = {c.e:.2f}) OU deux planètes circulaires "
                f"en résonance 2:1 ({_fmt_p(c.period)} et {_fmt_p(c.period / 2)}) : ΔBIC = {d:+.1f}, "
                f"les données ne permettent pas de trancher.",
                len(planets) + 1, d))
    return opt, ambiguities, notes


def _demote_weak_harmonics(ctx: _Ctx, opt: _Option, pending: list) -> _Option:
    """Planets sitting at a (near-)harmonic n f_j of another planet j, with an implied mass below
    HARMONIC_MASS_RATIO of planet j, while j has a third planet to interact with, are set aside as interaction
    artefacts (and reported as possible small resonant planets). Applied to the final model, whatever path
    (new component, 2:1 split) produced them."""
    while True:
        planets = [i for i, c in enumerate(opt.comps) if c.is_planet]
        if len(planets) < 3:
            return opt
        candidates = []
        for i in planets:
            ci = opt.comps[i]
            for j in planets:
                cj = opt.comps[j]
                if j == i or ci.frequency <= cj.frequency:
                    continue
                n = int(round(ci.frequency / cj.frequency))
                if 2 <= n <= 4 and abs(ci.frequency - n * cj.frequency) < max(1.0 / ctx.T, HARMONIC_TOL * n * cj.frequency):
                    ratio = _implied_mass_ratio(ci, cj, ctx.data)
                    if ratio < HARMONIC_MASS_RATIO:
                        candidates.append((ratio, i, j, n))
        if not candidates:
            return opt
        # The weakest first: removing it may leave the parent without an interaction partner, which saves the next.
        ratio, i, j, n = min(candidates)
        ci, cj = opt.comps[i], opt.comps[j]
        label = (f"composante non planétaire : harmonique {n}f de la planète à {_fmt_p(cj.period)} "
                 f"(masse impliquée {ratio:.0%} de la sienne), laissée par une orbite qui évolue sous les interactions")
        nuis = _Comp(_NUIS, np.array([ci.period, ci.amplitude, ci.lam]), ci.sense, ci.p_bounds, note=label)
        opt = _option(ctx, [nuis if k == i else c.copy() for k, c in enumerate(opt.comps)], opt.offset, opt.text)
        pending.append((label, ci.period, n, cj.period))


# --- physical parameters ------------------------------------------------------------------------------------------------


def planet_mass(period: float, amplitude: float, e: float, star_mass: float, data: str, G: float = units.G) -> float:
    """Planet mass (Msun) from the reflex amplitude: m sin i from K (m/s), or the true mass from the
    astrometric semi-major axis (AU). Solved iteratively (exact also for massive companions)."""
    if data == "rv":
        k = units.m_s_to_au_per_yr(amplitude) * math.sqrt(1.0 - e * e) * (period / (2.0 * math.pi * G)) ** (1.0 / 3.0)
    else:
        k = amplitude / (G * period**2 / (4.0 * math.pi**2)) ** (1.0 / 3.0)
    m = 0.0
    for _ in range(100):
        m_new = k * (star_mass + m) ** (2.0 / 3.0)
        if abs(m_new - m) <= 1e-15 * max(1.0, m_new):
            break
        m = m_new
    return m_new


def semi_major_axis(period: float, total_mass: float, G: float = units.G) -> float:
    return (G * total_mass * period**2 / (4.0 * math.pi**2)) ** (1.0 / 3.0)


# --- main entry point ------------------------------------------------------------------------------------------------------


def detect(t, y, dy=None, data: str = "rv", star_mass: float | None = None, G: float = units.G,
           settings: DetectionSettings | None = None) -> DetectionResult:
    """Count and characterise the planets in a reflex signal.

    t, y   observation times (yr) and values: radial velocity in m/s (``data='rv'``) or complex
           barycentric position in AU (``data='astrometry'``)
    dy     1-sigma errors (same unit); None or zeros = unknown noise level
    star_mass  Msun, to turn amplitudes into planet masses and semi-major axes (optional)
    """
    st = settings or DetectionSettings()
    if data not in ("rv", "astrometry"):
        raise ValueError("data must be 'rv' or 'astrometry'")
    if len(t) < 10:
        raise ValueError("au moins 10 observations sont nécessaires")
    ctx = _Ctx(t, y, dy, data, st)
    thr = st.bic_threshold

    current = _Option([], ctx.initial_offset(), 0.0, 0.0, "")
    current = _option(ctx, [], current.offset, "")
    steps: list[DetectionStep] = []
    pending: list[tuple] = []  # weak harmonics classified as non-planetary: reported as ambiguities
    stop = "nombre maximal de composantes atteint"
    for index in range(st.max_components):
        cand = _search(ctx, current.comps, current.offset)
        if cand is None:
            stop = "aucune fréquence dans l'intervalle de recherche"
            break
        step = DetectionStep(index + 1, 1.0 / cand.frequency, cand.amplitude, cand.power, cand.fap, None, "",
                             cand.freq, cand.spectrum)
        steps.append(step)
        planets = [c for c in current.comps if c.is_planet]
        if cand.fap > st.fap_threshold:
            step.decision = stop = f"arrêt : pic non significatif (FAP = {cand.fap:.2g} > {st.fap_threshold:g})"
            break
        if planets and cand.amplitude < st.min_amplitude_ratio * max(c.amplitude for c in planets):
            step.decision = stop = (f"arrêt : pic sous le plancher d'amplitude ({st.min_amplitude_ratio:g} × la planète "
                                    f"la plus forte)")
            break

        relation = _relation(ctx, cand.frequency, current.comps)
        options: list[_Option] = []
        new_kind = _KEP
        label = f"planète de période {_fmt_p(1.0 / cand.frequency)}"
        if relation is not None and relation[0] == "harmonic":
            _, j, n = relation
            cj = current.comps[j]
            if cj.kind == _KEP:
                options.append(_refit_eccentricity(ctx, current.comps, current.offset, j,
                                                   f"harmonique {n}f de la planète à {_fmt_p(cj.period)} : "
                                                   f"son excentricité est réajustée"))
                if n == 2:
                    options.append(_split_eccentric(ctx, current.comps, current.offset, j,
                                                    f"la planète à {_fmt_p(cj.period)} est en fait un couple "
                                                    f"résonant 2:1 ({_fmt_p(cj.period)} et {_fmt_p(cj.period / 2)})"))
            label += f" (à {n}f de la planète à {_fmt_p(cj.period)} : résonance possible)"
        elif relation is not None and relation[0] == "combination":
            _, i, j, a, b = relation
            new_kind = _NUIS
            label = (f"composante non planétaire : combinaison {a:+d}·f({_fmt_p(current.comps[i].period)}) "
                     f"{b:+d}·f({_fmt_p(current.comps[j].period)}) (interaction entre planètes)")
        elif relation is not None and relation[0] == "close":
            new_kind = _NUIS
            near = current.comps[relation[1]]
            label = (f"composante non planétaire : trop proche de la {'planète' if near.is_planet else 'composante'} à "
                     f"{_fmt_p(near.period)} (modulation ou précession de son orbite)")
        elif relation is not None and relation[0] == "libration":
            _, i, j, p_res, q_res, mult = relation
            new_kind = _NUIS
            label = (f"composante non planétaire : {mult if mult > 1 else ''}{'×' if mult > 1 else ''}fréquence lente du "
                     f"couple proche de la résonance {p_res}:{q_res} ({_fmt_p(current.comps[j].period)} / "
                     f"{_fmt_p(current.comps[i].period)}) : libération ou précession des orbites")
        if new_kind == _KEP and len(planets) >= st.max_planets:
            step.decision = stop = f"arrêt : nombre maximal de planètes ({st.max_planets}) atteint"
            break
        planet_option = _add_component(ctx, current.comps, current.offset, cand, new_kind, label)
        if new_kind == _KEP and relation is not None and relation[0] == "harmonic":
            _, j, n = relation
            cj = current.comps[j]
            ratio = _implied_mass_ratio(planet_option.comps[-1], cj, data)
            partners = [c for c in planets if c is not cj]  # an interaction artefact needs a second planet
            if ratio < HARMONIC_MASS_RATIO and partners:
                # A weak signal at n f_j is what an eccentric orbit that changes under planet-planet interactions
                # leaves after a fixed Keplerian fit. It could also be a small planet in n:1 resonance: say so.
                label = (f"composante non planétaire : harmonique {n}f de la planète à {_fmt_p(cj.period)} "
                         f"(masse impliquée {ratio:.0%} de la sienne), laissée par une orbite qui évolue sous les "
                         f"interactions")
                planet_option = _add_component(ctx, current.comps, current.offset, cand, _NUIS, label)
                pending.append((label, 1.0 / cand.frequency, n, cj.period))
        if new_kind == _KEP and 1.0 / cand.frequency > ctx.T:
            label = (f"composante non planétaire : période de {_fmt_p(1.0 / cand.frequency)}, plus longue que la durée "
                     f"d'observation ({_fmt_p(ctx.T)}) : tendance à long terme, planète non confirmable")
            planet_option = _add_component(ctx, current.comps, current.offset, cand, _NUIS, label)
        options.append(planet_option)

        best = min(options, key=lambda o: o.bic)
        gain = current.bic - best.bic
        step.delta_bic = gain
        if gain < thr:
            step.decision = stop = f"arrêt : gain de BIC insuffisant ({gain:.1f} < {thr:g})"
            break
        if best.text == label:  # the candidate itself was added (last component)
            best.comps[-1].fap, best.comps[-1].delta_bic, best.comps[-1].note = cand.fap, gain, label
        step.decision = f"retenu : {best.text} (ΔBIC = {gain:.1f})"
        current = best

    final, ambiguities, notes = _ambiguities(ctx, current)
    final = _demote_weak_harmonics(ctx, final, pending)
    n_planets = sum(1 for c in final.comps if c.is_planet)
    grouped: dict[tuple[int, int], list[float]] = {}
    final_planets = [c for c in final.comps if c.is_planet]
    for _label, period, n, parent in pending:
        if not final_planets or not any(not c.is_planet and abs(c.period - period) < 0.05 * period for c in final.comps):
            continue
        k = min(range(len(final_planets)), key=lambda q: abs(final_planets[q].period - parent))
        grouped.setdefault((n, k), []).append(period)
    for (n, k), periods in grouped.items():
        parent = final_planets[k].period
        listed = ", ".join(_fmt_p(p) for p in sorted(periods))
        ambiguities.append(Ambiguity(
            f"{'Signaux faibles' if len(periods) > 1 else 'Signal faible'} à {listed}, près de "
            f"l'harmonique {n}f de la planète à {_fmt_p(parent)} : compté{'s' if len(periods) > 1 else ''} comme non "
            f"planétaire{'s' if len(periods) > 1 else ''} (orbite qui évolue sous les interactions), mais ce pourrait être "
            f"une petite planète en résonance {n}:1.", n_planets + 1, float("nan")))
    resid = ctx.y - _model(ctx.t, final.comps, final.offset, data, ctx.t_ref)
    rms = float(np.sqrt(np.mean(np.abs(resid) ** 2)))

    planets_out, others = [], []
    for c in sorted(final.comps, key=lambda x: x.period):
        if not c.is_planet:
            others.append(OtherComponent(c.period, c.amplitude, c.note))
            continue
        mass = a = None
        if star_mass is not None and star_mass > 0:
            mass = planet_mass(c.period, c.amplitude, c.e, star_mass, data, G)
            a = semi_major_axis(c.period, star_mass + mass, G)
        planets_out.append(DetectedPlanet(c.period, c.amplitude, c.e, c.angle, c.lam,
                                          c.sense if data == "astrometry" else 0, mass, a, c.fap, c.delta_bic,
                                          c.note))
    if notes:
        stop = stop + " · " + " · ".join(notes)
    return DetectionResult(data, planets_out, others, ambiguities, steps, stop, len(ctx.t), ctx.T, rms, st,
                           ctx.t_ref, final.comps, final.offset)


def detect_observations(obs, star_mass: float | None = None, settings: DetectionSettings | None = None,
                        G: float = units.G) -> DetectionResult:
    """``detect`` applied to ``observer.Observations``."""
    dy = obs.error if np.any(obs.error > 0) else None
    return detect(obs.t, obs.value, dy, obs.kind, star_mass, G, settings)


# --- scoring against the truth (never used by the detection itself) -----------------------------------------------------


@dataclass
class MatchReport:
    matches: list[tuple[int, int]]  # (detected index, true index)
    missed: list[int]  # true planets not found
    spurious: list[int]  # detections matching no true planet

    @property
    def exact_count(self) -> bool:
        return not self.missed and not self.spurious


def match_truth(planets, truths, baseline: float) -> MatchReport:
    """Pair detections with true planets by frequency (|Δf| <= max(1/T, 3 % of f)), closest first."""
    pairs = []
    for i, p in enumerate(planets):
        for j, tr in enumerate(truths):
            df = abs(p.frequency - tr.frequency)
            if df <= max(1.0 / baseline, 0.03 * tr.frequency):
                pairs.append((df / tr.frequency, i, j))
    used_d, used_t, matches = set(), set(), []
    for _, i, j in sorted(pairs):
        if i not in used_d and j not in used_t:
            matches.append((i, j))
            used_d.add(i)
            used_t.add(j)
    return MatchReport(sorted(matches, key=lambda m: m[1]), [j for j in range(len(truths)) if j not in used_t],
                       [i for i in range(len(planets)) if i not in used_d])

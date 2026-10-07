"""From a simulated trajectory to a spectrum: observation settings in, labelled peaks out.

This is the headless core of the interface's "Spectre" tab, also usable from scripts and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.trajectory import Trajectory
from . import observer, orbits, spectral


SPECTROGRAM_REACH = 2.5  # highest frequency of the spectrogram, in units of the fastest planet's frequency
HARMONIC_REACH = 6.0  # highest harmonic of the fastest planet kept in the spectrum (matches label_peaks)


@dataclass
class ObservationSettings:
    """What to observe and how.

    signal          'rv' (radial velocity, m/s) or 'astrometry' (x + iy, AU)
    sampling        'regular' (windowed FFT) or 'irregular' (Lomb-Scargle / complex periodogram)
    sigma           white noise, in m/s for 'rv', in AU for 'astrometry'
    t_start, t_end  observation interval in years (None = start / end of the trajectory)
    dt              regular sampling step (yr); n_obs / season_fraction for irregular campaigns
    spectrogram_window  sliding window length in years (None = no spectrogram)
    """

    body: str
    signal: str = "rv"
    line_of_sight_deg: float = 0.0
    inclination_deg: float = 90.0
    t_start: float | None = None
    t_end: float | None = None
    sampling: str = "regular"
    dt: float | None = None
    n_obs: int = 150
    season_fraction: float = 0.0
    seed: int = 1
    sigma: float = 0.0
    window: str | None = "hann"
    oversample: float = 10.0
    peak_threshold: float = 0.02  # fraction of the highest peak
    max_peaks: int = 10
    spectrogram_window: float | None = None


@dataclass
class SpectrumResult:
    settings: ObservationSettings
    obs: observer.Observations
    spectrum: spectral.Spectrum
    peaks: list[spectral.Peak]
    labels: list[str]
    fap: list[float | None]
    truths: list[orbits.ReflexSignature]
    f_max: float
    clean_t: np.ndarray  # noise-free signal at the trajectory samples, decimated
    clean: np.ndarray
    notes: list[str] = field(default_factory=list)
    spectrogram: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None

    @property
    def windowed(self) -> bool:
        return self.spectrum.method.startswith("fft")


def suggest(traj: Trajectory, body) -> dict:
    """Sensible observation parameters from the companions of ``body`` (initial two-body elements)."""
    truths = orbits.reflex_signatures(traj, body)
    spacing = float(np.median(np.diff(traj.t))) if len(traj) > 1 else 0.0
    out = {"truths": truths, "spacing": spacing, "p_min": None, "p_max": None, "dt": None, "duration": None}
    if truths:
        p_min, p_max = truths[0].period, truths[-1].period
        out.update(p_min=p_min, p_max=p_max, dt=max(p_min / 50.0, spacing), duration=6.0 * p_max)
    return out


def default_start(traj: Trajectory) -> float:
    """First stored sample strictly after the last impulse.

    Observations cannot straddle a velocity jump, and the sample taken at an impulse time holds the state
    *before* it, so the earliest valid start is the next sample.
    """
    if not traj.impulses:
        return float(traj.t[0])
    last = max(e.t for e in traj.impulses)
    k = int(np.searchsorted(traj.t, last, side="right"))
    return float(traj.t[min(k, len(traj) - 1)])


def _masked(spec: spectral.Spectrum, f_max: float) -> spectral.Spectrum:
    keep = np.abs(spec.freq) <= f_max
    return spectral.Spectrum(spec.freq[keep], spec.amplitude[keep], spec.power[keep], spec.method, spec.n_points,
                             spec.baseline, spec.evaluator)


def run_observation(traj: Trajectory, st: ObservationSettings) -> SpectrumResult:
    """Observe ``st.body``, compute the spectrum, find and label its peaks. Raises ValueError with a readable message."""
    if len(traj) < 20:
        raise ValueError("trajectoire trop courte : simulez d'abord plus longtemps")
    k = traj.index(st.body)
    if traj.fixed[k]:
        raise ValueError(f"{traj.names[k]} est fixe : il n'a pas de mouvement réflexe à observer")
    if traj.masses.sum() <= 0:
        raise ValueError("masse totale nulle")
    t0 = max(traj.t[0] if st.t_start is None else st.t_start, traj.t[0])
    t1 = min(traj.t[-1] if st.t_end is None else st.t_end, traj.t[-1])
    if t1 - t0 <= 0:
        raise ValueError("intervalle d'observation vide")
    for ev in traj.impulses:
        if t0 < ev.t < t1:
            raise ValueError(f"une poussée a lieu à t = {ev.t:.5g} an dans l'intervalle : "
                             f"commencer l'observation après cet instant")

    geometry = observer.Observer(st.line_of_sight_deg, st.inclination_deg)
    sug = suggest(traj, k)
    truths = orbits.reflex_signatures(traj, k, geometry.sin_i)
    notes = []

    if st.sampling == "regular":
        dt = st.dt or sug["dt"] or float(np.median(np.diff(traj.t)))
        times = observer.regular_schedule(t0, t1, dt)
    elif st.sampling == "irregular":
        times = observer.random_schedule(t0, t1, st.n_obs, rng=st.seed, season_fraction=st.season_fraction)
    else:
        raise ValueError("échantillonnage inconnu : 'regular' ou 'irregular'")
    if len(times) < 16:
        raise ValueError(f"seulement {len(times)} observations : allongez l'intervalle ou réduisez le pas")

    if st.signal == "rv":
        obs = observer.observe_rv(traj, k, times, geometry, sigma=st.sigma, rng=st.seed + 1)
    elif st.signal == "astrometry":
        obs = observer.observe_astrometry(traj, k, times, sigma=st.sigma, rng=st.seed + 1)
    else:
        raise ValueError("signal inconnu : 'rv' ou 'astrometry'")

    median_dt = float(np.median(np.diff(times)))
    f_nyquist = 0.5 / median_dt
    # Up to the 6th harmonic of the fastest companion (an eccentric orbit radiates well above its fundamental).
    f_max = min(f_nyquist, HARMONIC_REACH / sug["p_min"]) if sug["p_min"] else f_nyquist
    sigma_given = st.sigma > 0

    if st.sampling == "regular":
        spec = spectral.fft_spectrum(obs.t, obs.value, window=st.window or None)
    else:
        oversample = st.oversample
        n_freq = max(f_max * obs.baseline * oversample, 1.0)
        n_freq *= 2 if st.signal == "astrometry" else 1
        oversample *= min(1.0, 6e7 / (n_freq * len(times)))  # keep the computation affordable
        dy = obs.error if sigma_given else None
        if st.signal == "rv":
            spec = spectral.gls(obs.t, obs.value, dy=dy, f_max=f_max, oversample=max(oversample, 2.0))
        else:
            spec = spectral.complex_periodogram(obs.t, obs.value, dy=dy, f_max=f_max, oversample=max(oversample, 2.0))
    spec = _masked(spec, f_max)

    floor = st.peak_threshold * float(spec.amplitude.max())
    peaks = spec.peaks(st.max_peaks, min_amplitude=floor)
    windowed = spec.method.startswith("fft")
    labels = spectral.label_peaks(peaks, truths, obs.baseline, windowed)
    fap = [spectral.false_alarm_probability(pk.power, spec.n_points, f_max, obs.baseline) if spec.method == "gls"
           else None for pk in peaks]

    # Noise-free reference signal at the stored samples (decimated for display).
    sel = (traj.t >= t0) & (traj.t <= t1)
    stride = max(1, int(sel.sum()) // 3000)
    clean_t = traj.t[sel][::stride]
    if st.signal == "rv":
        clean = observer.radial_velocity(traj, k, geometry)[sel][::stride]
    else:
        clean = observer.astrometric_signal(traj, k)[sel][::stride]

    # Advice.
    if sug["p_max"] and obs.baseline < 3.0 * sug["p_max"]:
        notes.append(f"Durée courte : {obs.baseline:.4g} an = {obs.baseline / sug['p_max']:.2g} période de la planète "
                     f"la plus lente (au moins 3 conseillées, 6 pour séparer les pics proches).")
    if sug["p_min"] and median_dt > sug["p_min"] / 10.0:
        notes.append(f"Pas d'observation grossier : {median_dt:.3g} an pour une période de {sug['p_min']:.3g} an "
                     f"(au plus P_min / 10 conseillé).")
    if traj.impulses:
        notes.append("Des poussées ont eu lieu : les planètes « vraies » affichées sont celles des conditions initiales.")
    if traj.fixed.any():
        notes.append("Un corps fixe est présent : la quantité de mouvement n'est pas conservée et le mouvement réflexe "
                     "mesuré par rapport au barycentre n'est pas physique.")
    if not truths:
        notes.append(f"Aucun compagnon lié à {traj.names[k]} : pas de référence pour étiqueter les pics.")
    if st.signal == "rv" and geometry.sin_i < 1e-6:
        notes.append("Inclinaison nulle (vue de face) : la vitesse radiale est nulle ; utilisez l'astrométrie.")

    result = SpectrumResult(st, obs, spec, peaks, labels, fap, truths, f_max, clean_t, np.asarray(clean), notes)

    if st.spectrogram_window:
        win = min(st.spectrogram_window, obs.baseline / 1.5)
        # Fundamentals and second harmonics are what the spectrogram is for: do not stretch the axis to 6f.
        f_view = min(f_max, SPECTROGRAM_REACH / sug["p_min"]) if sug["p_min"] else f_max
        pos = spectral.frequency_grid(obs.t[obs.t <= obs.t[0] + win], f_max=f_view, oversample=3.0)
        freq = np.concatenate([-pos[::-1], pos]) if st.signal == "astrometry" else pos
        result.spectrogram = spectral.spectrogram(obs.t, obs.value, win, step=win / 4.0, freq=freq)
    return result

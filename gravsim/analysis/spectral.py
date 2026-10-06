"""Spectral analysis of time series: FFT, generalised Lomb-Scargle, complex periodogram, spectrogram.

Frequencies are in cycles per year. Amplitudes are calibrated so that a pure
sinusoid of semi-amplitude K (or a circular motion z = A exp(2 i pi f t))
produces a peak of height K (or A).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.signal import find_peaks, get_window

_CHUNK_ELEMENTS = 4_000_000  # frequencies x samples evaluated at once


@dataclass
class Peak:
    frequency: float
    amplitude: float
    power: float

    @property
    def period(self) -> float:
        return 1.0 / abs(self.frequency) if self.frequency else float("inf")


@dataclass
class Spectrum:
    freq: np.ndarray  # cycles/yr; two-sided (negative = clockwise) for complex signals
    amplitude: np.ndarray  # semi-amplitude of the best-fitting sinusoid / circular motion
    power: np.ndarray  # normalised power in [0, 1] (GLS) or amplitude^2 (FFT)
    method: str
    n_points: int
    baseline: float
    # Exact evaluation at any frequency, f -> (amplitude, power), used to refine peaks.
    evaluator: Callable[[float], tuple[float, float]] | None = field(default=None, repr=False)

    @property
    def resolution(self) -> float:
        """Smallest separable frequency difference, ~ 1 / T."""
        return 1.0 / self.baseline

    def peaks(self, n: int = 10, min_separation: float | None = None, min_amplitude: float = 0.0) -> list[Peak]:
        """The ``n`` highest local maxima, at least ``min_separation`` apart (default 1/T)."""
        sep = self.resolution if min_separation is None else min_separation
        df = float(np.median(np.diff(self.freq)))
        idx, _ = find_peaks(self.amplitude, distance=max(1, int(round(sep / df))))
        idx = idx[self.amplitude[idx] >= min_amplitude]
        idx = idx[np.argsort(self.amplitude[idx])[::-1][:n]]
        out = []
        for k in idx:
            f, amp, pw = self.freq[k], self.amplitude[k], self.power[k]
            if self.evaluator is not None and 0 < k < len(self.freq) - 1:
                # Exact maximum of the *power* (the fitted amplitude alone can peak slightly off
                # the true frequency with irregular sampling).
                lo, hi = self.freq[k - 1], self.freq[k + 1]
                res = minimize_scalar(lambda x: -self.evaluator(x)[1], bounds=(lo, hi), method="bounded",
                                      options={"xatol": 1e-6 * (hi - lo)})
                if -res.fun >= pw:
                    f = res.x
                    amp, pw = self.evaluator(f)
            elif 0 < k < len(self.freq) - 1:  # parabolic refinement of the maximum
                y0, y1, y2 = self.amplitude[k - 1:k + 2]
                denom = y0 - 2 * y1 + y2
                if denom < 0:
                    delta = 0.5 * (y0 - y2) / denom
                    f = f + delta * (self.freq[k + 1] - self.freq[k])
                    amp = y1 - 0.25 * (y0 - y2) * delta
            out.append(Peak(float(f), float(amp), float(pw)))
        return out


def frequency_grid(t, f_min: float | None = None, f_max: float | None = None, oversample: float = 10.0) -> np.ndarray:
    """Uniform grid from ~1/T up to the (pseudo-)Nyquist frequency 1 / (2 median dt)."""
    t = np.asarray(t, dtype=float)
    T = float(t[-1] - t[0])
    df = 1.0 / (oversample * T)
    f_min = df if f_min is None else max(f_min, df)
    f_max = 0.5 / float(np.median(np.diff(t))) if f_max is None else f_max
    return np.arange(f_min, f_max + 0.5 * df, df)


def gls(t, y, freq=None, dy=None, **grid) -> Spectrum:
    """Generalised Lomb-Scargle periodogram (Zechmeister & Kürster 2009) with a floating mean.

    Works for irregular sampling and per-point errors ``dy``.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    freq = frequency_grid(t, **grid) if freq is None else np.asarray(freq, dtype=float)
    w = np.ones_like(t) if dy is None or np.all(np.asarray(dy) == 0) else 1.0 / np.asarray(dy, dtype=float) ** 2
    w = w / w.sum()
    t0 = t - t[0]
    Y = w @ y
    YY = w @ (y * y) - Y * Y
    power = np.empty(len(freq))
    amp = np.empty(len(freq))
    chunk = max(1, _CHUNK_ELEMENTS // len(t))
    for k in range(0, len(freq), chunk):
        arg = 2 * np.pi * np.outer(freq[k:k + chunk], t0)
        c, s = np.cos(arg), np.sin(arg)
        C, S = c @ w, s @ w
        YC = (c * y) @ w - Y * C
        YS = (s * y) @ w - Y * S
        CC = (c * c) @ w - C * C
        SS = (s * s) @ w - S * S
        CS = (c * s) @ w - C * S
        D = CC * SS - CS * CS
        power[k:k + chunk] = (SS * YC**2 + CC * YS**2 - 2 * CS * YC * YS) / (YY * D)
        a = (YC * SS - YS * CS) / D
        b = (YS * CC - YC * CS) / D
        amp[k:k + chunk] = np.hypot(a, b)
    def evaluator(f):
        one = gls(t, y, np.array([f]), dy)
        return float(one.amplitude[0]), float(one.power[0])

    return Spectrum(freq, amp, power, "gls", len(t), float(t[-1] - t[0]), evaluator)


def complex_periodogram(t, z, freq=None, dy=None, **grid) -> Spectrum:
    """Two-sided periodogram of a complex signal (e.g. astrometry z = x + i y), irregular sampling allowed.

    Amplitude at f: |sum w (z - <z>) exp(-2 i pi f t)| / sum w. Positive frequencies are
    counterclockwise motions, negative ones clockwise.
    """
    t = np.asarray(t, dtype=float)
    z = np.asarray(z, dtype=complex)
    if freq is None:
        pos = frequency_grid(t, **grid)
        freq = np.concatenate([-pos[::-1], pos])
    freq = np.asarray(freq, dtype=float)
    w = np.ones_like(t) if dy is None or np.all(np.asarray(dy) == 0) else 1.0 / np.asarray(dy, dtype=float) ** 2
    w = w / w.sum()
    zc = z - w @ z
    t0 = t - t[0]
    amp = np.empty(len(freq))
    chunk = max(1, _CHUNK_ELEMENTS // len(t))
    for k in range(0, len(freq), chunk):
        amp[k:k + chunk] = np.abs(np.exp(-2j * np.pi * np.outer(freq[k:k + chunk], t0)) @ (w * zc))
    def evaluator(f):
        a = float(np.abs(np.exp(-2j * np.pi * f * t0) @ (w * zc)))
        return a, a * a

    return Spectrum(freq, amp, amp**2, "complex", len(t), float(t[-1] - t[0]), evaluator)


def fft_spectrum(t, y, window: str = "hann", pad_factor: int = 8) -> Spectrum:
    """Windowed, zero-padded FFT for regularly sampled real or complex signals."""
    t = np.asarray(t, dtype=float)
    dt = np.diff(t)
    if np.max(np.abs(dt - dt.mean())) > 1e-6 * dt.mean():
        raise ValueError("fft_spectrum needs regular sampling; use gls or complex_periodogram")
    n = len(t)
    win = get_window(window, n, fftbins=False) if window else np.ones(n)
    nfft = int(2 ** np.ceil(np.log2(n * pad_factor)))
    y = np.asarray(y)
    yc = (y - y.mean()) * win
    if np.iscomplexobj(y):
        spec = np.fft.fftshift(np.fft.fft(yc, nfft))
        freq = np.fft.fftshift(np.fft.fftfreq(nfft, dt.mean()))
        amp = np.abs(spec) / win.sum()
    else:
        spec = np.fft.rfft(yc, nfft)
        freq = np.fft.rfftfreq(nfft, dt.mean())
        amp = 2.0 * np.abs(spec) / win.sum()
        freq, amp = freq[1:], amp[1:]  # drop the mean
    return Spectrum(freq, amp, amp**2, f"fft-{window or 'rect'}", n, float(t[-1] - t[0]))


def spectrogram(t, y, window_length: float, step: float | None = None, freq=None, **grid):
    """Sliding-window GLS amplitude: returns (window centres, freq, amplitude[n_windows, n_freq]).

    Shows how peak frequencies drift when planets interact.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y)
    step = window_length / 4 if step is None else step
    if freq is None:
        freq = frequency_grid(t[t <= t[0] + window_length], **grid)
    centres, rows = [], []
    start = t[0]
    while start + window_length <= t[-1] + 1e-12:
        sel = (t >= start) & (t <= start + window_length)
        if sel.sum() > 5:
            spec = complex_periodogram(t[sel], y[sel], freq) if np.iscomplexobj(y) else gls(t[sel], y[sel], freq)
            rows.append(spec.amplitude)
            centres.append(start + 0.5 * window_length)
        start += step
    return np.array(centres), np.asarray(freq), np.array(rows)


def false_alarm_probability(power: float, n_points: int, f_max: float, baseline: float) -> float:
    """Approximate FAP of a GLS peak of normalised ``power``.

    Uses P(single frequency) = (1 - p)^((N - 3) / 2) and M ~ f_max * T independent
    frequencies. Rough but monotonic; a Monte-Carlo estimate is planned for detection.
    """
    single = (1.0 - power) ** ((n_points - 3) / 2.0)
    m = max(1.0, f_max * baseline)
    return float(1.0 - (1.0 - single) ** m)


def fit_sinusoid(t, y, frequency: float, dy=None) -> dict:
    """Least-squares y = offset + a cos(2 pi f t) + b sin(2 pi f t). Returns amplitude, phase, offset, model."""
    t = np.asarray(t, dtype=float)
    arg = 2 * np.pi * frequency * (t - t[0])
    A = np.column_stack([np.ones_like(t), np.cos(arg), np.sin(arg)])
    w = np.ones_like(t) if dy is None else 1.0 / np.asarray(dy, dtype=float)
    coef, *_ = np.linalg.lstsq(A * w[:, None], np.asarray(y) * w, rcond=None)
    return {"offset": coef[0], "amplitude": float(np.hypot(coef[1], coef[2])),
            "phase": float(np.arctan2(-coef[2], coef[1])), "model": A @ coef}

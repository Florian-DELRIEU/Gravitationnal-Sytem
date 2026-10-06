"""Étude spectrale du mouvement d'une étoile, sans interface.

Simule un preset, observe l'étoile (vitesse radiale et astrométrie), calcule les
spectres et compare les pics trouvés aux planètes réellement présentes.

Exemples :
    python scripts/etude_spectre.py soleil_jupiter
    python scripts/etude_spectre.py systeme_solaire --annees 500
    python scripts/etude_spectre.py resonance_2_1 --bruit 3 --n-obs 200 --saison 0.3
    python scripts/etude_spectre.py --tous
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from gravsim.analysis import diagnostics, frames, observer, orbits, spectral  # noqa: E402
from gravsim.core.scenario import load_preset  # noqa: E402
from gravsim.core.simulation import Simulation  # noqa: E402

DEFAULT_SET = ["soleil_jupiter", "jupiter_chaud", "resonance_2_1", "excentrique", "systeme_solaire"]


def label_peaks(peaks, truths, baseline: float, windowed: bool) -> list[str]:
    """Name each peak: planet, harmonic, window side lobe, yearly alias, or unknown.

    The matching tolerance is 0.75 / T (below the resolution 1 / T). Side lobes of the
    Hann window lie within ~3.5 / T of a much stronger peak; with seasonal gaps the
    spectral window also creates aliases at +-1 and +-2 cycles/yr.
    """
    tol = 0.75 / baseline
    labels = []
    for pk in peaks:
        f = abs(pk.frequency)
        matches = []
        for tr in truths:
            for n in range(1, 7):
                if abs(f - n * tr.frequency) < tol:
                    matches.append(tr.name if n == 1 else f"harmonique {n}f de {tr.name}")
        if len(matches) > 1:
            label = " / ".join(matches) + "  (AMBIGU)"
        else:
            label = matches[0] if matches else "?"
        if label == "?":
            for big in peaks:
                ratio = pk.amplitude / big.amplitude
                df = abs(f - abs(big.frequency))
                if windowed and ratio < 0.05 and df < 3.5 / baseline:
                    label = "lobe secondaire de la fenêtre"
                    break
                if ratio < 0.8 and min(abs(df - 1.0), abs(df - 2.0)) < tol:
                    label = "alias annuel (trous saisonniers)"
                    break
        labels.append(label)
    return labels


def study(preset: str, years: float | None, star: str | None, integrator: str, sampling: float | None,
          sigma: float, n_obs: int, season: float, los: float, incl: float, out_dir: Path, seed: int) -> Path:
    sc = load_preset(preset)
    star = star or max(sc.bodies, key=lambda b: b.mass).name

    # Ground truth from the initial conditions, to size the run.
    probe = Simulation(sc, integrator)
    truths = orbits.reflex_signatures(probe.trajectory, star, observer.Observer(los, incl).sin_i)
    if not truths:
        raise SystemExit(f"{preset}: aucun compagnon lié à {star}")
    p_min, p_max = truths[0].period, truths[-1].period
    years = years or 6.0 * p_max
    sampling = sampling or p_min / 50.0

    print(f"\n=== {sc.name} — étoile : {star} — {years:.4g} ans, intégrateur {integrator} ===")
    t0 = time.perf_counter()
    sim = Simulation(sc, integrator, output_dt=sampling)
    sim.run(years)
    traj = sim.trajectory
    print(f"simulation : {len(traj)} échantillons en {time.perf_counter() - t0:.1f} s")

    obs_ = observer.Observer(los, incl)
    fid = diagnostics.fidelity(traj).summary()

    # Observations: full regular sampling, or a realistic irregular campaign.
    if n_obs > 0:
        times = observer.random_schedule(traj.t[0], traj.t[-1], n_obs, rng=seed, season_fraction=season)
        rv = observer.observe_rv(traj, star, times, obs_, sigma=sigma, rng=seed + 1)
        astro = observer.observe_astrometry(traj, star, times)
        f_max = 1.5 / p_min
        spec_rv = spectral.gls(rv.t, rv.value, dy=rv.error if sigma > 0 else None, f_max=f_max)
        spec_z = spectral.complex_periodogram(astro.t, astro.value, f_max=f_max)
    else:
        rv = observer.observe_rv(traj, star, traj.t, obs_, sigma=sigma, rng=seed + 1)
        astro = observer.Observations(traj.t, observer.astrometric_signal(traj, star), np.zeros(len(traj)),
                                      "astrometry", star)
        spec_rv = spectral.fft_spectrum(rv.t, rv.value)
        spec_z = spectral.fft_spectrum(astro.t, astro.value)

    print(f"{'planète':14s} {'P (j)':>10s} {'P (ans)':>9s} {'e':>6s} {'K (m/s)':>9s} {'astro (UA)':>11s}")
    for tr in truths:
        print(f"{tr.name:14s} {tr.period * 365.25:10.2f} {tr.period:9.4f} {tr.e:6.3f} "
              f"{tr.rv_semi_amplitude:9.3f} {tr.astrometric_amplitude:11.3e}")
    print(f"pics vitesse radiale ({spec_rv.method}) :")
    windowed = spec_rv.method.startswith("fft")
    peaks_rv = spec_rv.peaks(8, min_amplitude=0.02 * spec_rv.amplitude.max())
    for pk, lab in zip(peaks_rv, label_peaks(peaks_rv, truths, years, windowed)):
        print(f"   P = {pk.period:10.4f} ans  K = {pk.amplitude:8.3f} m/s  -> {lab}")
    print(f"pics astrométrie ({spec_z.method}) :")
    peaks_z = spec_z.peaks(8, min_amplitude=0.02 * spec_z.amplitude.max())
    for pk, lab in zip(peaks_z, label_peaks(peaks_z, truths, years, windowed)):
        sens = "direct" if pk.frequency > 0 else "rétrograde"
        print(f"   P = {pk.period:10.4f} ans  A = {pk.amplitude:9.3e} UA ({sens}) -> {lab}")
    print(f"fidélité : dérive d'énergie max {fid['energy']:.1e}")

    # --- figure ---------------------------------------------------------------------
    fig, ax = plt.subplots(2, 3, figsize=(17, 9.5))
    fig.suptitle(f"{sc.name} — {years:.4g} ans — visée {los:g}°, inclinaison {incl:g}°"
                 + (f", bruit {sigma:g} m/s, {n_obs} obs." if n_obs or sigma else ""), fontsize=13)
    bc = frames.barycentric(traj)
    step = max(1, len(traj) // 20000)
    colors = plt.cm.tab10(np.arange(traj.n_bodies) % 10)
    k_star = traj.index(star)

    a = ax[0, 0]
    for k, name in enumerate(traj.names):
        a.plot(bc.pos[::step, k, 0], bc.pos[::step, k, 1], lw=0.6, color=colors[k], label=name)
    a.set_aspect("equal"), a.set_title("Orbites (référentiel barycentrique)"), a.set_xlabel("x (UA)")
    a.set_ylabel("y (UA)"), a.legend(fontsize=7, loc="upper right")

    a = ax[0, 1]
    a.plot(bc.pos[::step, k_star, 0], bc.pos[::step, k_star, 1], lw=0.6, color=colors[k_star])
    r_star = traj.radii[k_star]
    if r_star > 0:
        a.add_patch(plt.Circle((0, 0), r_star, fill=False, ls="--", color="grey", label="rayon de l'étoile"))
        a.legend(fontsize=8)
    a.set_aspect("equal"), a.set_title(f"Mouvement réflexe de {star}"), a.set_xlabel("x (UA)"), a.set_ylabel("y (UA)")
    a.ticklabel_format(style="sci", scilimits=(-2, 2))
    a.xaxis.set_major_locator(plt.MaxNLocator(5))

    a = ax[0, 2]
    clean = observer.radial_velocity(traj, star, obs_)
    a.plot(traj.t[::step], clean[::step], lw=0.6, color="k", label="signal")
    if n_obs > 0 or sigma > 0:
        a.errorbar(rv.t, rv.value, yerr=rv.error if sigma > 0 else None, fmt=".", ms=3, color="C3",
                   alpha=0.7, label="observations")
    a.set_title("Vitesse radiale"), a.set_xlabel("t (ans)"), a.set_ylabel("v_r (m/s)"), a.legend(fontsize=8)

    def mark_truths(a, signed=False, x_is_period=True):
        for i, tr in enumerate(truths):
            c = f"C{i % 10}"
            for n, ls in ((1, "-"), (2, ":"), (3, ":")):
                f = n * tr.frequency * (tr.direction if signed else 1)
                x = 1 / abs(f) if x_is_period else f
                a.axvline(x, color=c, ls=ls, lw=1.0 if n == 1 else 0.7, alpha=0.8 if n == 1 else 0.5,
                          label=tr.name if n == 1 else None)

    a = ax[1, 0]
    sel = spec_rv.freq > 0
    a.semilogx(1 / spec_rv.freq[sel], spec_rv.amplitude[sel], color="k", lw=0.7)
    mark_truths(a)
    for pk in peaks_rv:
        a.plot(pk.period, pk.amplitude, "v", color="C3", ms=6)
    a.set_xlim(0.5 * p_min, min(2 * p_max, years))
    a.set_title(f"Spectre de la vitesse radiale ({spec_rv.method})\ntrait plein : planète, pointillés : harmoniques 2f, 3f",
                fontsize=10)
    a.set_xlabel("période (ans)"), a.set_ylabel("amplitude (m/s)"), a.legend(fontsize=7)

    a = ax[1, 1]
    fz = spec_z.freq
    lim = 3.5 * truths[0].frequency
    sel = np.abs(fz) <= lim
    a.plot(fz[sel], spec_z.amplitude[sel], color="k", lw=0.7)
    mark_truths(a, signed=True, x_is_period=False)
    for pk in peaks_z:
        if abs(pk.frequency) <= lim:
            a.plot(pk.frequency, pk.amplitude, "v", color="C3", ms=6)
    a.set_yscale("log"), a.set_ylim(spec_z.amplitude[sel].max() * 1e-5, spec_z.amplitude[sel].max() * 2)
    if truths[-1].frequency < 0.1 * truths[0].frequency:  # widely spread periods: log scale on both sides
        a.set_xscale("symlog", linthresh=0.5 * truths[-1].frequency)
    a.set_title("Spectre de l'astrométrie z = x + iy\n(f > 0 : sens direct, f < 0 : rétrograde)", fontsize=10)
    a.set_xlabel("fréquence (cycles/an)"), a.set_ylabel("amplitude (UA)")

    a = ax[1, 2]
    fdat = diagnostics.fidelity(traj)
    if fdat.energy is not None:
        a.semilogy(traj.t[::step], np.abs(fdat.energy[::step]) + 1e-17, lw=0.6, label="énergie")
    if fdat.angular_momentum is not None:
        a.semilogy(traj.t[::step], np.abs(fdat.angular_momentum[::step]) + 1e-17, lw=0.6, label="moment cinétique")
    a.set_title("Jauge de fidélité (dérive relative)"), a.set_xlabel("t (ans)"), a.legend(fontsize=8)

    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_bruit{sigma:g}_n{n_obs}" if (sigma or n_obs) else ""
    path = out_dir / f"spectre_{preset}{suffix}.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"figure : {path}")
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("preset", nargs="?", help="nom du preset (voir gravsim/presets)")
    p.add_argument("--tous", action="store_true", help="lancer la série d'études par défaut")
    p.add_argument("--annees", type=float, help="durée simulée (défaut : 6 x la plus longue période)")
    p.add_argument("--etoile", help="corps observé (défaut : le plus massif)")
    p.add_argument("--integrateur", default="yoshida4", choices=["yoshida4", "leapfrog", "dop853"])
    p.add_argument("--echantillonnage", type=float, help="pas d'échantillonnage en ans (défaut : P_min / 50)")
    p.add_argument("--bruit", type=float, default=0.0, help="bruit blanc sur la vitesse radiale (m/s)")
    p.add_argument("--n-obs", type=int, default=0, help="nombre d'observations irrégulières (0 = échantillonnage complet)")
    p.add_argument("--saison", type=float, default=0.0, help="fraction de l'année inobservable")
    p.add_argument("--visee", type=float, default=0.0, help="direction de la ligne de visée (degrés)")
    p.add_argument("--inclinaison", type=float, default=90.0, help="inclinaison de l'observateur (degrés)")
    p.add_argument("--graine", type=int, default=1)
    p.add_argument("--sortie", type=Path, default=Path("outputs"))
    args = p.parse_args()
    presets = DEFAULT_SET if args.tous else [args.preset]
    if presets == [None]:
        p.error("donner un preset ou --tous")
    for name in presets:
        study(name, args.annees, args.etoile, args.integrateur, args.echantillonnage, args.bruit, args.n_obs,
              args.saison, args.visee, args.inclinaison, args.sortie, args.graine)


if __name__ == "__main__":
    main()

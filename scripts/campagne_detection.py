"""Campagne par injection : la détection retrouve-t-elle le bon nombre de planètes ?

Des systèmes aléatoires de vérité connue sont simulés (N corps, interactions comprises), observés en vitesse
radiale (calendrier irrégulier, saisons, bruit blanc), puis soumis à la détection aveugle. La vérité ne sert
qu'à noter le résultat.

Exemples :
    python scripts/campagne_detection.py                 # 60 systèmes, bruit 3 m/s, 100 observations
    python scripts/campagne_detection.py --systemes 200 --bruit 5 --n-obs 60
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from gravsim.analysis.campaign import CampaignSettings, run_campaign  # noqa: E402

LABELS = {
    "systemes": "systèmes simulés",
    "planetes": "planètes injectées",
    "compte_exact": "nombre de planètes exact",
    "compte_dans_les_possibles": "vrai nombre parmi les réponses possibles",
    "systemes_ambigus": "systèmes signalés AMBIGU",
    "completude": "planètes retrouvées (toutes)",
    "fausses_detections_par_systeme": "fausses détections par système",
    "systemes_avec_fausse_detection": "systèmes avec au moins une fausse détection",
    "erreur_periode_mediane": "erreur médiane sur la période",
    "erreur_amplitude_mediane": "erreur médiane sur K",
    "duree_moyenne_s": "durée moyenne par système (s)",
}


def figure(result, path: Path) -> None:
    st = result.settings
    planets = result.planets()
    fig, ax = plt.subplots(2, 2, figsize=(13, 9.5))
    fig.suptitle(f"Campagne par injection — {len(result.outcomes)} systèmes, {len(planets)} planètes, "
                 f"bruit {st.sigma:g} m/s, {st.n_obs} observations sur {st.baseline:g} ans", fontsize=12)

    a = ax[0, 0]
    snr = np.array([p.snr for p in planets])
    found = np.array([p.found for p in planets])
    edges = np.logspace(np.log10(max(snr.min(), 0.3)), np.log10(snr.max() * 1.01), 14)
    centres, rates, counts = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (snr >= lo) & (snr < hi)
        if sel.any():
            centres.append(np.sqrt(lo * hi))
            rates.append(found[sel].mean())
            counts.append(sel.sum())
    a.semilogx(centres, rates, "o-", color="C0")
    for x, y, n in zip(centres, rates, counts):
        a.annotate(str(n), (x, y), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    a.axvline(5, color="grey", ls=":", label="SNR = 5")
    a.set_ylim(-0.05, 1.1)
    a.set_xlabel("K / σ · √(N/2)")
    a.set_ylabel("fraction retrouvée")
    a.set_title("Complétude selon le rapport signal / bruit (nombre de planètes par point)")
    a.legend()

    a = ax[0, 1]
    n_max = max(max(len(o.truths) for o in result.outcomes), max(o.detected for o in result.outcomes))
    matrix = np.zeros((n_max + 1, n_max + 1), dtype=int)
    for o in result.outcomes:
        matrix[len(o.truths), o.detected] += 1
    a.imshow(matrix, cmap="Blues", origin="lower")
    for i in range(n_max + 1):
        for j in range(n_max + 1):
            if matrix[i, j]:
                a.text(j, i, str(matrix[i, j]), ha="center", va="center",
                       color="white" if matrix[i, j] > matrix.max() / 2 else "black")
    a.set_xlabel("planètes détectées")
    a.set_ylabel("planètes injectées")
    a.set_xticks(range(n_max + 1))
    a.set_yticks(range(n_max + 1))
    a.set_title("Nombre détecté contre nombre réel (diagonale = exact)")

    a = ax[1, 0]
    ok = [p for p in planets if p.found]
    if ok:
        k_true = np.array([p.amplitude for p in ok])
        k_det = k_true * (1 + np.array([p.amplitude_error for p in ok]))
        a.loglog(k_true, k_det, "o", ms=4, alpha=0.7)
        lim = [min(k_true.min(), k_det.min()) * 0.8, max(k_true.max(), k_det.max()) * 1.2]
        a.plot(lim, lim, "k--", lw=0.8)
    missed = [p for p in planets if not p.found]
    if missed:
        a.scatter([p.amplitude for p in missed], [min(p.amplitude for p in planets) * 0.7] * len(missed),
                  marker="x", color="C3", label="non retrouvées")
        a.legend()
    a.set_xlabel("K réel (m/s)")
    a.set_ylabel("K mesuré (m/s)")
    a.set_title("Amplitudes retrouvées")

    a = ax[1, 1]
    if ok:
        err = np.array([p.period_error for p in ok]) * 100
        a.hist(err, bins=30, color="C2")
    a.set_xlabel("erreur relative sur la période (%)")
    a.set_ylabel("planètes")
    a.set_title("Précision des périodes")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--systemes", type=int, default=60)
    p.add_argument("--graine", type=int, default=2026)
    p.add_argument("--bruit", type=float, default=3.0, help="bruit blanc (m/s)")
    p.add_argument("--n-obs", type=int, default=100)
    p.add_argument("--duree", type=float, default=4.0, help="durée des observations (ans)")
    p.add_argument("--saison", type=float, default=0.3)
    p.add_argument("--planetes-max", type=int, default=3)
    p.add_argument("--sortie", type=Path, default=Path("outputs"))
    args = p.parse_args()
    st = CampaignSettings(n_systems=args.systemes, seed=args.graine, sigma=args.bruit, n_obs=args.n_obs,
                          baseline=args.duree, season_fraction=args.saison, n_planets=(1, args.planetes_max))
    started = time.perf_counter()

    def progress(i, n, o):
        mark = "exact" if o.exact else ("possible" if o.count_possible else "FAUX")
        print(f"{i:4d}/{n}  vrai {len(o.truths)}  détecté {o.detected}  possibles {o.possible_counts}  "
              f"fausses {o.spurious}  SNR {[round(t.snr) for t in o.truths]}  -> {mark}", flush=True)

    result = run_campaign(st, progress)
    summary = result.summary()
    print(f"\n=== Bilan ({time.perf_counter() - started:.0f} s) ===")
    for key, value in summary.items():
        text = f"{value:.1%}" if key in ("compte_exact", "compte_dans_les_possibles", "systemes_ambigus", "completude",
                                         "systemes_avec_fausse_detection", "erreur_periode_mediane",
                                         "erreur_amplitude_mediane") else f"{value:.3g}"
        print(f"  {LABELS[key]:45s} {text}")
    print("  complétude selon le rapport signal/bruit K/σ·√(N/2) :")
    for lo, hi, n, found in result.completeness_by_snr():
        print(f"    {lo:>4g} – {hi:<4g} : {n:4d} planètes, {found:.0%} retrouvées" if n else
              f"    {lo:>4g} – {hi:<4g} :    0 planète")
    args.sortie.mkdir(parents=True, exist_ok=True)
    png = args.sortie / "campagne_detection.png"
    figure(result, png)
    data = {"reglages": {k: v for k, v in vars(st).items() if k != "detection"}, "bilan": summary,
            "systemes": [{"vrai": len(o.truths), "detecte": o.detected, "possibles": o.possible_counts,
                          "fausses": o.spurious,
                          "planetes": [{"P": t.period, "K": t.amplitude, "e": t.e, "M_jup": t.mass_mjup,
                                        "snr": t.snr, "trouvee": t.found} for t in o.truths]}
                         for o in result.outcomes]}
    (args.sortie / "campagne_detection.json").write_text(json.dumps(data, indent=1, ensure_ascii=False),
                                                         encoding="utf-8")
    print(f"\nfigure : {png}\ndonnées : {args.sortie / 'campagne_detection.json'}")


if __name__ == "__main__":
    main()

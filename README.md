# Gravitationnal-Sytem

Simulateur gravitationnel 2D à N corps, conçu pour :

1. **visualiser** le comportement de corps en interaction gravitationnelle ;
2. **analyser par spectre** le mouvement réflexe d'une étoile (vitesse radiale, astrométrie) pour retrouver le nombre de planètes qui gravitent autour.

Spécification complète : [docs/SPEC.md](docs/SPEC.md).

## Installation

Environnement conda dédié (Python 3.11, numpy, scipy, matplotlib, PySide6, pyqtgraph, pytest) :

```bash
conda env create -f environment.yml
conda activate gravsim
```

Le paquet `gravsim` est installé en mode éditable : les modifications du code sont prises en compte sans réinstallation.

## Lancer le simulateur

```bash
conda activate gravsim
gravsim            # ou : python -m gravsim
```

- **Espace** lecture/pause · **S** pas · **R** réinitialiser · **L** revenir au direct. Molette pour zoomer, glisser pour déplacer, clic sur un corps pour le sélectionner.
- Panneau **Corps** : masse, rayon, position, vitesse (norme + direction, ou composantes), corps fixe, vitesse orbitale automatique (circulaire, excentrique, libération).
- Panneau **Poussées** : variation de vitesse signée (prograde, radiale, angle absolu), immédiate ou programmée.
- Panneau **Vue** : taille des corps (masse, manuelle, échelle réelle), référentiel (inertiel, barycentrique, centré sur un corps, tournant avec une paire), cadrage, vecteurs vitesse et force, sphères de Hill.
- Panneau **Intégration** : DOP853, Yoshida 4 ou leapfrog, avec le pas conseillé. La barre d'état affiche la dérive d'énergie (hors poussées).
- Un curseur permet de remonter dans le temps sur la trajectoire déjà calculée ; la case « Pause à la collision » arrête la simulation exactement au contact.

## Tests

```bash
pytest
```

## Études spectrales (sans interface)

```bash
python scripts/etude_spectre.py soleil_jupiter
python scripts/etude_spectre.py --tous
python scripts/etude_spectre.py resonance_2_1 --annees 3 --bruit 5 --n-obs 120 --saison 0.3
```

Chaque étude simule un preset, observe l'étoile (vitesse radiale et astrométrie), compare les pics du spectre aux planètes réellement présentes et enregistre une figure dans `outputs/`. Options : `--help`. Résultats commentés : [docs/RESULTATS_JALON2.md](docs/RESULTATS_JALON2.md).

Presets disponibles : `soleil_jupiter`, `terre_lune`, `binaire`, `systeme_solaire`, `jupiter_chaud`, `resonance_2_1`, `excentrique`, `soleil_fixe_comete`.

## Structure

```
gravsim/
  core/       physique : corps, forces, intégrateurs, événements (sans Qt)
  analysis/   référentiels, orbites, diagnostics, analyse spectrale (sans Qt)
  gui/        interface PySide6 / pyqtgraph (fenêtre, viewer, panneaux, contrôleur de lecture)
  presets/    scénarios prêts à l'emploi (JSON)
scripts/      études sans interface
tests/
docs/
```

## Avancement

- [x] Jalon 0 : mise en place
- [x] Jalon 1 : cœur physique + tests
- [x] Jalon 2 : analyse et spectre sans interface
- [x] Jalon 3 : interface de simulation
- [ ] Jalon 4 : interface d'analyse
- [ ] Jalon 5 : détection de planètes et validation
- [ ] Jalon 6 : finitions

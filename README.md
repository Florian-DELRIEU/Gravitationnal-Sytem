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

## Tests

```bash
pytest
```

## Structure

```
gravsim/
  core/       physique : corps, forces, intégrateurs, événements (sans Qt)
  analysis/   référentiels, orbites, diagnostics, analyse spectrale (sans Qt)
  gui/        interface PySide6 / pyqtgraph
  presets/    scénarios prêts à l'emploi (JSON)
scripts/      études sans interface
tests/
docs/
```

## Avancement

- [x] Jalon 0 : mise en place
- [ ] Jalon 1 : cœur physique + tests
- [ ] Jalon 2 : analyse et spectre sans interface
- [ ] Jalon 3 : interface de simulation
- [ ] Jalon 4 : interface d'analyse
- [ ] Jalon 5 : détection de planètes et validation
- [ ] Jalon 6 : finitions

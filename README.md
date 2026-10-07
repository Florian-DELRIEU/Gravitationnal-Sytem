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

Trois façons, de la plus simple à la plus souple :

**1. Application autonome (aucun Python à installer)** : un fichier à double-cliquer, copiable sur un autre ordinateur du même système. PyInstaller ne fait pas de compilation croisée : chaque système construit la sienne.

```bash
pip install -e ".[gui,build]"          # ou, dans l'environnement conda : pip install pyinstaller
python scripts/construire_executable.py
```

Résultat dans `dist/` : sous **Windows**, le dossier `Simulateur Gravitationnel` avec `Simulateur Gravitationnel.exe` (à copier en entier) ; sous **macOS**, `Simulateur Gravitationnel.app` (~170 Mo). L'exécutable accepte `--autotest` (vérifie les presets, les trois intégrateurs et le rendu, code de sortie 0 si tout va bien).

Sous Windows, le plus simple : double-cliquer sur `windows\Construire l'executable (Windows).bat` (il utilise l'environnement `gravsim` créé par `Installer (Windows).bat`).

Sans PC Windows sous la main : le workflow `.github/workflows/construire.yml` construit et vérifie les versions **Windows et macOS** sur les serveurs de GitHub (onglet *Actions* → *Construire les exécutables* → *Run workflow*, puis télécharger le zip dans *Artifacts*). Il faut pour cela que le projet soit sur GitHub.

**2. Lanceur léger (Windows, avec conda)** : dans le dossier `windows/`, double-cliquer une fois sur `Installer (Windows).bat` (crée l'environnement `gravsim`), puis sur `Lancer le simulateur.bat`. Rapide à mettre en place, mais demande Miniconda.

**3. Lanceur léger (macOS)** : `python scripts/creer_app.py` crée `Simulateur Gravitationnel.app` à la racine, qui lance le Python de l'environnement `gravsim` (journal : `~/Library/Logs/gravsim.log`). À recréer si l'environnement est déplacé.

**Depuis un terminal** :

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

## Analyse et spectre dans l'interface

La zone centrale a trois onglets : **Simulation**, **Analyse**, **Spectre**. Les panneaux latéraux s'effacent dans les deux derniers pour laisser la place aux graphes (celui des *Propriétés* reste dans « Analyse », car l'onglet *Vue* choisit le référentiel) et reviennent avec la simulation.

- **Analyse** : distances entre paires (min, max, actuelle), vitesses (norme, composantes, relative à un corps, en UA/an ou km/s), positions (x(t), y(t), distance, trajectoire x–y), énergies et **jauge de fidélité** (dérive de l'énergie, du moment cinétique et de la quantité de mouvement, hors poussées), éléments orbitaux (a, périastre, apoastre, e, ω) avec le résumé de la paire (type d'orbite, masse réduite, vitesse de libération). Les collisions (rouge) et les poussées (orange) sont marquées sur tous les graphes de temps. Les courbes suivent le référentiel choisi dans l'onglet *Vue*.
- **Spectre** : choix du corps observé, du signal (vitesse radiale avec ligne de visée et inclinaison, ou astrométrie x + iy), de l'échantillonnage (régulier + FFT fenêtrée, ou irrégulier avec trous saisonniers + Lomb-Scargle), du bruit, du spectrogramme. Le spectre porte les **planètes réelles** en repère (trait plein, harmoniques 2f et 3f en pointillés), les pics sont numérotés et identifiés dans l'onglet *Pics et planètes* (planète, harmonique, lobe de fenêtre, alias annuel, **AMBIGU** quand deux explications se valent). Des conseils s'affichent : durée trop courte, pas trop grossier, poussée dans l'intervalle, corps fixe. Le bouton *Compléter* poursuit la simulation jusqu'à 6 fois la période de la planète la plus lente.
- **Export** : *Fichier → Exporter l'analyse (.csv)* écrit une table (positions et vitesses dans le référentiel choisi, énergies, barycentre, distances, dérives) et, s'il y en a, un fichier `_evenements.csv` (poussées, collisions, séparations).

Les mêmes calculs sont disponibles sans interface : `gravsim.analysis.pipeline` (observation → spectre → pics identifiés) et `gravsim.analysis.export`.

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
  gui/        interface PySide6 / pyqtgraph (fenêtre, viewer, panneaux, onglets Analyse et Spectre)
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
- [x] Jalon 4 : interface d'analyse
- [ ] Jalon 5 : détection de planètes et validation
- [ ] Jalon 6 : finitions

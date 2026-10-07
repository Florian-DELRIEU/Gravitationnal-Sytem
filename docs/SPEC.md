# Cahier des charges — Simulateur gravitationnel 2D à N corps

Statut : **v2, revue critique faite, à valider** (aucun code écrit). Projet repris de zéro.

## 1. Objectifs

1. **Visualiser** le comportement global de corps en interaction gravitationnelle, en 2D.
2. **Étudier par analyse spectrale** le mouvement d'une étoile (réflexe dû à ses planètes) : retrouver les fréquences et amplitudes des oscillations, et en déduire le **nombre de planètes** qui gravitent autour.

Le simulateur doit être **fidèle aux équations** (pas de triche visuelle sur la physique) tout en restant **pratique à visualiser** (échelles d'affichage compressées, mais jamais appliquées aux calculs).

## 2. Décisions de conception

| Sujet | Décision |
|---|---|
| Langage / GUI | Python 3.11, cœur numpy/scipy, interface PySide6 + pyqtgraph |
| Environnement | env conda dédié `gravsim`, dépendances déclarées dans `pyproject.toml`, tests pytest |
| Langue | code (identifiants, docstrings) en anglais ; interface et documentation en français |
| Unités internes | UA, M☉, an. `G = 4π²` par convention (écart ≈ 4×10⁻⁵ avec la valeur IAU, constante unique modifiable). Conversion SI à l'affichage ; vitesses radiales en m/s (1 UA/an = 4740,47 m/s) |
| Nombre de corps | N corps dès le départ ; interface pensée pour 2 à ~10 corps ; masse nulle autorisée (particule test) |
| Signaux spectraux | Vitesse radiale **et** position complexe `z = x + iy`, comparées |
| Collisions | Détectées (y compris entre deux pas) et signalées ; case « pause à la collision » ; pas de fusion |
| Référentiel | La physique est toujours calculée dans un repère inertiel unique ; le référentiel choisi n'est qu'un post-traitement (affichage + analyse) |

## 3. Exigences fonctionnelles

### 3.1 Définition d'un corps

Chaque corps possède :
- **nom** et **couleur** ;
- **masse** `m` (M☉, avec raccourcis M⊕ et M_Jup). `m = 0` autorisé : particule test, qui subit la gravité sans en exercer ;
- **rayon physique** `R` (R☉ / UA), utilisé pour détecter les collisions. Valeur par défaut déduite d'une densité réglable, modifiable à la main ;
- **position** `(x, y)` ;
- **vitesse**, saisie de deux façons équivalentes et toujours synchronisées :
  - norme + direction (angle en degrés dans le plan), ou
  - composantes `(vx, vy)` ;
- case **corps fixe** : il exerce sa force mais n'est jamais accéléré (position et vitesse figées).

Conséquences d'un corps fixe, affichées dans l'interface : la quantité de mouvement totale n'est plus conservée, le barycentre n'est pas immobile ; l'énergie reste conservée ; le moment cinétique n'est conservé que calculé autour du corps fixe (s'il est unique).

### 3.2 Vitesse orbitale automatique

Bouton « vitesse orbitale » pour un corps `i` autour d'un corps de référence `j` (par défaut le plus massif) :
- orbite **circulaire** : `v = √(G(mᵢ + mⱼ)/r)`, perpendiculaire à `r`, sens horaire ou antihoraire au choix ;
- option **excentricité** `e` avec départ au périastre ou à l'apoastre : `v_p = √(G(mᵢ+mⱼ)(1+e)/(r(1−e)))` au périastre, `v_a = √(G(mᵢ+mⱼ)(1−e)/(r(1+e)))` à l'apoastre ;
- la vitesse calculée est **relative à `j`** : on lui ajoute la vitesse de `j` ;
- boutons annexes : **vitesse de libération** `√(2G(mᵢ+mⱼ)/r)` (orbite parabolique), et affichage de la vitesse circulaire de référence à côté de la saisie manuelle.

Avec plus de deux corps, la formule à deux corps est une approximation (les autres corps perturbent). L'interface l'indique.

Bouton **« annuler la quantité de mouvement totale »** : retire la dérive du centre de masse, indispensable pour l'analyse spectrale (sinon l'étoile dérive en plus d'osciller). Il est proposé automatiquement avant une analyse spectrale si la dérive n'est pas nulle.

### 3.3 Poussées (impulsions)

Une poussée est une variation instantanée de vitesse `Δv` appliquée à un corps :
- **grandeur** signée (positive = accélération, négative = freinage) ;
- **direction**, au choix : prograde/rétrograde (le long de la vitesse **relative à un corps de référence**, par défaut le plus massif), radiale (vers/depuis ce corps), ou angle absolu ;
- **déclenchement** : immédiat, ou à un instant `t` programmé. Les poussées programmées sont listées, modifiables et sauvegardées avec le scénario ;
- sans effet sur un corps fixe.

L'intégrateur s'arrête exactement à l'instant de chaque poussée (jamais d'application « à peu près ») : segment d'intégration interrompu pour DOP853, pas partiel pour les intégrateurs à pas fixe.

Chaque poussée change l'énergie et le moment cinétique : ces variations sont **comptabilisées** (bilan d'énergie injectée) pour que la jauge de fidélité ne les confonde pas avec une erreur numérique.

### 3.4 Collisions

- Collision quand `‖rᵢ − rⱼ‖ ≤ Rᵢ + Rⱼ`.
- **Détection continue** : la distance minimale est recherchée *à l'intérieur* de chaque pas (fonction d'événement de scipy pour DOP853, interpolation cubique d'Hermite des positions relatives pour les intégrateurs à pas fixe). Un contact rasant entre deux pas n'est donc jamais manqué.
- Elle est **signalée** : bandeau, entrée dans un journal d'événements (instant, corps, vitesse relative, angle d'impact), marqueur sur les graphes.
- Case **« pause à la collision »** (désactivée par défaut) et bouton pour stopper à tout moment.
- Pas de fusion. Si la simulation continue, les corps qui se recouvrent subissent la force d'une **sphère homogène** (`a = G·m·r / R³` à l'intérieur du rayon), ce qui supprime la singularité `1/r²` sans paramètre arbitraire. L'état « en recouvrement » est signalé dans les diagnostics.

### 3.5 Contrôle de la simulation

Lecture, pause, pas à pas, vitesse de simulation réglable (an/s), remise à zéro, remontée dans le temps sur la trajectoire déjà calculée (curseur). Choix de l'intégrateur et du pas ou de la tolérance, avec un **pas conseillé** calculé automatiquement (voir §4).

### 3.6 Visualisation

- Vue 2D avec zoom, déplacement, suivi automatique d'un corps, traînées de trajectoire à longueur réglable.
- **Taille affichée** : modes (a) proportionnelle à `m^(1/3)` compressée et bornée entre un minimum et un maximum en pixels, (b) taille choisie à la main, (c) **échelle réelle** (rayons physiques). Le mode n'affecte jamais le calcul. Les particules test ont une taille minimale fixe.
- Vecteurs optionnels : vitesse, force, barycentre, sphères de Hill.
- Échelle graduée dans la vue (UA).

### 3.7 Référentiels

Référentiel d'affichage et d'analyse, au choix :
- inertiel initial ;
- barycentrique ;
- centré sur un corps ;
- tournant avec une paire de corps (le corps A→B reste sur l'axe des x).

Changer de référentiel ne relance pas la simulation. Dans un référentiel tournant, les vitesses affichées sont les vitesses relatives à ce repère (`v' = v − ω × r'`). En option dans ce repère : **constante de Jacobi** d'une particule test et **points de Lagrange** de la paire.

### 3.8 Données d'analyse

Séries temporelles et graphes pour tout corps ou toute paire :
- positions, trajectoires dans le référentiel choisi ;
- distances entre paires, distance minimale et maximale ;
- vitesses (norme et composantes), vitesse relative ;
- énergies cinétique, potentielle, totale ; moment cinétique ; quantité de mouvement ; barycentre ;
- **analyse d'une paire** : masse réduite, énergie du mouvement relatif, **type d'orbite** (liée elliptique, parabolique, hyperbolique), vitesse de libération ;
- éléments orbitaux instantanés par rapport à un corps de référence : demi-grand axe `a` (négatif si hyperbolique), excentricité `e`, argument du périastre `ω`, période (si liée). Le type d'orbite se déduit du **signe de l'énergie**, pas de `e` seul : une chute radiale depuis le repos a `e = 1` mais est liée ;
- **jauge de fidélité** : dérive relative de l'énergie (après retrait du bilan des poussées), du moment cinétique et de la quantité de mouvement, chacune désactivée quand elle n'a pas de sens (corps fixe, recouvrement).

Export CSV et NPZ des trajectoires et des analyses ; sauvegarde et chargement d'un scénario en JSON versionné.

### 3.9 Analyse spectrale (objectif 2)

**Observateur.** Le plan de la simulation est le plan orbital. L'observateur est défini par :
- une **ligne de visée** `φ` dans le plan ;
- une **inclinaison** `i` (90° par défaut : vue par la tranche).

**Signal observé.** On choisit un corps cible (l'étoile) et on extrait, dans le référentiel barycentrique :
- la **vitesse radiale** `v_r(t) = sin i · v★(t) · n̂`, avec `n̂ = (cos φ, sin φ)` ;
- la **position complexe** `z(t) = x★(t) + i·y★(t)` (astrométrie, vue de face).

**Échantillonnage.** Indépendant du pas d'intégration : grille régulière, ou instants irréguliers (calendrier d'observation avec trous). Règles indicatives affichées : durée `T ≳ 3 P_max`, pas `Δt ≲ P_min / 10`. Bruit optionnel : blanc gaussien (σ = 1 m/s par défaut, ordre de grandeur des spectrographes actuels), plus une composante rouge (activité stellaire) en option.

**Méthodes.**
- FFT avec fenêtrage (Hann ou autre) pour les grilles régulières ; pour `z(t)`, la FFT complexe distingue prograde (`f > 0`) et rétrograde (`f < 0`) et donne un seul pic par planète circulaire ;
- périodogramme de Lomb-Scargle pour les échantillonnages irréguliers ;
- spectrogramme (fenêtre glissante) pour visualiser la dérive des fréquences quand les planètes interagissent.

**Extraction itérative (prewhitening).** Détecter le pic le plus fort, ajuster une sinusoïde puis une orbite képlérienne, la soustraire, recommencer. L'arrêt repose sur deux critères : probabilité de fausse alarme du pic résiduel, et **sélection de modèle** (Δ BIC entre « k planètes » et « k + 1 planètes »).

**Pièges à traiter explicitement :**
- une orbite excentrique génère des harmoniques à `2f`, `3f` (amplitudes ∝ `e`, `e²`) qu'il ne faut pas compter comme des planètes ;
- **dégénérescence connue** : une planète excentrique et deux planètes circulaires en résonance 2:1 produisent au premier ordre en `e` le même spectre. L'outil doit **signaler l'ambiguïté** plutôt que trancher arbitrairement ; la distinguer (termes d'ordre supérieur, évolution dynamique du couple résonant) est un sujet d'étude, pas une garantie ;
- les interactions planète-planète décalent et élargissent les pics ;
- résolution : deux fréquences ne sont séparables que si `|f₁ − f₂| ≳ 1/T` ; fréquence maximale `1/(2Δt)` ;
- pics de repliement (aliasing) pour un échantillonnage irrégulier ou grossier ; fuite spectrale d'une planète forte qui masque une faible (raison d'être du prewhitening).

**Sorties.** Nombre de planètes estimé (avec indicateur d'ambiguïté), et pour chacune période `P`, amplitude `K`, excentricité estimée, demi-grand axe (3ᵉ loi de Kepler) et masse `m sin i` déduite de `K` (masse vraie quand `i = 90°`) :

`K = (2πG/P)^(1/3) · m_p sin i / (M★ + m_p)^(2/3) · 1/√(1 − e²)`.

Ordres de grandeur : Jupiter autour du Soleil, `P ≈ 11,86 an`, `K ≈ 12,5 m/s`, balancement de position ≈ `0,005 UA` ; la Terre, `K ≈ 0,09 m/s`.

**Validation par injection.** Un mode « campagne » génère des systèmes aléatoires de vérité connue (nombre de planètes, masses, périodes), simule, ajoute du bruit, lance la détection et mesure : taux de détection en fonction du rapport `K/σ` et de `T/P`, fausses détections, erreur sur `P` et `K`, nombre de planètes retrouvé. Les seuils de réussite sont fixés après les premiers résultats.

## 4. Équations et schémas numériques

Accélération du corps `i` (non fixe) :

`aᵢ = G · Σ_{j≠i} mⱼ · (rⱼ − rᵢ) / ‖rⱼ − rᵢ‖³`

Les corps fixes contribuent à la somme mais leur `a` est forcé à zéro. En recouvrement, avec `sᵢⱼ = max(Rᵢ, Rⱼ)` et `‖rⱼ − rᵢ‖ < sᵢⱼ`, le terme `j` devient `G·mⱼ·(rⱼ − rᵢ)/sᵢⱼ³` (point dans une sphère homogène). Cette loi est symétrique (action = réaction) et dérive du potentiel `U = −G mᵢ mⱼ (3s² − r²)/(2s³)` : quantité de mouvement et énergie restent conservées pendant un recouvrement.

Paramètre gravitationnel d'une paire : `μ = G(mᵢ + mⱼ)` si les deux corps sont libres, mais `μ = G mⱼ` si le corps de référence `j` est fixe (il ne recule pas). Utilisé par la vitesse orbitale automatique et les éléments orbitaux.

Intégrateurs sélectionnables :
- **DOP853** (scipy, adaptatif, ordre 8, sortie dense, événements natifs) : défaut en mode interactif et pour les rencontres proches ;
- **Leapfrog / vitesse-Verlet** et **Yoshida d'ordre 4** (symplectiques, pas fixe) : pas d'accumulation d'erreur d'énergie sur le long terme, défaut pour les longues durées et l'analyse spectrale.

**Pas conseillé** (pas fixe) : le plus petit de `P_min / 200` et d'une fraction du temps de passage au périastre de l'orbite la plus excentrique (`~ (r_p³ / G M)^(1/2) / 20`), car un pas fixe dimensionné sur la période seule échoue au périastre d'une orbite très excentrique.

Les poussées et les collisions sont gérées comme des **événements** : l'intégration s'arrête à l'instant exact, applique l'effet, puis reprend.

Dérives calculées à chaque échantillon : `ΔE/E₀` (corrigée du bilan des poussées), `ΔL/L₀`, `‖Δp‖/p_réf`.

## 5. Architecture

```
gravsim/
  core/          units.py  body.py  scenario.py  forces.py
                 integrators.py  events.py  simulation.py  trajectory.py
  analysis/      frames.py  orbits.py  diagnostics.py
                 observer.py  spectral.py  detection.py  campaign.py
  gui/           main_window.py  viewer.py  body_panel.py
                 time_controls.py  analysis_tabs.py  spectral_tab.py
  presets/       *.json
scripts/         études sans interface (spectre, campagnes)
tests/
docs/
```

Principes :
- `core/` et `analysis/` n'importent jamais Qt : ils tournent sans fenêtre (lots, tests, campagnes, scripts) ;
- `Trajectory` est la structure centrale : temps `(T,)`, positions `(T, N, 2)`, vitesses `(T, N, 2)`, journal d'événements ;
- **stockage** : la trajectoire complète est enregistrée à la cadence d'échantillonnage demandée, pas à chaque pas d'intégration ; l'affichage lit une version décimée. Ordre de grandeur : 10⁶ échantillons × 10 corps ≈ 320 Mo, à garder en tête pour les campagnes ;
- les référentiels et l'observateur sont des fonctions pures `Trajectory → données` ;
- l'interface fait avancer la simulation par tranches courtes à budget de temps CPU (12 ms par image), dans le thread de l'interface : pour 2 à ~10 corps c'est aussi fluide qu'un thread de travail, sans verrou autour des poussées immédiates ni des modifications. La vitesse réellement atteinte s'affiche, et se réduit si le calcul ne suit pas. Un thread de travail reste possible si de grands N l'exigent ;
- le calcul des forces est vectorisé en numpy (O(N²), largement suffisant pour N ≤ 50). Numba envisageable si les campagnes sont trop lentes (mesure au jalon 5).

**Presets** servant aussi de cas de test : Terre-Lune, Soleil-Jupiter, binaire d'étoiles, Soleil + 8 planètes, Jupiter chaud, couple résonant 2:1 (type GJ 876), étoile + planète excentrique (pendant de la dégénérescence).

## 6. Validation (tests automatisés)

Les seuils sont des cibles, calibrées au premier passage.

| # | Test | Critère visé |
|---|---|---|
| T1 | Deux corps, orbite circulaire : période mesurée vs `2π√(a³/(G(M+m)))` | erreur relative < 10⁻⁶ (DOP853) |
| T2 | Orbite `e = 0,5` : dérive d'énergie | DOP853 < 10⁻⁹ sur 100 périodes ; au pas conseillé, Yoshida < 5×10⁻⁶ et leapfrog < 10⁻³, bornés sans dérive séculaire sur 200 périodes |
| T3 | Conservation de la quantité de mouvement, sans corps fixe | < 10⁻¹² relatif (invariant linéaire, conservé par tous les intégrateurs retenus) |
| T4 | Corps fixe : position strictement inchangée, énergie conservée | exact / même critère que T2 |
| T5 | Vitesse orbitale automatique : excentricité mesurée sur deux corps | réglage exact (`e < 10⁻¹²` à t₀) ; en cours d'intégration `e < 10⁻⁶` (DOP853), `< 5×10⁻⁶` (Yoshida) ; `e` demandée retrouvée ; vitesse de libération → `e = 1` ; référence fixe → `μ = G mⱼ` |
| T6 | Poussée prograde au périastre : nouvel apoastre vs vis-viva ; bilan d'énergie de la jauge nul | erreur < 10⁻⁶ |
| T7 | Collision par chute radiale et contact rasant : instant détecté vs analytique | < 10⁻⁶ an ; contact rasant entre deux pas détecté |
| T8 | Référentiel tournant : un binaire circulaire apparaît immobile | écart < 10⁻⁶ |
| T9 | Étoile + 1 planète : pic spectral à `P`, `K` retrouvé (cas circulaire), sur `v_r` et sur `z` | `P` à moins de `1/T` ; `K` à 2 % |
| T10 | Excentricité 0,5 (et 0,2, preset 0,4) : harmoniques absorbées par l'excentricité, une seule planète comptée | nombre = 1, e à 0,002, K à 0,1 % ✔ |
| T11 | Étoile + 3 planètes, périodes bien séparées, sans bruit et avec bruit | nombre exact, P à 0,5 %, K à 3 % ✔ |
| T12 | Couple 2:1 circulaire vs planète excentrique équivalente | sans bruit : correctement distingués ; bruit cachant les termes en e² : vrai nombre toujours parmi les réponses possibles, ambiguïté signalée dans la majorité des tirages ✔ (voir RESULTATS_JALON5.md) |
| T13 | Campagne par injection avec bruit | 0 fausse détection, 100 % des planètes retrouvées au-delà d'un signal/bruit de 7 (test) ; 120 systèmes : 100 % au-delà de 10 ✔ |

## 7. Jalons

L'ordre suit le risque : la partie la plus incertaine (objectif 2) est validée **sans interface** dès le jalon 2, avant d'investir dans la GUI.

0. **Mise en place** : env conda `gravsim`, `pyproject.toml`, pytest, structure des dossiers, README.
1. **Cœur + tests** : corps, forces, intégrateurs, événements (poussées, collisions continues), bilan d'énergie. T1 à T7.
2. **Analyse et spectre sans interface** : diagnostics, référentiels, orbites, observateur, FFT, Lomb-Scargle ; scripts produisant des graphes matplotlib sur les presets. T8, T9. *Point d'étape : on regarde ensemble les premiers spectres.*
3. **Interface de simulation** : viewer, panneau de saisie des corps (norme/angle, composantes, vitesse orbitale auto, poussées), contrôles de temps, tailles d'affichage, collisions.
4. **Interface d'analyse** : onglets graphes, référentiels, jauge de fidélité, export, onglet spectre. *(fait : pipeline d'observation `analysis/pipeline.py`, export `analysis/export.py` ; l'onglet Spectre liste les pics sans les compter, le comptage des planètes est le jalon 5)*
5. **Détection et validation** : prewhitening, ajustement képlérien, sélection de modèle, harmoniques et ambiguïté, campagne par injection. T10 à T13. *(fait : `analysis/detection.py`, `analysis/campaign.py`, onglet Spectre → Détection ; résultats dans docs/RESULTATS_JALON5.md)*
6. **Finitions** : presets, scénarios JSON, performances (Numba si mesuré nécessaire), documentation d'utilisation.

Chaque jalon se termine par un état utilisable et ses tests au vert.

## 8. Hors périmètre (pour l'instant)

3D (au-delà de l'inclinaison de l'observateur), relativité, fusion de corps, marées et rotation propre, frottement, intégrateurs spécialisés planétaires (Wisdom-Holman), méthodes de type arbre pour de grands N, interface multi-fenêtres.

## 9. Points à trancher plus tard

- Densité par défaut pour déduire le rayon physique d'un corps non précisé (probablement différenciée étoile / planète via les presets).
- ~~Forme exacte du seuil de fausse alarme~~ : formule analytique retenue, validée par la campagne (aucune fausse détection).
- ~~REBOUND comme oracle de test~~ : non nécessaire, les tests analytiques (Kepler, vis-viva, chute radiale, conservation) suffisent.

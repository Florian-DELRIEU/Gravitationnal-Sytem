# Plan : points de Lagrange et potentiels gravitationnels dans la vue

Statut : **plan validé, à exécuter** (rédigé sur Opus 5.5 ; exécution prévue sur Sonnet 5.5, effort medium).
Les vérifications physiques et techniques préalables sont faites (voir « Faits établis »).

## Objectif

Dans la vue de la simulation, pouvoir afficher :

1. les **cinq points de Lagrange** d'une paire de corps (marqueurs L1 à L5, étiquetés) ;
2. en fond, une **carte du potentiel** :
   - *potentiel gravitationnel* Φ de tous les corps (le « paysage » de gravité), ou
   - *potentiel effectif* Φ_eff dans le référentiel tournant avec la paire (gravité + effet centrifuge) : il montre
     les lobes de Roche, et les points de Lagrange y sont des cols (L1, L2, L3) et des sommets (L4, L5) ;
3. des **lignes de niveau**, et en évidence les **courbes critiques** passant par L1, L2, L3 (la courbe de L1
   est le lobe de Roche) ;
4. *(optionnel, étape 6)* la **région accessible** du corps sélectionné (courbe de vitesse nulle, constante de
   Jacobi).

## Décisions (modifiables avant exécution)

| Sujet | Choix retenu | Raison |
|---|---|---|
| Où l'afficher | dans la vue principale, en surimpression activable (onglet *Vue*) | voir les corps bouger sur leur potentiel ; pas de nouvel onglet |
| Paire de référence | par défaut celle du référentiel tournant si actif, sinon les deux corps les plus massifs ; modifiable | cas usuel Soleil–Jupiter, binaire |
| Potentiel effectif | gravité de **tous** les corps − ½ ω² \|r − c\|², avec ω et c de la paire | c'est le vrai champ ressenti dans ce repère ; avec 2 corps, c'est exactement le problème restreint |
| Points de Lagrange | formule exacte du problème à 2 corps (`frames.lagrange_points`), avec la séparation **instantanée** | exacte pour une orbite circulaire ; pour une orbite excentrique, approximation « pulsante » standard (signalée) |
| Couleurs | Φ : log10(−Φ) écrêté aux percentiles 2–98 %, palette `magma` ; Φ_eff : écrêté entre Φ(L1) − 1,5 Δ et Φ(L4) + 0,1 Δ (Δ = Φ(L4) − Φ(L1)), palette `viridis` ; opacité 0,75 | Φ diverge près des masses : sans écrêtage, tout est uniforme |
| Lignes de niveau | `contourpy` (déjà installé avec matplotlib) | rapide, robuste |
| Fréquence de calcul | à la demande, avec cache ; au plus ~7 fois/s pendant la lecture, immédiat à l'arrêt | la vue est redessinée 40 fois/s |

## Faits établis (vérifiés le 2026-10-07)

- Avec `frames.lagrange_points` et Φ_eff(p) = −G m₁/r₁ − G m₂/r₂ − ½ ω² \|p\|² (origine au barycentre, m₁ sur −x,
  ω² = G (m₁ + m₂)/d³) : gradient relatif aux cinq points < 10⁻⁸ ; L1, L2, L3 = cols (valeurs propres de la
  hessienne de signes opposés), L4, L5 = maxima (deux valeurs propres négatives).
- Soleil–Jupiter (d = 5,2 UA, G = 4π²) : Φ_eff(L1) = −11,54616 < Φ_eff(L2) = −11,54132 < Φ_eff(L3) = −11,40250
  < Φ_eff(L4) = Φ_eff(L5) = −11,39526.
- Binaire 1 + 0,8 M☉, d = 1 UA : Φ_eff(L1) = −141,915 ; L2 = −124,134 ; L3 = −121,342 ; L4 = L5 = −97,819.
- `contourpy` 1.3.3 disponible : 12 niveaux sur 200×200 en 50 ms (bruit aléatoire, pire cas ; un champ lisse est
  bien plus rapide). Carte de potentiel 200×200 avec 10 corps : 2,3 ms.

## Conventions du projet (à respecter)

- Code et docstrings en anglais, interface et documentation en français.
- `gravsim/core` et `gravsim/analysis` n'importent **jamais** Qt (un test le vérifie).
- Tests : `conda run -n gravsim python -m pytest -q` (tout doit rester vert, ~210 tests) ; tests d'interface
  hors écran (`QT_QPA_PLATFORM=offscreen`, déjà réglé dans `tests/conftest.py`), et **chaque état dessiné doit
  être rendu avec `grab()`** (c'est au moment de peindre que Qt plante, voir l'historique : une légende à qui
  l'on donnait une `InfiniteLine`).
- Ne jamais passer une `InfiniteLine` à une légende pyqtgraph.
- En mode log de pyqtgraph, les données des courbes sont transformées, pas les `InfiniteLine` ni les `TextItem`.
- Fin de travail : commit (attribution indiquée par le système), régénérer l'exécutable et donner les commandes
  macOS et Windows (voir la mémoire du projet).

---

## Étape 1 — Module de calcul `gravsim/analysis/potential.py` (sans Qt)

```python
@dataclass
class PairFrame:
    center: np.ndarray      # (2,) barycentre of the pair, inertial
    velocity: np.ndarray    # (2,) velocity of that barycentre
    angle: float            # direction a -> b (rad)
    omega: float            # (dr x dv) / |dr|^2, signed (rad/yr)
    separation: float       # |r_b - r_a|

def gravitational_potential(points, positions, masses, G, radii=None) -> np.ndarray
    """Phi at points (..., 2): -sum G m_i / |p - r_i|; inside a body (|p - r_i| < R_i) the homogeneous-sphere
    value -G m_i (3 R_i^2 - r^2) / (2 R_i^3), the same law as core/forces.py. Massless bodies contribute nothing."""

def pair_frame(positions, velocities, masses, a: int, b: int) -> PairFrame
    """Raises ValueError if a == b or m_a + m_b == 0 or the bodies coincide."""

def effective_potential(points, positions, masses, G, frame: PairFrame, radii=None) -> np.ndarray
    """Phi(points) - 0.5 * omega^2 * |points - center|^2."""

def lagrange_points_inertial(positions, velocities, masses, a, b) -> dict[str, np.ndarray]
    """L1..L5 in the inertial frame at this instant: frames.lagrange_points(m_a, m_b, separation) (rotating
    coordinates, origin at the barycentre, a on -x), rotated by frame.angle, translated by frame.center.
    ValueError if m_a or m_b is zero (no Lagrange points for a massless partner)."""

def critical_levels(positions, masses, G, frame, lagrange: dict, radii=None) -> dict[str, float]
    """Phi_eff at L1, L2, L3 (zero-velocity curves through the collinear points; L1 = Roche lobe)."""

def zero_velocity_level(r, v, positions, masses, G, frame, radii=None) -> float
    """Phi_eff(r) + 0.5 |v'|^2 with v' = v - frame.velocity - omega x (r - center) (velocity in the rotating
    frame): the body can only reach the region Phi_eff <= this level (Jacobi, restricted problem)."""
```

Rotation : la position dans le repère tournant p' s'obtient par p = c + R(angle)·p', avec
R(θ) = [[cos θ, −sin θ], [sin θ, cos θ]] (l'inverse de `viewer._rotate`, qui applique R(−θ)).

**Tests** (`tests/test_potential.py`) :

1. −∇Φ par différences centrées = accélération donnée par `GravityModel` pour une particule test (masse 0)
   ajoutée au même point, à 10⁻⁶ près, hors des corps ; à l'intérieur d'un corps de rayon R, idem avec la loi de
   la sphère homogène.
2. Pour Soleil–Jupiter et la binaire (deux corps seuls, orbite circulaire), aux cinq points :
   \|∇Φ_eff\| < 10⁻⁶ × G (m₁ + m₂)/d².
3. Hessienne : L1, L2, L3 cols ; L4, L5 maxima.
4. Ordre et valeurs : celles des « Faits établis » (à 10⁻⁴ près).
5. Preset `troyens` à t = 0 : L4 et L5 inertiels = positions des corps « Troyen L4 » et « Troyen L5 » (10⁻⁶ UA).
6. Preset `binaire` simulé 3 ans (DOP853, rtol 1e-12) : L1…L5 ramenés dans le référentiel tournant
   (`frames.rotating`) restent fixes (écart < 10⁻⁶ UA).
7. Particule test dans Soleil–Jupiter (comme `test_jacobi_constant_conserved`) : `zero_velocity_level` constant
   dans le temps à 10⁻⁸ près (c'est −C/2, C = constante de Jacobi).
8. Erreurs : même corps, partenaire sans masse → `ValueError`.

## Étape 2 — Réglages (`gravsim/gui/widgets.py`, classe `ViewSettings`)

Nouveaux champs :

```python
self.show_lagrange = False
self.lagrange_follow_frame = True   # use the rotating frame's pair when that frame is active
self.lagrange_pair = (0, 1)         # indices (primary, secondary) otherwise
self.field = "none"                 # "none" | "potential" | "effective"
self.field_contours = True
self.field_critical = True          # zero-velocity curves through L1, L2, L3
self.field_accessible = False       # step 6: region accessible to the selected body
self.field_resolution = 160         # grid points along the longer side
```

Règle de choix de la paire (fonction `lagrange_pair(view, scenario) -> (a, b) | None` dans `viewer.py`, à côté
de `frame_spec`) : si `lagrange_follow_frame` et référentiel tournant valide → sa paire ; sinon
`lagrange_pair` si valide ; à défaut les deux corps les plus massifs ; `None` s'il y a moins de deux corps massifs.

## Étape 3 — Panneau (`gravsim/gui/view_panel.py`, classe `ViewPanel`)

Nouveau groupe **« Points de Lagrange et potentiel »**, sous « Référentiel et cadrage » :

- case *Points de Lagrange* ;
- case *Suivre la paire du référentiel tournant* + combos *Primaire* / *Secondaire* (grisés quand la case est
  cochée et que le référentiel est tournant) ;
- combo *Fond* : « Aucun », « Potentiel gravitationnel », « Potentiel effectif (référentiel tournant) » ;
- cases *Lignes de niveau*, *Courbes critiques L1, L2, L3*, *Région accessible du corps sélectionné* ;
- une ligne d'information (`QLabel`) : distance de L1 et L2 au secondaire et rappel « exact pour une orbite
  circulaire » si l'excentricité instantanée de la paire dépasse 0,05 ; « effectif : à regarder dans le
  référentiel tournant » si le fond effectif est choisi hors référentiel tournant.

Mêmes mécanismes que l'existant : `_refill_bodies` recharge les combos, `_on_any` recopie dans `ViewSettings`
puis `notify()`.

## Étape 4 — Dessin (`gravsim/gui/viewer.py`, classe `SimViewer`)

Nouveaux éléments (créés dans `__init__`, ordre de superposition par `setZValue`) :

| Élément | Type | z |
|---|---|---|
| `field_image` | `pg.ImageItem`, opacité 0,75 | −10 |
| `field_contours` | `pg.PlotCurveItem(connect="finite")`, gris fin | −5 |
| `field_critical` | 3 `PlotCurveItem` (L1 rouge `#ff5c5c`, L2 orange `#ffb454`, L3 jaune `#ffd166`), épaisseur 1,6 | −4 |
| `field_accessible` | `PlotCurveItem` blanc pointillé | −4 |
| `lagrange_points` | `ScatterPlotItem`, symbole « x », blanc, 12 px | 25 |
| `lagrange_labels` | 5 `pg.TextItem` « L1 »…« L5 » | 26 |

Dans `_redraw`, après le calcul de `inertial`, `angle`, `origin` (déjà présents), et avec la vitesse inertielle à
l'instant affiché `inertial_vel = blend(win.vel)` :

1. **Points de Lagrange** (si `show_lagrange` et paire valide) : `lagrange_points_inertial(inertial, inertial_vel,
   masses, a, b)` puis passage en coordonnées affichées : `_rotate(L - origin, angle)`. Étiquettes décalées de
   ~8 px (utiliser `px_world`, comme pour les noms des corps).
2. **Fond** (si `field != "none"`), dans une méthode `_draw_field(...)` :
   - grille sur `self.vb.viewRange()` en coordonnées affichées : `n` points sur le grand côté
     (`field_resolution`), autant de pixels-monde sur l'autre (aspect verrouillé) ;
   - passage en inertiel : p_inertiel = origin + R(angle)·p_affiché ;
   - `gravitational_potential` ou `effective_potential` (paire requise ; sinon ne rien dessiner et indiquer
     pourquoi dans la ligne d'information du panneau) ;
   - échelle de couleurs selon les « Décisions » ; `field_image.setImage(valeurs, levels=(lo, hi))` avec
     `setColorMap(pg.colormap.get("magma"|"viridis"))` et `setRect(QRectF(x0, y0, largeur, hauteur))` (même
     convention d'axes que le spectrogramme de `spectral_tab.py` : le premier indice est x) ;
   - lignes de niveau : `contourpy.contour_generator(x=xs, y=ys, z=valeurs.T)`, 10 niveaux régulièrement espacés
     dans [lo, hi] ; concaténer les lignes avec des NaN entre elles ;
   - courbes critiques (fond effectif) : niveaux `critical_levels(...)` pour L1, L2, L3 ;
   - **cache** : clé = (plage de vue arrondie, instant affiché, référentiel, mode, paire, résolution, options) ;
     ne recalculer que si la clé change, et pendant la lecture (`ctrl.playing`) pas plus d'une fois toutes les
     0,15 s (garder l'image précédente entre-temps) ; à l'arrêt, recalcul immédiat.
3. Effacer ces éléments quand l'option est désactivée (comme `_clear` pour les autres).

## Étape 5 — Documentation et vérification de l'exécutable

- `docs/GUIDE_UTILISATEUR.md`, section 6 : paragraphe « Points de Lagrange et potentiel », avec l'exercice :
  preset *Troyens*, référentiel tournant Soleil–Jupiter, fond « potentiel effectif », courbes critiques : les
  troyens restent au **sommet** des collines L4 et L5 (stables grâce à la force de Coriolis, pas au fond d'un
  creux), et la courbe de L1 dessine le lobe de Roche de Jupiter. Second exercice : preset *Étoile binaire* :
  la courbe critique L1 forme un « 8 » autour des deux étoiles.
- `gravsim/gui/help_dialog.py` : une ligne dans « Regarder ».
- `README.md` : mention dans la liste des fonctions de la vue.
- `MainWindow._autotest` : activer Lagrange + les deux fonds (potentiel, effectif) sur `troyens`, puis `grab()` :
  l'exécutable autonome doit embarquer `contourpy` (sinon ajouter `--hidden-import contourpy` dans
  `scripts/construire_executable.py`).

## Étape 6 (optionnelle) — Région accessible du corps sélectionné

Si `field_accessible` et fond effectif : niveau `zero_velocity_level(r_sel, v_sel, ...)` du corps sélectionné,
tracé en blanc pointillé ; la région où Φ_eff > niveau (interdite) peut être assombrie (deuxième `ImageItem` semi-
transparent, ou simplement le contour). Légende dans la ligne d'information : « région accessible de X (Jacobi) ».
Rappel affiché : exact seulement pour une particule test et une paire circulaire.

## Étape 7 — Tests d'interface (`tests/test_gui_potential.py`)

1. Chaque combinaison (Lagrange on/off × fond aucun/potentiel/effectif × contours on/off × référentiel inertiel/
   tournant) se dessine sans erreur : `grab()` non nul.
2. Preset `troyens`, référentiel tournant Soleil–Jupiter : les 5 marqueurs existent ; L4 et L5 coïncident avec
   les troyens affichés (à quelques 10⁻³ UA, ils librent) ; après avoir avancé de 10 ans, les marqueurs n'ont pas
   bougé (écart < 10⁻³ UA).
3. Fond effectif sur la binaire : l'image a des niveaux finis, `lo < hi` ; la courbe critique L1 contient des
   points (non vide).
4. Paire invalide (même corps, ou un seul corps massif) : aucun marqueur, aucun plantage, message dans la ligne
   d'information.
5. Performance : sur `systeme_solaire` (9 corps), un recalcul complet du fond en résolution 160 prend < 100 ms ;
   pendant 1 s de lecture simulée (40 ticks), le fond n'est pas recalculé plus de 8 fois.
6. `_autotest` toujours OK.

## Critères d'acceptation

- Tous les tests verts (anciens + nouveaux), sans avertissement numérique (`-W error::RuntimeWarning`).
- Captures vérifiées à l'œil : troyens sur les maxima L4/L5 ; lobe de Roche de Jupiter fermé par L1 ; « 8 »
  critique de la binaire ; carte de potentiel lisible (pas uniforme) avec le système solaire.
- Exécutable reconstruit, `--autotest` OK (code 0).

## Risques et parades

| Risque | Parade |
|---|---|
| Potentiel qui diverge près des masses → image uniforme | écrêtage (percentiles / niveaux critiques), échelle log pour Φ |
| Fond effectif incompréhensible hors référentiel tournant | message dans le panneau ; le guide recommande le référentiel tournant |
| Lenteur pendant la lecture | cache + limitation à ~7 calculs/s ; résolution réglable |
| Paire excentrique | séparation instantanée ; mention « exact pour une orbite circulaire » |
| `contourpy` absent de l'exécutable | l'autotest le détecte ; `--hidden-import contourpy` |
| Orientation de l'image (axes inversés) | même convention que le spectrogramme ; test 2 (marqueurs sur les troyens) et capture d'écran |

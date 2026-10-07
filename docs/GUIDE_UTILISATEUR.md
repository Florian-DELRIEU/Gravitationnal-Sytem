# Guide d'utilisation — Simulateur gravitationnel 2D

Ce guide part de zéro : lancer le logiciel, construire un système, l'observer, puis compter les planètes d'une
étoile à partir de son seul mouvement. Les termes techniques sont expliqués au passage.

---

## 1. Lancer le logiciel

| Situation | Comment |
|---|---|
| Application autonome (Mac) | double-clic sur `dist/Simulateur Gravitationnel.app` |
| Application autonome (Windows) | double-clic sur `dist\Simulateur Gravitationnel\Simulateur Gravitationnel.exe` (garder le dossier entier) |
| Lanceur léger (Mac, avec l'environnement conda) | double-clic sur `Simulateur Gravitationnel.app` à la racine du projet |
| Lanceur léger (Windows, avec conda) | `windows\Lancer le simulateur.bat` |
| Terminal | `conda activate gravsim` puis `gravsim` |

Régénérer l'application autonome après une mise à jour du code :

```bash
python scripts/construire_executable.py
```

(sous Windows : `windows\Construire l'executable (Windows).bat`). L'application accepte `--autotest` : elle
vérifie seule les presets, les intégrateurs, l'analyse, le spectre et la détection, puis s'arrête (code 0 = tout va bien).

---

## 2. Premier tour (5 minutes)

1. Au démarrage, le preset **Soleil – Jupiter** est chargé. Appuyez sur **Espace** (ou *▶ Lecture*).
2. Le curseur **Vitesse** règle combien de temps simulé s'écoule par seconde réelle. Si le calcul ne suit pas,
   la barre d'état affiche « vitesse réelle … (limitée par le calcul) ».
3. **Clic sur un corps** pour le sélectionner : ses propriétés s'affichent à droite (onglet *Corps*), son état
   en bas à gauche (position, vitesse, orbite autour du corps qui l'attire le plus).
4. **Molette** pour zoomer, **glisser** pour déplacer. Le cadrage repasse alors en « Libre » ; remettez
   « Tout voir » dans l'onglet *Vue* pour revenir au cadrage automatique.
5. Le long curseur sous la vue remonte dans le temps sur ce qui a déjà été calculé (« relecture ») ;
   *⇥ Direct* (touche **L**) revient au dernier instant.
6. Menu **Presets** : essayez *Système solaire*, *Couple résonant 2:1*, *Troyens de Jupiter*, *Chorégraphie en huit*.

Raccourcis : **Espace** lecture/pause · **S** un pas · **R** réinitialiser · **L** direct · **F1** guide rapide.

---

## 3. Construire un système

Panneau de gauche : la liste des corps (*＋ Ajouter*, *Dupliquer*, *Supprimer*). Un nouveau corps est placé
au-delà des autres, déjà sur une orbite circulaire autour du plus massif.

Onglet **Corps** (à droite), pour le corps sélectionné :

- **Masse** et **rayon**, avec choix d'unité (M☉, M_Jup, M⊕, M_Lune ; R☉, R_Jup, R⊕, km, UA). Le bouton
  *depuis la densité…* calcule le rayon d'une sphère homogène (Terre 5,5 g/cm³, Jupiter 1,3, Soleil 1,4).
  Le rayon sert aux collisions ; il n'influence pas la gravité tant que les corps ne se touchent pas.
- **Masse nulle** = *particule test* : elle subit la gravité sans en exercer (astéroïde, sonde).
- **Corps fixe** : il attire les autres mais ne bouge jamais. Pratique pour un exercice « Soleil immobile ».
  Attention : la quantité de mouvement totale n'est alors plus conservée.
- **Position** (x, y) et **vitesse** : soit *norme + direction* (en degrés, sens antihoraire depuis l'axe x),
  soit *composantes vx, vy*. Les deux restent synchronisées ; l'unité (UA/an, km/s, m/s) est au choix.
- **Vitesse orbitale automatique** : choisissez le corps central, l'excentricité, si la position actuelle est le
  périastre (point le plus proche) ou l'apoastre (le plus lointain) et le sens. *Appliquer* donne la vitesse
  exacte du problème à deux corps. *Vitesse de libération* donne la vitesse minimale pour s'échapper (orbite
  parabolique). Avec plus de deux corps, c'est une approximation : les autres corps perturbent.

Boutons sous la liste :

- **Annuler la quantité de mouvement totale** : retire la vitesse d'ensemble du système. Sans cela, tout le
  système dérive lentement. Indispensable avant une analyse spectrale soignée.
- **Centrer le système sur le barycentre** : place le centre de masse à l'origine.

**Enregistrer / ouvrir** : menu *Fichier*. Le format (JSON lisible) est décrit dans
[FORMAT_SCENARIO.md](FORMAT_SCENARIO.md) : on peut aussi écrire ses scénarios à la main.

> Toute modification des conditions initiales réinitialise la simulation (sauf la couleur et la taille affichée).

---

## 4. Poussées (changer la vitesse d'un corps)

Onglet **Poussées** : une poussée est une variation instantanée de vitesse Δv, **signée** :

- *prograde / rétrograde* : le long de la vitesse du corps **par rapport à la référence** (Δv > 0 accélère,
  Δv < 0 freine) ;
- *radiale* : le long de la ligne référence → corps (Δv > 0 éloigne, Δv < 0 rapproche) ;
- *angle absolu* : dans une direction fixe du plan.

*Appliquer maintenant* agit à l'instant affiché ; *Programmer à t* agit à un instant futur exact (la simulation
s'arrête pile à cet instant). Une poussée dans le passé est ajoutée au scénario et la simulation est rejouée.
L'énergie apportée est comptée à part : la jauge de fidélité ne la confond pas avec une erreur de calcul.

Exemple : une poussée prograde au périastre allonge l'orbite (manœuvre de transfert) ; rétrograde, elle la
rapproche.

---

## 5. Collisions

Deux corps entrent en collision quand leur distance devient inférieure à la somme de leurs rayons. La détection
fonctionne même si le contact a lieu entre deux pas de calcul. Un bandeau rouge et le journal le signalent.

- Case **Pause à la collision** : la simulation s'arrête exactement au contact.
- Il n'y a pas de fusion : si on continue, les corps se traversent (la gravité entre eux suit alors la loi d'une
  sphère homogène, sans singularité). Un anneau rouge marque les corps qui se recouvrent.

Preset de démonstration : *Collision frontale*.

---

## 6. Affichage (onglet *Vue*)

- **Taille des corps** : *selon la masse* (compressée, pour que tout reste visible), *manuelle* (champ « taille
  affichée » de chaque corps) ou *échelle réelle* (les rayons vrais : à l'échelle d'un système planétaire, tout
  devient minuscule, ce qui est la réalité).
- **Référentiel** (le point de vue d'où l'on regarde ; la physique, elle, ne change pas) :
  - *inertiel* : le repère fixe de la simulation ;
  - *barycentrique* : centré sur le centre de masse, immobile si le système est isolé ;
  - *centré sur un corps* : comme vu depuis ce corps (la Lune vue depuis la Terre) ;
  - *tournant avec une paire* : tourne avec la droite qui joint deux corps (Soleil–Jupiter). Les points de
    Lagrange et les troyens y deviennent immobiles.
- **Cadrage** : tout voir, libre, ou suivre un corps.
- **Vecteurs vitesse et force**, **barycentre**, **sphères de Hill** (zone où la gravité d'une planète domine
  celle de son étoile), **traînées** (longueur réglable).

Le référentiel choisi s'applique aussi aux graphes de l'onglet *Analyse* et à l'export CSV.

### Points de Lagrange et potentiel

Le groupe **Points de Lagrange et potentiel** de l'onglet *Vue* superpose à la simulation :

- **Points de Lagrange (L1 à L5)** d'une paire de corps (marqueurs ✕ étiquetés). La paire est celle du
  référentiel tournant si la case *Suivre la paire du référentiel tournant* est cochée ; sinon on choisit
  *Primaire* et *Secondaire* ; à défaut, ce sont les deux corps les plus massifs. Les positions sont celles du
  problème à deux corps pour la séparation *instantanée* : exactes si la paire est en orbite circulaire,
  approchées sinon (l'application le signale quand l'excentricité dépasse 0,05).
- Un **fond** colorant le plan :
  - *potentiel gravitationnel* Φ de tous les corps : le « paysage » de gravité (clair = puits profond, échelle
    logarithmique, écrêtée pour que la carte reste lisible) ;
  - *potentiel effectif* Φ_eff : gravité de tous les corps **plus** l'effet centrifuge dans le référentiel
    tournant avec la paire. C'est le relief qu'un petit corps « ressent » dans ce repère : L1, L2, L3 y sont des
    **cols**, L4 et L5 des **sommets**. À regarder dans le référentiel tournant (l'application le rappelle sinon).
- des **lignes de niveau**, et les **courbes critiques** passant par L1 (rouge), L2 (orange) et L3 (jaune) ;
  celle de L1 est le **lobe de Roche**.
- la **région accessible** du corps sélectionné (pointillé blanc) : un corps d'énergie de Jacobi donnée ne peut pas
  franchir la courbe de Φ_eff égale à cette valeur (exact pour une particule test et une paire circulaire).

**Exercice 1 — pourquoi les troyens tiennent.** Preset *Troyens de Jupiter*, référentiel *tournant avec une paire*
(Soleil, Jupiter), fond *potentiel effectif*, courbes critiques cochées. Les deux astéroïdes sont **au sommet** des
collines L4 et L5, pas au fond d'un creux : ils sont stables grâce à la force de Coriolis, pas à cause d'un
minimum de potentiel. La courbe rouge de L1 dessine le lobe de Roche de Jupiter.

**Exercice 2 — l'étoile binaire.** Preset *Étoile binaire*, mêmes réglages : la courbe critique de L1 forme un
« 8 » autour des deux étoiles ; une étoile qui déborde de son lobe déverse de la matière par L1.

Le calcul de la carte est refait à la demande (jusqu'à environ 7 fois par seconde pendant la lecture).

---

## 7. Intégrateurs et fidélité (onglet *Intégration*)

L'intégrateur est la méthode qui fait avancer le temps.

| Intégrateur | Quand l'utiliser |
|---|---|
| **DOP853** (défaut) | Précision maximale, pas adaptatif : rencontres proches, collisions, études soignées |
| **Yoshida 4** | Longues durées (siècles) : l'énergie ne dérive pas, même après des milliers d'orbites |
| **Leapfrog** | Le plus rapide ; demande un pas plus petit pour la même précision |

Le **pas conseillé** est calculé automatiquement (au plus 1/200 de la période la plus courte, et plus fin près
d'un périastre serré).

La **jauge de fidélité** (barre d'état, `ΔE/E`) mesure de combien l'énergie totale a dérivé, poussées exclues.
Dans un système isolé, elle devrait rester nulle : sa valeur est donc l'erreur numérique.

- vert (< 10⁻⁶) : excellent ; orange (< 10⁻³) : correct pour visualiser ; rouge : réduire le pas, ou passer en DOP853.

---

## 8. Analyse (onglet central *Analyse*)

Cinq onglets de graphes, mis à jour pendant la simulation (environ une fois par seconde) :

- **Distances** entre les paires cochées, avec minimum, maximum (et quand) et valeur actuelle ;
- **Vitesses** : norme, composantes, ou vitesse relative à un corps (UA/an ou km/s) ;
- **Positions** : x(t), y(t), distance à l'origine du référentiel, ou trajectoire x–y ;
- **Énergie et conservation** : énergies cinétique, potentielle, totale, et dérives relatives de l'énergie, du
  moment cinétique et de la quantité de mouvement ;
- **Éléments orbitaux** d'un corps autour d'un autre : demi-grand axe, périastre, apoastre, excentricité,
  argument du périastre, avec le type d'orbite (liée ou non), la masse réduite et la vitesse de libération.

Les collisions (traits rouges) et les poussées (pointillés orange) sont marquées sur les graphes.
**Export** : *Fichier → Exporter l'analyse (.csv)* (tableur) ; *Exporter la trajectoire (.npz)* (Python).

---

## 9. Spectre : observer une étoile

Une planète fait tourner son étoile autour de leur centre de masse commun. Ce petit mouvement **réflexe** est
ce que mesurent les astronomes :

- en **vitesse radiale** (m/s) : la vitesse de l'étoile le long de la ligne de visée, par effet Doppler ;
- en **astrométrie** : la position de l'étoile dans le ciel (ici z = x + iy, vue de face).

Chaque planète ajoute une oscillation de période égale à la sienne. Le **spectre** décompose le signal en
fréquences : un pic par planète, à sa période, de hauteur égale à son amplitude.

Marche à suivre (onglet central **Spectre**) :

1. Choisissez le **corps observé** (l'étoile) et le **signal**.
2. *Compléter (6 × P max)* : simule assez longtemps pour couvrir 6 orbites de la planète la plus lente
   (en dessous de 3, les pics sont flous).
3. **Échantillonnage** : *régulier* (une mesure à pas fixe, FFT) ou *irrégulier* (des nuits d'observation au
   hasard, avec une saison où l'étoile est inobservable, méthode de Lomb-Scargle). Ajoutez du **bruit** pour être
   réaliste : 1 m/s pour un bon spectrographe (HARPS), 0,1 à 0,3 m/s pour le meilleur (ESPRESSO), plus 1 à 3 m/s
   d'activité pour une étoile calme. En astrométrie, à 10 parsecs, 1 µas ≈ 10⁻⁵ UA : Gaia mesure à environ
   50–100 µas près par passage, soit σ ≈ 500–1000 (× 10⁻⁶ UA).
4. **Ligne de visée** et **inclinaison** (vitesse radiale) : à 90° on voit l'orbite par la tranche ; plus on
   s'approche de 0° (vue de face), plus le signal s'affaiblit (facteur sin i). On mesure donc m sin i.
5. *Calculer le spectre*. Les planètes réelles sont repérées (traits pleins) avec leurs harmoniques 2f et 3f
   (pointillés) ; les pics sont numérotés et identifiés dans *Pics et planètes*.

Ce que l'on rencontre dans un spectre :

- **Harmoniques** (2f, 3f…) : une orbite excentrique n'est pas une sinusoïde pure ; elle produit des pics aux
  multiples de sa fréquence. Ce ne sont pas des planètes.
- **Lobes secondaires** : de petits pics de part et d'autre d'un pic fort (effet de la fenêtre d'observation).
- **Alias annuels** : avec des saisons d'observation, de faux pics à ±1 cycle/an d'un vrai.
- **AMBIGU** : deux explications tiennent (voir plus bas).
- **Spectrogramme** : le spectre sur une fenêtre glissante, pour voir si les fréquences dérivent au cours du
  temps (planètes en interaction).

---

## 10. Détection : combien de planètes ?

Sous-onglet **Détection** de la page *Spectre*, bouton *Détecter les planètes*. La détection est **aveugle** :
elle ne voit que les observations. Les vraies planètes ne servent qu'à noter le résultat (colonne
*Planète réelle*).

Ce qu'elle fait, étape par étape (tableau *Étapes*) : elle prend le pic le plus fort, ajuste une orbite
complète (période, amplitude, excentricité…), le retire, et recommence sur ce qui reste. Elle s'arrête quand le
pic suivant n'est plus significatif (probabilité de fausse alarme), trop faible, ou n'améliore plus assez le
modèle (critère BIC).

Lire le résultat :

- **« 2 planètes détectées »** avec, pour chacune, période, amplitude K, excentricité e, argument du périastre ω,
  masse (m sin i en vitesse radiale) et demi-grand axe a.
- **Signaux non planétaires** : des signaux réels mais qui ne sont pas des planètes — combinaisons de
  fréquences, libération d'une résonance, orbite qui évolue sous les interactions, tendance plus longue que
  l'observation. Ils sont ajustés (pour nettoyer les résidus) mais pas comptés.
- **« 1 ou 2 planètes (AMBIGU) »** : une planète excentrique et deux planètes en résonance 2:1 produisent
  presque le même signal. Si les données ne permettent pas de trancher (le terme qui les distingue, à 3f, est
  noyé dans le bruit), le logiciel le dit au lieu de choisir au hasard. Avec des données plus précises ou plus
  longues, l'ambiguïté disparaît.
- **Non retrouvée(s)** : une planète réelle dont le signal est trop faible. Repère : on retrouve presque toutes
  les planètes dont le **rapport signal/bruit** K/σ·√(N/2) dépasse 10, et presque aucune sous 5 (N = nombre
  d'observations).

Réglages : *FAP max* (10⁻³), *ΔBIC min* (10), *planètes max*, *plancher* (0,1 % de la planète la plus forte).
Les valeurs par défaut ont été validées sur 120 systèmes aléatoires sans aucune fausse détection
([RESULTATS_JALON5.md](RESULTATS_JALON5.md)).

Limite à connaître : sur des données **sans bruit** d'un système en **forte interaction** (couple résonant),
l'ajustement par orbites fixes laisse des signaux réels ; ils sont classés non planétaires, et une petite planète
qui tomberait exactement à ces fréquences serait signalée « possible » plutôt que comptée.

Exercice conseillé, preset *Trois planètes*, *Compléter*, échantillonnage irrégulier, saison 0,3 :

1. **150 observations, bruit 1 m/s** (un bon spectrographe), *Calculer* puis *Détecter* : **3 planètes**, avec
   leurs masses à quelques pour cent près.
2. **100 observations, bruit 3 m/s** : selon le tirage (changez la *graine du hasard*), on obtient 3 planètes ou
   **« 3 ou 4 planètes (AMBIGU) »** : la légère excentricité (e = 0,08) de la planète extérieure ne se distingue
   plus d'une quatrième planète en résonance 2:1, car le terme qui les sépare est noyé dans le bruit. C'est
   exactement le piège que rencontrent les astronomes.
3. **Bruit 30 puis 60 m/s** : les planètes les plus faibles disparaissent (« non retrouvée ») — leur rapport
   signal/bruit est passé sous 5 à 10.

---

## 11. Études sans interface

```bash
python scripts/etude_spectre.py systeme_solaire          # spectres + détection aveugle d'un preset
python scripts/etude_spectre.py --tous
python scripts/campagne_detection.py --systemes 120      # validation statistique de la détection
```

Exemple en Python :

```python
from gravsim.core.scenario import load_preset
from gravsim.core.simulation import Simulation
from gravsim.analysis import observer
from gravsim.analysis.detection import detect_observations

sim = Simulation(load_preset("trois_planetes"), "dop853", output_dt=0.002)
sim.run(10.0)
times = observer.random_schedule(0, 10, 150, rng=1, season_fraction=0.3)
obs = observer.observe_rv(sim.trajectory, "Étoile", times, sigma=1.0, rng=2)
result = detect_observations(obs, star_mass=1.0)
print(result.count_text())                      # 3 planètes détectées
for p in result.planets:
    print(p.period, p.amplitude, p.e, p.mass_mjup)
```

---

## 12. Les presets

| Preset | À essayer |
|---|---|
| Soleil – Jupiter | le cas de référence : K = 12,5 m/s, P = 11,9 ans |
| Système solaire (2D) | détection aveugle sur 1000 ans : 6 planètes retrouvées |
| Jupiter chaud | une planète en 4 jours : signal fort et rapide |
| Trois planètes | le cas d'école de la détection |
| Couple résonant 2:1 | planètes en interaction forte, signaux non planétaires |
| Planète excentrique | le pendant du couple 2:1 : comparez leurs spectres |
| Troyens de Jupiter | points de Lagrange L4/L5, en référentiel tournant |
| Chorégraphie en huit | trois étoiles sur une même courbe : test de fidélité |
| Soleil – Terre – Lune | système hiérarchique, vue centrée sur la Terre |
| Terre – Lune | la Lune seule autour de la Terre |
| Étoile binaire | deux étoiles, référentiel tournant |
| Planète circumbinaire | une planète autour de deux étoiles (Tatooine) |
| Collision frontale | collision détectée, pause au contact |
| Soleil fixe, Terre et comète | corps fixe et particule test |

---

## 13. Dépannage

| Problème | Solution |
|---|---|
| L'application ne s'ouvre pas (lanceur léger) | voir `~/Library/Logs/gravsim.log` ; recréer le lanceur (`python scripts/creer_app.py`) |
| macOS bloque l'application | clic droit → *Ouvrir* la première fois |
| « vitesse réelle … limitée par le calcul » | baisser la vitesse, ou passer en Yoshida/leapfrog pour les longues durées |
| `ΔE/E` orange ou rouge | réduire le pas (onglet *Intégration*) ou utiliser DOP853 |
| « Trajectoire trop longue » | réinitialiser (R) ; augmenter le pas d'échantillonnage |
| Spectre : « une poussée a lieu dans l'intervalle » | commencer l'observation après la poussée (*Valeurs conseillées*) |
| Spectre : « trajectoire trop courte » | simuler plus longtemps (*Compléter*) |
| Pas de vitesse radiale | inclinaison 0° = vue de face : utiliser l'astrométrie |

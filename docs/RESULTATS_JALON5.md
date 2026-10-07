# Jalon 5 : détection des planètes — méthode et résultats

Module : `gravsim/analysis/detection.py` (détection), `gravsim/analysis/campaign.py` (campagne par injection).
Interface : onglet **Spectre → Détection**. Scripts : `scripts/campagne_detection.py`, et la détection est
affichée par `scripts/etude_spectre.py`.

## La méthode, en bref

La détection est **aveugle** : elle ne voit que les observations (temps, valeurs, incertitudes). Les vraies
planètes ne servent qu'après coup, à noter le résultat.

1. **Extraction itérative** : le pic le plus fort du périodogramme des résidus est un candidat. On l'ajoute
   au modèle, on réajuste **toutes** les orbites ensemble (orbites képlériennes complètes : P, K, e, ω,
   longitude moyenne), puis on recommence sur les nouveaux résidus.
2. **Trois conditions pour garder un candidat** : probabilité de fausse alarme < 10⁻³, amplitude au-dessus de
   0,1 % de la planète la plus forte, et **gain de BIC > 10** (preuve « très forte »).
3. **Harmoniques** : un pic à 2f, 3f, 4f d'une planète connue est d'abord expliqué par une meilleure
   excentricité de cette planète ; à 2f, la lecture « couple résonant 2:1 » est ajustée aussi. Le meilleur
   BIC l'emporte.
4. **Signaux non planétaires** : combinaisons de fréquences (a·f₁ + b·f₂), fréquences lentes d'un couple
   proche d'une résonance (libration), pics à moins de 1/T d'une composante connue (modulation, non résolu),
   périodes plus longues que l'observation (tendance), et harmoniques faibles d'une planète qui a une voisine
   avec qui interagir (masse impliquée < 25 %). Ils sont ajustés pour nettoyer les résidus mais **pas comptés**.
5. **Ambiguïté** : chaque couple 2:1 est comparé à une planète excentrique seule, et chaque planète
   excentrique dont le signal à 2f est significatif à un couple 2:1 circulaire. Si aucune lecture n'est
   « fortement » favorisée (ΔBIC < 6), le résultat dit **« 1 ou 2 planètes (AMBIGU) »** au lieu de choisir.
6. **Masses** : m sin i à partir de K, de P, de e et de la masse de l'étoile (supposée connue, comme pour un
   astronome qui la tire de la spectroscopie) ; masse vraie en astrométrie vue de face.

## Tests de validation (cahier des charges, section 6)

| # | Test | Résultat |
|---|---|---|
| T10 | Planète excentrique (e = 0,5 et 0,2 ; preset e = 0,4) | 1 planète, e retrouvée à 0,002 près, K à 0,1 %, masse à 0,2 % |
| T11 | Trois planètes séparées, sans bruit et avec 2 m/s / 200 obs. | 3 planètes, P à 0,5 %, K à 3 %, e à 0,02 |
| T12 | Couple 2:1 contre planète excentrique | voir ci-dessous |
| T13 | Campagne par injection | voir ci-dessous |

### T12 : ce que l'on a appris (et qui corrige le cahier des charges)

Le cahier des charges demandait « ambiguïté signalée dans les deux cas ». La réalité est plus intéressante :

- **Avec de bonnes données (sans bruit)**, les deux cas sont **correctement distingués** : la planète excentrique
  donne 1 planète, le couple 2:1 donne 2 planètes, sans ambiguïté. La dégénérescence n'existe qu'au premier
  ordre en e ; les termes d'ordre supérieur (harmonique 3f ∝ e²) la lèvent.
- **Avec du bruit qui cache ces termes** (2f clairement significatif, 3f noyé), le vrai nombre fait **toujours
  partie des réponses possibles**, et l'ambiguïté est signalée dans la majorité des tirages (test statistique
  sur 5 réalisations du bruit). Pour une vraie planète excentrique, le modèle exact est un peu favorisé dans
  une partie des tirages : c'est attendu, il colle exactement aux données.

### Le couple résonant GJ 876 (preset `resonance_2_1`)

Les deux planètes interagissent fortement : l'orbite de c évolue visiblement en quelques mois. Des orbites
képlériennes fixes laissent donc des **signaux réels** dans les résidus (harmoniques de c qui évoluent,
modulations, libération de la résonance). La détection compte **2 planètes** (vitesse radiale, bruitée ou non,
et astrométrie) et range ces signaux dans les composantes non planétaires, avec la mention qu'un faible
signal près de 2f_c *pourrait* être une petite planète en résonance. Seul un ajustement dynamique N corps
pourrait trancher : c'est la limite connue de la méthode képlérienne.

## Le système solaire, en aveugle

990 ans de vitesse radiale du Soleil, sans bruit : **6 planètes détectées, toutes réelles** — Vénus
(0,81 M⊕), la Terre (1,00 M⊕), Jupiter (1,00 M_Jup), Saturne (0,30 M_Jup), Uranus (14,5 M⊕), Neptune
(17,2 M⊕). Mercure et Mars (K ≈ 0,008 m/s) sont sous le plancher d'amplitude (0,1 % de Jupiter). Aucune
fausse planète, alors que Jupiter et Saturne interagissent (grande inégalité).

## Campagne par injection (T13)

`python scripts/campagne_detection.py --systemes 120` — 120 systèmes aléatoires de 1 à 3 planètes
(périodes 0,05 à 2 ans, masses 0,02 à 3 M_Jup, e ≤ 0,3, systèmes stables au sens de Hill), simulés en N corps
sur 4 ans, 100 observations irrégulières avec 30 % de l'année inobservable, bruit 3 m/s.

| Indicateur | Valeur |
|---|---|
| Fausses détections | **0** sur 120 systèmes |
| Planètes retrouvées, signal/bruit K/σ·√(N/2) ≥ 10 | **100 %** (140 planètes) |
| Planètes retrouvées, signal/bruit 5 à 10 | 63 % |
| Planètes retrouvées, signal/bruit < 5 | 0 % |
| Nombre de planètes exact | 69 % (tous les échecs viennent de planètes sous le seuil) |
| Vrai nombre parmi les réponses possibles | 73 % |
| Systèmes signalés AMBIGU | 12 % |
| Erreur médiane sur la période / sur K | 0,1 % / 1,4 % |

La courbe de complétude est la courbe de détection classique, avec une transition vers un signal/bruit de 7.
Près du seuil, les K mesurés sont légèrement surestimés : c'est le **biais d'Eddington**, bien connu des
relevés réels (on ne détecte les signaux faibles que lorsque le bruit les renforce).

## Limites assumées

- **Systèmes en forte interaction avec des données très précises** : les signaux d'interaction sont réels et
  significatifs ; ils sont classés non planétaires selon des règles physiques (harmoniques, combinaisons,
  libération, proximité), mais une petite planète réelle tombant exactement à ces fréquences serait signalée
  comme ambiguë plutôt que comptée.
- **Planète de période plus longue que l'observation** : traitée comme une tendance, non confirmée.
- **Probabilité de fausse alarme** : formule analytique approchée (nombre de fréquences indépendantes ≈ f_max·T) ;
  la campagne montre qu'elle est conservatrice (aucune fausse détection).
- **Masse de l'étoile** : supposée connue ; sans elle, P, K et e restent mesurés mais pas les masses.

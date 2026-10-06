# Point d'étape du jalon 2 : premiers spectres

Figures produites par `scripts/etude_spectre.py --tous` (dossier `outputs/`, non versionné).
Intégrateur Yoshida 4, observateur par la tranche (i = 90°), signal sans bruit sauf mention contraire.

## Ce qui fonctionne

| Système | Attendu | Mesuré (spectre de vitesse radiale) |
|---|---|---|
| Soleil-Jupiter | P = 11,85 ans, K = 12,47 m/s | P = 11,85 ans, K = 12,47 m/s |
| Jupiter chaud (51 Peg b) | P = 4,23 j, K = 53,9 m/s | P = 4,23 j, K = 53,9 m/s |
| Système solaire, géantes | K = 12,5 / 2,76 / 0,30 / 0,28 m/s | les 4 retrouvées, mêmes amplitudes |

- L'astrométrie complexe `z = x + iy` donne un pic par planète circulaire, du côté des fréquences positives (sens direct) : l'orientation des orbites est lisible directement.
- La jauge de fidélité reste entre 10⁻¹² (deux corps) et 10⁻⁹ (système solaire sur 990 ans).

## Pièges rencontrés, tous prévus par le cahier des charges

1. **Lobes de la fenêtre de Hann.** Chaque pic fort est flanqué de petits pics (≈ 3 %) à ±2,5/T. Ce ne sont pas des planètes. Le script les étiquette « lobe secondaire de la fenêtre ».
2. **Planètes telluriques masquées.** La Terre et Vénus (K ≈ 0,09 m/s) sont noyées sous la fuite spectrale de Jupiter dans le spectre de vitesse radiale. Elles restent devinables en astrométrie (≈ 3×10⁻⁶ UA vers 1 cycle/an). Il faut l'extraction itérative (jalon 5) : retirer Jupiter, puis chercher dans le résidu.
3. **Dégénérescence 2:1, observée concrètement.**
   - Couple résonant (planètes circulaires) : rapport des pics 2f/f = 0,39.
   - Planète unique excentrique (e = 0,4) : rapport 0,38.
   - Au premier ordre, c'est indiscernable : le script affiche « GJ 876 c / harmonique 2f de GJ 876 b (AMBIGU) ».
   - **Mais deux indices les séparent :** la planète excentrique produit des harmoniques 3f, 4f, 5f nettes (amplitudes ∝ e², e³…) et, en astrométrie, un petit pic **rétrograde** à −f. Le couple résonant ne produit ni l'un ni l'autre. Piste concrète pour le jalon 5.
4. **Amplitude d'une orbite excentrique.** Pour e = 0,4, le pic fondamental vaut 236 m/s alors que K = 274 m/s : l'énergie du signal se répartit sur les harmoniques. Seul un ajustement képlérien (jalon 5) retrouve K.
5. **Campagne réaliste** (120 observations irrégulières sur 3 ans, bruit 5 m/s, 30 % de l'année inobservable) : la planète principale sort, mais entourée d'une forêt d'alias annuels (±1 et ±2 cycles/an) atteignant ~40 % de son amplitude, du même ordre que la planète intérieure. Sans extraction itérative, compter les pics donnerait un résultat faux.
6. **Résonance réelle.** Partant d'orbites circulaires, la planète intérieure du couple 2:1 voit son excentricité et son orientation évoluer (figure des orbites) : c'est la dynamique résonante, pas une erreur numérique (jauge à 2×10⁻⁷).

## Conséquences pour la suite

- Jalon 5 : prewhitening + ajustement képlérien + critère d'arrêt (FAP, ΔBIC), et test de discrimination « excentrique vs résonant » à partir des harmoniques d'ordre ≥ 3 et de la composante rétrograde astrométrique.
- Performance : 990 ans de système solaire ≈ 110 s. Suffisant pour des études ; à optimiser (Numba) seulement si les campagnes du jalon 5 l'exigent.

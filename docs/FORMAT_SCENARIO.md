# Format des scénarios (JSON)

Un scénario décrit les conditions initiales : les corps, leurs positions et vitesses, et les poussées
programmées. Il s'enregistre et s'ouvre depuis le menu *Fichier*. Les presets du dossier `gravsim/presets/`
sont des exemples complets.

## Structure

```json
{
  "format": "gravsim-scenario",
  "version": 1,
  "name": "Mon système",
  "description": "Texte libre affiché dans le menu des presets.",
  "bodies": [ ... ],
  "impulses": [ ... ],
  "zero_momentum": true,
  "center": true
}
```

| Clé | Rôle |
|---|---|
| `format`, `version` | identification (version 1 ; un fichier plus récent que le logiciel est refusé) |
| `name`, `description` | affichage |
| `bodies` | liste des corps, **dans l'ordre** (un corps peut orbiter autour d'un corps listé avant lui) |
| `impulses` | poussées programmées (facultatif) |
| `zero_momentum` | `true` : retire la vitesse du barycentre après création des corps (refusé s'il y a un corps fixe) |
| `center` | `true` : place le barycentre à l'origine |
| `G`, `t0` | constante de gravitation (défaut 4π² en UA³/(M☉·an²)) et instant initial (défaut 0) |

## Unités

Unités internes : **UA** (longueurs), **M☉** (masses), **an** (temps), donc **UA/an** pour les vitesses
(1 UA/an = 4,74 km/s). Toute grandeur peut aussi s'écrire `{"value": v, "unit": "u"}` :

- masses : `Msun` (ou `MS`), `Mjup` (`MJ`), `Mearth` (`ME`), `Mmoon` ;
- longueurs : `AU`, `Rsun` (`RS`), `Rjup` (`RJ`), `Rearth` (`RE`), `Rmoon`, `km`.

## Un corps

```json
{"name": "Jupiter", "mass": {"value": 1, "unit": "Mjup"}, "radius": {"value": 1, "unit": "Rjup"},
 "color": "#d9a066", "fixed": false, "display_px": 12,
 "orbit": {"around": "Soleil", "distance": 5.2, "angle_deg": 0, "e": 0.05, "at": "periapsis", "clockwise": false}}
```

| Clé | Rôle |
|---|---|
| `name` | unique |
| `mass` | ≥ 0 (0 = particule test) |
| `radius` **ou** `density` | rayon physique (collisions), ou densité en g/cm³ pour le calculer ; défaut 0 |
| `fixed` | corps immobile qui attire les autres |
| `color`, `display_px` | apparence (diamètre en pixels pour le mode de taille « manuelle ») |

Position et vitesse, au choix :

- **explicites** : `"position": [x, y]` et `"velocity": [vx, vy]`, ou `"velocity": {"speed": s, "direction_deg": a}` ;
- **par une orbite** : `"orbit"` place le corps à `distance` du corps `around`, dans la direction `angle_deg`, et
  lui donne la vitesse d'une orbite d'excentricité `e` dont cette position est le périastre (`"at": "periapsis"`)
  ou l'apoastre (`"apoapsis"`), dans le sens antihoraire (ou horaire avec `"clockwise": true`). La vitesse est
  celle du problème à deux corps, relative au corps central (qui peut lui-même être en mouvement).

## Une poussée

```json
{"body": "Jupiter", "dv": 0.5, "t": 12.0, "direction": "prograde", "reference": "Soleil", "angle_deg": 0}
```

| Clé | Rôle |
|---|---|
| `body` | corps poussé |
| `dv` | variation de vitesse en UA/an, **signée** (négative = freinage / vers l'intérieur) |
| `t` | instant en années |
| `direction` | `prograde` (le long de la vitesse relative à la référence), `radial` (référence → corps), `angle` (direction fixe `angle_deg`) |
| `reference` | corps de référence ; défaut : le plus massif des autres |

## Exemple complet

```json
{
  "format": "gravsim-scenario", "version": 1,
  "name": "Étoile et deux planètes",
  "bodies": [
    {"name": "Étoile", "mass": 0.9, "radius": {"value": 0.9, "unit": "Rsun"}},
    {"name": "b", "mass": {"value": 0.5, "unit": "Mjup"}, "density": 1.3,
     "orbit": {"around": "Étoile", "distance": 0.3}},
    {"name": "c", "mass": {"value": 2, "unit": "Mjup"}, "density": 1.3,
     "orbit": {"around": "Étoile", "distance": 1.2, "angle_deg": 140, "e": 0.15}}
  ],
  "impulses": [{"body": "c", "dv": -0.3, "t": 5.0}],
  "zero_momentum": true
}
```

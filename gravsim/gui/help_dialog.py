"""Quick guide shown by Aide → Guide rapide (F1). The full guide is docs/GUIDE_UTILISATEUR.md."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

QUICK_GUIDE = """
<h2>Guide rapide</h2>

<h3>Simuler</h3>
<ul>
<li><b>Espace</b> lecture / pause · <b>S</b> un pas · <b>R</b> réinitialiser · <b>L</b> revenir au direct.</li>
<li>Curseur <b>Vitesse</b> : temps simulé par seconde. Curseur du bas : remonter dans le temps déjà calculé.</li>
<li>Clic sur un corps pour le sélectionner ; molette pour zoomer, glisser pour déplacer.</li>
<li>Menu <b>Presets</b> : systèmes prêts à l'emploi (Système solaire, Couple résonant 2:1, Troyens…).</li>
</ul>

<h3>Construire un système (panneau de droite, onglet Corps)</h3>
<ul>
<li>Masse, rayon, position, vitesse en <i>norme + direction</i> ou en <i>composantes</i>, avec unités au choix.</li>
<li><b>Vitesse orbitale automatique</b> : orbite circulaire ou excentrique autour d'un corps, ou vitesse de libération.</li>
<li><b>Corps fixe</b> : il attire sans bouger. <b>Masse 0</b> : particule test.</li>
<li><b>Annuler la quantité de mouvement totale</b> (sous la liste) avant toute analyse spectrale.</li>
<li>Onglet <b>Poussées</b> : Δv signé (prograde, radial ou angle), maintenant ou à un instant programmé.</li>
</ul>

<h3>Regarder</h3>
<ul>
<li>Onglet <b>Vue</b> : taille des corps (selon la masse, manuelle, échelle réelle) ; <b>référentiel</b> inertiel,
barycentrique, centré sur un corps ou <b>tournant avec une paire</b> (points de Lagrange immobiles) ; vecteurs,
sphères de Hill.</li>
<li>Groupe <b>Points de Lagrange et potentiel</b> : marqueurs L1 à L5, fond de potentiel gravitationnel ou
<b>effectif</b> (à regarder en référentiel tournant : les troyens sont au sommet de L4 et L5), lignes de niveau,
courbes critiques (L1 = lobe de Roche).</li>
<li>Barre d'état : <b>ΔE/E</b> = dérive de l'énergie (erreur numérique). Vert : excellent ; rouge : réduire le pas
(onglet Intégration) ou passer en DOP853.</li>
</ul>

<h3>Analyser</h3>
<ul>
<li>Page <b>Analyse</b> : distances, vitesses, positions, énergies et conservation, éléments orbitaux.</li>
<li><i>Fichier → Exporter l'analyse (.csv)</i> pour un tableur.</li>
</ul>

<h3>Compter les planètes d'une étoile</h3>
<ol>
<li>Page <b>Spectre</b> : choisir l'étoile et le signal (vitesse radiale ou astrométrie).</li>
<li><b>Compléter (6 × P max)</b> pour simuler assez longtemps.</li>
<li>Échantillonnage irrégulier + bruit réaliste (1 à 3 m/s), puis <b>Calculer le spectre</b>.</li>
<li>Sous-onglet <b>Détection</b> → <b>Détecter les planètes</b> : nombre de planètes, périodes, masses (m sin i),
signaux non planétaires, et « AMBIGU » quand une planète excentrique ne se distingue pas d'un couple 2:1.</li>
</ol>
<p>Repère : on retrouve presque toute planète dont le rapport signal/bruit K/σ·√(N/2) dépasse 10.</p>

<p><i>Guide complet : docs/GUIDE_UTILISATEUR.md · format des scénarios : docs/FORMAT_SCENARIO.md</i></p>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guide rapide")
        self.resize(720, 760)
        self.browser = QTextBrowser()
        self.browser.setHtml(QUICK_GUIDE)
        self.browser.setOpenExternalLinks(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        lay = QVBoxLayout(self)
        lay.addWidget(self.browser)
        lay.addWidget(buttons)

from GSmain import Domain, AstralBody
from gui.viewer import PygameViewer

# Définir le moteur
domain = Domain(dt=0.05, tf=10)

# Ajouter des planètes
planetA = AstralBody(domain, ci_pos=(-1, 0), ci_speed=(0, -0.2), mass=50)
planetA.color = (50, 100, 255)

planetB = AstralBody(domain, ci_pos=(5, 0), ci_speed=(0, 1), mass=10)
planetB.color = (50, 100, 255)

# Lancer l'affichage
viewer = PygameViewer(domain)
viewer.run()

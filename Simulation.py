from body import Body  # On importe Body (on fera aussi le fichier body.py)

class Simulation:
    def __init__(self):
        # Liste pour stocker tous les corps célestes
        self.bodies = []

        # Exemple : ajouter deux planètes pour démarrer
        body1 = Body(x=300, y=400, mass=1000, vx=0, vy=2, color=(0, 255, 0), radius=10)
        body2 = Body(x=800, y=400, mass=500, vx=0, vy=-2, color=(255, 0, 0), radius=8)
        self.bodies.append(body1)
        self.bodies.append(body2)

    def update(self):
        # Ici on fera le calcul des forces de gravité
        dt = 1  # On peut ajuster le temps plus tard
        for body in self.bodies:
            # Pour l'instant, pas de forces : on laisse bouger les corps
            body.update((0, 0), dt)

    def draw(self, screen):
        for body in self.bodies:
            body.draw(screen)

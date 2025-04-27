from body import Body  # On importe Body (on fera aussi le fichier body.py)

class Simulation:
    def __init__(self):
        # Liste pour stocker tous les corps célestes
        self.bodies = []

        # Exemple : ajouter deux planètes pour démarrer
        body1 = Body() #todo faire initialisation des corps
        body2 = Body()
        self.bodies.append(body1)
        self.bodies.append(body2)

    def update(self):
        # Ici on fera le calcul des forces de gravité
        dt = .1  # On peut ajuster le temps plus tard
        for body in self.bodies:
            # Pour l'instant, pas de forces : on laisse bouger les corps
            body.refresh(dt)

    def draw(self, screen):
        for body in self.bodies:
            body.draw(screen)

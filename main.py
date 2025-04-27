import pygame
from simulation import Simulation

# Initialisation de Pygame
pygame.init()

# Définir la taille de la fenêtre
screen_width, screen_height = 1200, 800
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Simulation Gravitationnelle 2D")

# Couleur pour effacer l'écran
BLACK = (0, 0, 0)

# Horloge pour contrôler les FPS
clock = pygame.time.Clock()

# Créer une instance de ta Simulation
simulation = Simulation()

# Boucle principale
running = True
while running:
    # Limite la vitesse à 60 images/seconde
    clock.tick(60)

    # Gestion des événements (fermeture fenêtre)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Mise à jour de la simulation
    simulation.update()

    # Efface l'écran
    screen.fill(BLACK)

    # Dessine la simulation
    simulation.draw(screen)

    # Met à jour l'affichage
    pygame.display.flip()

# Quitter Pygame proprement
pygame.quit()

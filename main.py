import pygame
from Simulation import Simulation

pygame.init()

# Définir la taille de la fenêtre
screen_width, screen_height = 1200, 800
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Simulation Gravitationnelle 2D")

# Couleurs utiles
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Clock pour contrôler la vitesse d'animation
clock = pygame.time.Clock()

# Créer ta simulation
simulation = Simulation()

# Boucle principale
running = True
while running:
    clock.tick(60)  # 60 FPS

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    simulation.update()

    screen.fill(BLACK)
    simulation.draw(screen)
    pygame.display.flip()

pygame.quit()

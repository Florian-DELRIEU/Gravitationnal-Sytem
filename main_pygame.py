import pygame
from GSmain import Domain, AstralBody

# --- Paramètres de la fenêtre ---
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 800
VIEW_WIDTH = int(WINDOW_WIDTH * 0.8)      # Zone graphique
PANEL_WIDTH = WINDOW_WIDTH - VIEW_WIDTH   # Zone de contrôle future

# --- Couleurs ---
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE = (50, 100, 255)

# --- Initialisation du moteur physique ---
domain = Domain(dt=0.05, tf=10)
planet = AstralBody(domain, ci_pos=(3, 0), ci_speed=(0, 1), mass=100)

# --- Initialisation Pygame ---
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Simulation gravitationnelle - 2D")

clock = pygame.time.Clock()

# --- Boucle principale ---
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # --- Simulation physique ---
    domain.step()

    # --- Affichage ---
    screen.fill(BLACK)

    # Dessin de la zone graphique
    pygame.draw.rect(screen, (20, 20, 20), (0, 0, VIEW_WIDTH, WINDOW_HEIGHT))

    # Dessin de la zone latérale
    pygame.draw.rect(screen, (40, 40, 40), (VIEW_WIDTH, 0, PANEL_WIDTH, WINDOW_HEIGHT))

    # Coordonnées converties en pixels (centre de la zone graphique = origine)
    px = int(VIEW_WIDTH / 2 + planet.x * 50)
    py = int(WINDOW_HEIGHT / 2 - planet.y * 50)

    pygame.draw.circle(screen, BLUE, (px, py), 5)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()

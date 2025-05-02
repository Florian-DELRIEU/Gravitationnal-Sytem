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
RED = (255, 100, 50)

# --- Initialisation du moteur physique ---
domain = Domain(dt=0.05, tf=10)
planetA = AstralBody(domain, ci_pos=(3, 0), ci_speed=(0, 1), mass=10)
planetA.color = BLUE
planetB = AstralBody(domain, ci_pos=(-3, 0), ci_speed=(0, -1), mass=10)
planetB.color = BLUE

# --- Initialisation Pygame ---
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Simulation gravitationnelle - 2D")

clock = pygame.time.Clock()

# --- Boucle principale ---
running = True
paused = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                paused = not paused
            elif event.key == pygame.K_RIGHT:
                if paused:
                    domain.step()
            elif event.key == pygame.K_LEFT:
                pass  #todo ← Avancer d’un pas en arrière = plus complexe, à implémenter plus tard
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if buttons["play_pause"].collidepoint(event.pos):
                paused = not paused
            elif buttons["step_forward"].collidepoint(event.pos) and paused:
                domain.step()
            elif buttons["step_back"].collidepoint(event.pos):
                print("Fonction pas encore disponible.")  # À remplacer plus tard

    # --- Simulation physique ---
    if not paused:
        domain.step()

    # --- Affichage ---
    screen.fill(BLACK)

    # Dessin de la zone graphique
    pygame.draw.rect(screen, (20, 20, 20), (0, 0, VIEW_WIDTH, WINDOW_HEIGHT))

    # Dessin de la zone latérale
    pygame.draw.rect(screen, (40, 40, 40), (VIEW_WIDTH, 0, PANEL_WIDTH, WINDOW_HEIGHT))
    font = pygame.font.SysFont(None, 24)
    status_text = "PAUSE" if paused else "PLAY"
    text_surface = font.render(status_text, True, WHITE)
    screen.blit(text_surface, (VIEW_WIDTH + 20, 20))
    # --- Interface latérale ---
    pygame.draw.rect(screen, (40, 40, 40), (VIEW_WIDTH, 0, PANEL_WIDTH, WINDOW_HEIGHT))

    font = pygame.font.SysFont(None, 24)

    # Définir les boutons
    buttons = {
        "play_pause": pygame.Rect(VIEW_WIDTH + 20, 40, 120, 30),
        "step_forward": pygame.Rect(VIEW_WIDTH + 20, 80, 120, 30),
        "step_back": pygame.Rect(VIEW_WIDTH + 20, 120, 120, 30)
    }

    # Dessiner les boutons
    pygame.draw.rect(screen, (100, 200, 100), buttons["play_pause"])
    pygame.draw.rect(screen, (100, 100, 255), buttons["step_forward"])
    pygame.draw.rect(screen, (150, 150, 150), buttons["step_back"])

    screen.blit(font.render("Play/Pause", True, BLACK), (buttons["play_pause"].x + 10, buttons["play_pause"].y + 5))
    screen.blit(font.render("Avancer", True, BLACK), (buttons["step_forward"].x + 20, buttons["step_forward"].y + 5))
    screen.blit(font.render("<< (désactivé)", True, BLACK), (buttons["step_back"].x + 5, buttons["step_back"].y + 5))

    # Détecter le survol du bouton "recul"
    mouse_pos = pygame.mouse.get_pos()
    if buttons["step_back"].collidepoint(mouse_pos):
        screen.blit(font.render("À venir : sauvegarde état précédent", True, WHITE), (VIEW_WIDTH + 20, 160))



    # Coordonnées converties en pixels (centre de la zone graphique = origine)
    for body in domain.body_list:
        color = getattr(body, 'color', body.color)  # Couleur par défaut si non définie
        px = int(VIEW_WIDTH / 2 + body.x * 50)
        py = int(WINDOW_HEIGHT / 2 - body.y * 50)
        pygame.draw.circle(screen, color, (px, py), 5)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()

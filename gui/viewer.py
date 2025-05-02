import pygame

# --- Constantes graphiques ---
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 800
VIEW_WIDTH = int(WINDOW_WIDTH * 0.8)
PANEL_WIDTH = WINDOW_WIDTH - VIEW_WIDTH

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREY = (40, 40, 40)
DARK_GREY = (20, 20, 20)
BLUE = (50, 100, 255)

class PygameViewer:
    def __init__(self, domain):
        self.domain = domain
        self.paused = True

        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Simulation gravitationnelle - 2D")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)

        self.buttons = {
            "play_pause": pygame.Rect(VIEW_WIDTH + 20, 40, 120, 30),
            "step_forward": pygame.Rect(VIEW_WIDTH + 20, 80, 120, 30),
            "step_back": pygame.Rect(VIEW_WIDTH + 20, 120, 120, 30)
        }

    def draw_interface(self):
        # Zones de fond
        self.screen.fill(BLACK)
        pygame.draw.rect(self.screen, DARK_GREY, (0, 0, VIEW_WIDTH, WINDOW_HEIGHT))   # zone graphique
        pygame.draw.rect(self.screen, GREY, (VIEW_WIDTH, 0, PANEL_WIDTH, WINDOW_HEIGHT))  # zone latérale

        # Boutons
        pygame.draw.rect(self.screen, (100, 200, 100), self.buttons["play_pause"])
        pygame.draw.rect(self.screen, (100, 100, 255), self.buttons["step_forward"])
        pygame.draw.rect(self.screen, (150, 150, 150), self.buttons["step_back"])

        self.screen.blit(self.font.render("Play/Pause", True, BLACK), (self.buttons["play_pause"].x + 10, self.buttons["play_pause"].y + 5))
        self.screen.blit(self.font.render("Avancer", True, BLACK), (self.buttons["step_forward"].x + 20, self.buttons["step_forward"].y + 5))
        self.screen.blit(self.font.render("<< (désactivé)", True, BLACK), (self.buttons["step_back"].x + 5, self.buttons["step_back"].y + 5))

        # Infobulle si survol bouton "recul"
        mouse_pos = pygame.mouse.get_pos()
        if self.buttons["step_back"].collidepoint(mouse_pos):
            self.screen.blit(self.font.render("À venir : sauvegarde état précédent", True, WHITE), (VIEW_WIDTH + 20, 160))

        # État Play/Pause
        status = "PAUSE" if self.paused else "PLAY"
        self.screen.blit(self.font.render(f"État : {status}", True, WHITE), (VIEW_WIDTH + 20, 10))

    def draw_bodies(self):
        for body in self.domain.body_list:
            color = getattr(body, 'color', BLUE)
            px = int(VIEW_WIDTH / 2 + body.x * 50)
            py = int(WINDOW_HEIGHT / 2 - body.y * 50)
            pygame.draw.circle(self.screen, color, (px, py), 5)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_RIGHT and self.paused:
                    self.domain.step()
                elif event.key == pygame.K_LEFT:
                    print("Recul non encore implémenté.")

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.buttons["play_pause"].collidepoint(event.pos):
                    self.paused = not self.paused
                elif self.buttons["step_forward"].collidepoint(event.pos) and self.paused:
                    self.domain.step()
                elif self.buttons["step_back"].collidepoint(event.pos):
                    print("Recul non encore implémenté.")

        return True

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            if not self.paused:
                self.domain.step()

            self.draw_interface()
            self.draw_bodies()
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

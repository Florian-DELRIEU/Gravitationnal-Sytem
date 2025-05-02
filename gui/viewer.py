import pygame
from gui.panel import SidePanel


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
        self.panel = SidePanel(VIEW_WIDTH, PANEL_WIDTH, WINDOW_HEIGHT, self.font)

    def draw_interface(self):
        # Zones de fond
        self.screen.fill(BLACK)
        pygame.draw.rect(self.screen, DARK_GREY, (0, 0, VIEW_WIDTH, WINDOW_HEIGHT))   # zone graphique
        self.panel.draw(self.screen, self.paused)

    def draw_bodies(self):
        for body in self.domain.body_list:
            color = getattr(body, 'color', BLUE)
            px = int(VIEW_WIDTH / 2 + body.x * 50)
            py = int(WINDOW_HEIGHT / 2 - body.y * 50)
            radius = max(3, min(int(body.mass ** 0.5), 20))
            pygame.draw.circle(self.screen, color, (px, py), radius)

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
                self.paused = self.panel.handle_click(event.pos, self.paused, self.domain)


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

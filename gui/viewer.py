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
        self.show_trajectories = False

        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Simulation gravitationnelle - 2D")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)
        self.panel = SidePanel(VIEW_WIDTH, PANEL_WIDTH, WINDOW_HEIGHT, self.font)

    def draw_interface(self):
        # Zones de fond
        self.screen.fill(BLACK)
        # Ecran principal
        pygame.draw.rect(self.screen, DARK_GREY, (0, 0, VIEW_WIDTH, WINDOW_HEIGHT))  # zone graphique
        # Affichage du temps en haut à gauche
        t = self.domain.current_step * self.domain.dt
        time_str = f"t = {t:.2f} s"
        self.screen.blit(self.font.render(time_str, True, WHITE), (10, 10))
        self.panel.draw(self.screen, self.paused, self.show_trajectories)

    def draw_bodies(self):
        for body in self.domain.body_list:
            color = getattr(body, 'color', BLUE)
            px = int(VIEW_WIDTH / 2 + body.x * 50)
            py = int(WINDOW_HEIGHT / 2 - body.y * 50)
            radius = max(3, min(int(body.mass ** 0.5), 20))

            pygame.draw.circle(self.screen, color, (px, py), radius)

            if self.show_trajectories and "x" in body.kinetic_dict and "y" in body.kinetic_dict:
                traj_x = body.kinetic_dict["x"]
                traj_y = body.kinetic_dict["y"]

                if len(traj_x) > 1:
                    points = [
                        (
                            int(VIEW_WIDTH / 2 + x * 50),
                            int(WINDOW_HEIGHT / 2 - y * 50)
                        )
                        for x, y in zip(traj_x, traj_y)
                    ]
                    pygame.draw.lines(self.screen, color, False, points, 1)

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
                action = self.panel.handle_click(event.pos, self.paused, self.domain)
                if action == "toggle_trajectories":
                    print("Affichage des trajectoires :", self.show_trajectories)
                    self.show_trajectories = not self.show_trajectories
                elif isinstance(action, bool):
                    self.paused = action

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

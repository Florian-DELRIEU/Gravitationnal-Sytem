import pygame

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (40, 40, 40)
LIGHT_GREY = (150, 150, 150)

class SidePanel:
    def __init__(self, x_offset, width, height, font):
        self.rect = pygame.Rect(x_offset, 0, width, height)
        self.font = font
        self.buttons = {
            "play_pause": pygame.Rect(x_offset + 20, 40, 120, 30),
            "step_forward": pygame.Rect(x_offset + 20, 80, 120, 30),
            "step_back": pygame.Rect(x_offset + 20, 120, 120, 30),
            "toggle_trajectories": pygame.Rect(x_offset + 20, 160, 120, 30)
        }

    def draw(self, screen, paused, show_trajectories=False):
        pygame.draw.rect(screen, GREY, self.rect)
        traj_color = (255, 150, 50) if show_trajectories else (180, 180, 180)

        # Boutons
        pygame.draw.rect(screen, (100, 200, 100), self.buttons["play_pause"])
        pygame.draw.rect(screen, (100, 100, 255), self.buttons["step_forward"])
        pygame.draw.rect(screen, traj_color, self.buttons["toggle_trajectories"])
        pygame.draw.rect(screen, LIGHT_GREY, self.buttons["step_back"])

        screen.blit(self.font.render("Play/Pause", True, BLACK), self.buttons["play_pause"].move(10, 5).topleft)
        screen.blit(self.font.render("Avancer", True, BLACK), self.buttons["step_forward"].move(20, 5).topleft)
        screen.blit(self.font.render("<< (désactivé)", True, BLACK), self.buttons["step_back"].move(5, 5).topleft)
        screen.blit(self.font.render("Trajectoires", True, BLACK), self.buttons["toggle_trajectories"].move(10, 5).topleft)

        status = "PAUSE" if paused else "PLAY"
        screen.blit(self.font.render(f"État : {status}", True, WHITE), (self.rect.x + 20, 10))

        # Infobulle
        mouse_pos = pygame.mouse.get_pos()
        if self.buttons["step_back"].collidepoint(mouse_pos):
            screen.blit(self.font.render("À venir : sauvegarde état précédent", True, WHITE), (self.rect.x + 20, 160))

    def handle_click(self, event_pos, paused, domain):
        if self.buttons["play_pause"].collidepoint(event_pos):
            return not paused
        elif self.buttons["step_forward"].collidepoint(event_pos) and paused:
            domain.step()
        elif self.buttons["step_back"].collidepoint(event_pos):
            print("Fonction recul non encore disponible.")
        elif self.buttons["toggle_trajectories"].collidepoint(event_pos):
            return "toggle_trajectories"
        return paused

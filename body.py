import pygame

class Body:
    def __init__(self, x, y, mass, vx=0, vy=0, color=(255, 255, 255), radius=5):
        self.x = x
        self.y = y
        self.mass = mass
        self.vx = vx
        self.vy = vy
        self.color = color
        self.radius = radius

    def update(self, forces, dt):
        fx, fy = forces
        ax = fx / self.mass
        ay = fy / self.mass
        self.vx += ax * dt
        self.vy += ay * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

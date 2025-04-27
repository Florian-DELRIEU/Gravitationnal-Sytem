import pygame
import numpy as np

class Body:
    def __init__(self, Domain, ci_pos=(0, 0), ci_speed=(0, 0), mass=0.0):
        """
        Comporte toutes les caractérisques et données d'un objet célèste
        :param Domain: objet :class Universe: nécéssaire comportant les données du domain dans lequel il évolue
            -
        """
        self.Domain = Domain  # Liaison avex l'objet :Universe:
        self.G = Domain.G  # Recupere G de l'objet :Universe:
    # Variable definitions
        self.mass = mass
        self.x = ci_pos[0]
        self.y = ci_pos[1]
        self.vx = ci_speed[0]
        self.vy = ci_speed[1]
        self.ax = float(0)
        self.ay = float(0)
        Domain.body_list.append(self)  # S'ajoute lui-même dans liste de l'univers
        self.Bodylist = Domain.body_list.copy()  # Listes des autres corps dans :Universe:
        self.is_moving = True  # Si :False: l'objet ne peut pas bouger
    # Paramètres garphiques
        self.filename = ""
        self.color = ""
        self.mark = "o"
        self.kinetic_dict = dict()
        self.kinetic_dict["Time"] = np.array(Domain.t)
        self.kinetic_dict["x"] = []
        self.kinetic_dict["y"] = []
        self.kinetic_dict["vx"] = np.array([])
        self.kinetic_dict["vy"] = np.array([])
        self.kinetic_dict["ax"] = np.array([])
        self.kinetic_dict["ay"] = np.array([])

    def __repr__(self):
        txt = """Astral Body
            - Pos = ({} , {})
            - Mass = {}
        """.format(self.x, self.y, self.mass)
        return txt

    def refresh(self,dt):
        if self.is_moving:  # si il peut bouger
            self.body_list = self.Domain.body_list.copy() # Obliger de faire une copy de la liste
            self.body_list.remove(self)  # se supprime lui meme pour eviter auto-influence
            self.ax, self.ay = 0,0  # refresh pour eviter cumuls des acc avec itération précédente
            # Calcul de l'accéleration due à la présence de chaque corps
            for this_body in self.body_list:
                cur_distance = np.sqrt((this_body.x - self.x)**2 + (this_body.y - self.y)**2)  # distance
                # Calcul des accélérations
                self.ax += - self.G * this_body.mass / cur_distance ** 3 * (self.x - this_body.x)
                self.ay += - self.G * this_body.mass / cur_distance ** 3 * (self.y - this_body.y)
            # Calcul des vitesses
            self.vx += self.ax*dt
            self.vy += self.ay*dt
            # Calcul des nouvelles positions
            self.x += self.vx*dt
            self.y += self.vy*dt
            self.kinetic_dict["x"] = np.append(self.kinetic_dict["x"], self.x)
            self.kinetic_dict["y"] = np.append(self.kinetic_dict["y"], self.y)
            self.kinetic_dict["vx"] = np.append(self.kinetic_dict["vx"], self.vx)
            self.kinetic_dict["vy"] = np.append(self.kinetic_dict["vy"], self.vy)
            self.kinetic_dict["ax"] = np.append(self.kinetic_dict["ax"], self.ax)
            self.kinetic_dict["ay"] = np.append(self.kinetic_dict["ay"], self.ay)

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

"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt
plt.ion()

def GRAVITYFIELD(body_list): pass

class AstralBody:
    def __init__(self,Domain):
        """
        Comporte toutes les caractérisques et données d'un objet célèste
        :param Domain: objet :class Universe: nécéssaire comportant les données du domain dans lequel il évolue
            -
        """
        self.Domain = Domain  # Liaison avex l'objet :Univere:
        self.G = Domain.G  # Recupere G de l'objet :Universe:
    # Variable definitions
        self.Mass = float(0)
        self.x = float(0)
        self.y = float(0)
        self.vx = float(0)
        self.vy = float(0)
        self.ax = float(0)
        self.ay = float(0)
        Domain.BodyList.append(self)  # S'ajoute lui-même dans liste de l'univers
        self.Bodylist = Domain.BodyList.copy()  # Listes des autres corps dans :Universe:
        self.IsMoving = True  # Si :False: l'objet ne peut pas bouger
    # Paramètres garphiques
        self.Color = ""
        self.Mark = "o"
        self.Trajectory = list()  # Suite des points parcourues
    def __repr__(self):
        txt = """Astral Body
            - Pos = ({} , {})
            - Mass = {}
        """.format(self.x,self.y,self.Mass)
        return txt
    def refresh(self,dt):
        if self.IsMoving:  # si il peut bouger
            self.Body_list = self.Domain.BodyList.copy() # Obliger de faire une copy de la liste
            self.Body_list.remove(self)  # se supprime lui meme pour eviter auto-influence
            self.ax, self.ay = 0,0  # refresh pour eviter cumuls des acc avec itération précédente
        # Calcul de l'accéleration due à la présence de chaque corps
            for this_body in self.Body_list:
                cur_distance = np.sqrt((this_body.x - self.x)**2 + (this_body.y - self.y)**2)  # distance
            # Calcul des accélérations
                self.ax += - self.G * this_body.Mass / cur_distance**3 * (self.x - this_body.x)
                self.ay += - self.G * this_body.Mass / cur_distance**3 * (self.y - this_body.y)
        # Calcul des vitesses
            self.vx += self.ax*dt
            self.vy += self.ay*dt
        # Calcul des nouvelles positions
            self.x += self.vx*dt
            self.y += self.vy*dt
            self.Trajectory.append((self.x,self.y))  # Ajout du nouveau point
    def setbody(self,x,y,Mass):
        """
        Definition rapide d'un astre
        :param x: Position x initiale
        :param y: Position y initiale
        :param Mass: Masse
        """
        self.x = x
        self.y = y
        self.Mass = Mass
    def setvelocity(self,vx,vy):
        """
        Définition rapide d'une vitesse (souvent utilisé pour ajouter une vitesse initiale
        :param vx: vitesse selon x
        :param vy: vitesse selon y
        """
        self.vx = vx
        self.vy = vy

class Domain:
    """
    Objet regroupant les constantes de l'univers ainsi que le maillage spatio-temporel
    """
    def __init__(self):
        self.G = 1  # Constante gravitationnelle (G = 6.67e-11 SI)
    # Maillage espace - temps
        self.dx = .1
        self.dy = .1
        self.dt = .1
    # Taille domaine
        self.x_range = 10
        self.y_range = 10
        self.tf = 1  # Temps final
    # Maillage
        self.X,self.Y = np.meshgrid(np.arange(-self.x_range,self.x_range,self.dx),
                                    np.arange(-self.y_range,self.y_range,self.dy))
    # Liste des corps appartenant à l'univers (systeme)
        self.BodyList = list()
    # Creation vecteur temps
        self.settime()

    def settime(self,dt=self.dt,tf=self.tf):
        """
        Creation du array de temps
        :param dt: pas de temps (par défaut si vide)
        :param tf: temps final (par défaut si vide)

        :return: self.t as :array: 0:dt:tf
        """
        self.dt = dt
        self.tf = tf
        self.t = np.array([])
        self.t = np.arange(0,self.tf,self.dt)

"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt
from MyPack2.Saves.CSV import Dict2CSV
from MyPack2.Utilities import AskUser

class AstralBody:
    def __init__(self, Domain, ci_pos:tuple=(0, 0), ci_speed:tuple=(0, 0), mass:float=0):
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
        self.kinetic_dict["x"] = list()
        self.kinetic_dict["y"] = list()
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

    def Gvector(self,ratio=1):
        """
        Affiche le vecteur accélération de :self:
        """
        self.body_list = self.Domain.body_list.copy()  # Obliger de faire une copy de la liste
        self.body_list.remove(self)  # se supprime lui meme pour eviter auto-influence
        self.ax, self.ay = 0, 0  # refresh pour eviter cumuls des acc avec itération précédente
        # Calcul de l'accéleration due à la présence de chaque corps
        for this_body in self.body_list:
            cur_distance = np.sqrt((this_body.x - self.x) ** 2 + (this_body.y - self.y) ** 2)  # distance
            # Calcul des accélérations
            self.ax += - self.G * this_body.mass / cur_distance ** 3 * (self.x - this_body.x)
            self.ay += - self.G * this_body.mass / cur_distance ** 3 * (self.y - this_body.y)
        plt.arrow(self.x,self.y,ratio*self.ax,ratio*self.ay)
        self.ax, self.ay = 0, 0  # refresh pour eviter cumuls des acc avec itération précédente

    def setbody(self,x,y,Mass):
        """
        Definition rapide d'un astre
        :param x: Position x initiale
        :param y: Position y initiale
        :param Mass: Masse
        """
        self.x = x
        self.y = y
        self.mass = Mass

    def setvelocity(self,vx,vy):
        """
        Définition rapide d'une vitesse (souvent utilisé pour ajouter une vitesse initiale
        :param vx: vitesse selon x
        :param vy: vitesse selon y
        """
        self.vx = vx
        self.vy = vy

    def setCI(self,pos:tuple,speed:tuple,mass:float):
        self.setbody(pos[0],pos[1],mass)
        self.setvelocity(speed[0],speed[1])

    def DoBurn(self,Prograde=0,Radial=0):
        """
        Effectue une poussé dans les deux directions tangeantielles ou radiales à la vitesse
        """
        DV_p = Prograde
        DV_r = Radial
        Theta_p = np.arctan(self.vy/self.vx)  # Angle du vecteur vitesse
        Theta_r = Theta_p + np.pi/2  # Angle du vecteur radiale (vers le centre de l'ellipse)
        V_p = np.sqrt(self.vx**2 + self.vy**2)
        V_r = 0

        V_p += DV_p
        V_r += DV_r

        self.vx = np.cos(Theta_p)*V_p + np.cos(Theta_r)*V_r
        self.vy = np.sin(Theta_p)*V_p + np.sin(Theta_r)*V_r

    def save_kinetic(self, filename=""):
        filename = self.set_filename(filename)
        Dict2CSV(self.kinetic_dict, filename + ".csv")

    def set_filename(self,filename=None):
        if (filename == "" or None) and (self.filename == "" or None):
            filename = f"Body_{self.find_body_list_indic()}"
            self.filename = filename
        elif filename == ["" or None] and self.filename != ["" or None]:
            filename = self.filename
        else: pass
        return filename

    def find_body_list_indic(self):
        temp_body_list = np.array(self.Domain.body_list)
        i = int(np.where(temp_body_list==self)[0])
        return i

class Domain:
    """
    Objet regroupant les constantes de l'univers ainsi que le maillage spatio-temporel
    """
    def __init__(self,dt:float=0.1,tf:float=1):
        self.G = 1  # Constante gravitationnelle (G = 6.67e-11 SI)
    # Maillage espace - temps
        self.dx = .1
        self.dy = .1
        self.dt = dt
    # Taille domaine
        self.x_range = 10
        self.y_range = 10
        self.tf = tf  # Temps final
    # Maillage
        self.X,self.Y = np.meshgrid(np.arange(-self.x_range,self.x_range,self.dx),
                                    np.arange(-self.y_range,self.y_range,self.dy))
    # Liste des corps appartenant à l'univers (systeme)
        self.body_list = []
    # Creation vecteur temps
        self.settime()

    def settime(self,dt=float(0),tf=float(0)):
        """
        Creation du array de temps
        :param dt: pas de temps (par défaut si vide)
        :param tf: temps final (par défaut si vide)

        :return: self.t as :array: 0:dt:tf
        """
        if dt == float(0): dt = self.dt
        else: pass
        if tf == float(0): tf = self.tf
        else: pass

        self.t = np.array([])
        self.t = np.arange(0,tf,dt)

    def run_simulation(self,save_data=False):
        """
        Run the simulation for all bodies of the domain :object;
        """
        for ti in self.t:
            for body in self.body_list:
                body.refresh(self.dt)
        if save_data:
            for body in self.body_list:
                body.save_kinetic()
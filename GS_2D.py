"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import numpy.ma as ma  # masque
import matplotlib.pyplot as plt

def GRAVITYFIELD(body_list):
    return sum(_.grav_x for _ in body_list) , sum(_.grav_y for _ in body_list)

class AstralBody:
    def __init__(self,BodyList):
    # Initial verifications
        assert type(BodyList) is list() , ":BodyList: must be a list"
    # Variable definitions
        self.Mass = float()
        self.x = float(0)
        self.y = float(0)
        self.vx = float(0)
        self.vy = float(0)
        self.ax = float(0)
        self.ay = float(0)
        self.distx_f = lambda x: X - self.x # Distance d'un corps a x,y par rapport a self
        self.disty_f = lambda y: Y - self.y
        self.IsMoving = True
        self.BodyList = BodyList # Liste de corps auquel appartient l'objet
    def __repr__(self):
        txt = """Astral Body
            - Pos = ({} , {})
            - Mass = {}
        """.format(self.x,self.y,self.Mass)
        return txt

########################################################################################################################
########################################################################################################################
# Global Parametres
G = 1  # Constante Gravitationnelle
Body = list()

# Maillage
dx, x_range = .1, 10
dy, y_range = .1, 10
dt, tf = 0.1, 10
X,Y = np.meshgrid(
    np.arange(-x_range,x_range,dx),
    np.arange(-y_range,y_range,dy))
t = np.arange(0,tf,dt)
Nt, Nx, Ny = len(t), len(X), len(Y)


# Testing
for _ in np.arange(2): Body.append(AstralBody())  # Ajout des corps celestes

# Simulation


plt.figure(1)
plt.plot(Body[0].x,Body[0].y,"r*")
plt.plot(Body[1].x,Body[1].y,"r*")
plt.show()

"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt

def getPOTENTIAL(body_list): return sum(_.Potential for _ in body_list)
def getGRAVITY(body_list): return sum(_.Gravity for _ in body_list)

class AstralObject:
    def __init__(self):
        self.Mass = int()
        self.x = int()
        self.y = int()
        self.Vx = int()
        self.Vy = int()
        self.Dist_x = np.array(0)
        self.Dist_y = np.array(0)
        self.Distance = np.array(0)
        self.G_x = np.array(0)
        self.G_y = np.array(0)
        self.Gravity = np.array(0)
        self.Potent_x = np.array(0)
        self.Potent_y = np.array(0)
        self.Potential = np.array(0)
        self.IsMoving = True
        self.setMass(1)
        self.setPos(0,0)
    def getDistance(self):
        self.Dist_x = np.array(X-self.x)
        self.Dist_y = np.array(Y-self.y)
        self.Distance = np.array(np.sqrt(self.Dist_x**2+self.Dist_y**2))
    def getGravity(self):
        self.G_x = np.array(- G*self.Mass/self.Dist_x**2)
        self.G_y = np.array(- G*self.Mass/self.Dist_y**2)
        self.Gravity = np.array( np.sqrt(self.G_x**2 + self.G_y**2))
    def getPotential(self):
        self.Potent_x = - G*self.Mass/self.Dist_x**3
        self.Potent_y = - G*self.Mass/self.Dist_y**3
        self.Potential = - G*self.Mass/self.Distance**3
    def setPos(self,x,y):
        self.x = x
        self.y = y
        self.getDistance()
        self.getPotential()
        self.getGravity()
    def setMass(self,m):
        self.Mass = m
        self.getPotential()
        self.getGravity()
# Global Parametres
G = 1  # Constante Gravitationnelle
Body = list()

# Maillage
dx, x_range = 0.1, 10
dy, y_range = 0.1, 10
dt, tf = 0.1, 10
X,Y = np.meshgrid(
    np.arange(-x_range,x_range,dx),
    np.arange(-y_range,y_range,dy))
t = np.arange(0,tf,dt)
Nt, Nx, Ny = len(t), len(X), len(Y)


# Testing
for _ in np.arange(2):
    Body.append(AstralObject())
Body[0].setPos(3,7)
Body[0].setMass(10)
Body[1].setPos(-1,-5)
Body[1].setMass(1)

POTENTIAL = getPOTENTIAL(Body)
GRAVITY = getGRAVITY(Body)
plt.figure(1)
plt.contourf(X,Y,GRAVITY)
plt.plot(Body[0].x,Body[0].y,"r*")
plt.show()

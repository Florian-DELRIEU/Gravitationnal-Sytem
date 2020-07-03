"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt

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
        self.Grav_x = np.array(0)
        self.Grav_y = np.array(0)
        self.Gravity = np.array(0)
        self.IsMoving = True
        self.setPos(0,0)
        self.setMass(1)
    def getDistance(self):
        self.Dist_x = np.array( X - self.x )
        self.Dist_y = np.array( Y - self.y )
        self.Distance = np.sqrt(self.Dist_x**2 + self.Dist_y**2)
        self.getGravity()
    def getGravity(self):
        self.Grav_x = np.array(- G * self.Mass / self.Dist_x)
        self.Grav_y = np.array(- G * self.Mass / self.Dist_y)
        self.Gravity = np.sqrt(self.Grav_x**2 + self.Grav_y**2)
    def setPos(self,x,y):
        self.x = x
        self.y = y
        self.getDistance()
    def setMass(self,m):
        self.Mass = m

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
for _ in np.arange(2): Body.append(AstralObject())
Body[0].setPos(0,0)
Body[1].setPos(1,0)

GRAVITY = getGRAVITY(Body)
plt.figure(1)
Gravity_level = np.logspace(Body[0].Gravity.min(),Body[0].Gravity.max(),10)
plt.contourf(X,Y,Body[0].Gravity)
plt.plot(Body[0].x,Body[0].y,"r*")
plt.plot(Body[1].x,Body[1].y,"r*")
plt.show()

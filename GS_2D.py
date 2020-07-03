"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt

def getPOTENTIAL(body_list):
    return sum(_.Potential for _ in body_list)

class AstralObject:
    def __init__(self):
        self.Mass = int()
        self.x = int()
        self.y = int()
        self.Vx = int()
        self.Vy = int()
        self.Distance = np.array(0)
        self.Potential = np.array(0)
        self.IsMoving = True
        self.setMass(1)
        self.setPos(0,0)
    def getDistance(self):
        self.Distance = np.array(np.sqrt((X-self.x)**2 + (Y-self.y)**2))
    def getPotential(self):
        self.Potential = - G*self.Mass/self.Distance**3
    def setPos(self,x,y):
        self.x = x
        self.y = y
        self.getDistance()
        self.getPotential()
    def setMass(self,m):
        self.Mass = m
        self.getPotential()

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
plt.figure(1)
plt.contourf(X,Y,np.log(abs(POTENTIAL)))
plt.plot(Body[0].x,Body[0].y,"r*")
plt.show()

"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt

class AstralObject:
    def __init__(self):
        self.Mass = int()
        self.x = int()
        self.y = int()
        self.Vx = int()
        self.Vy = int()
        self.Distance = int()
        self.Potential = int()
        self.IsMoving = True
        self.setMass(1)
        self.setPos(0,0)
    def getDistance(self):  self.Distance = np.sqrt((X-self.x)**2 + (Y-self.y)**2)
    def getPotential(self): self.Potential = - G*self.Mass/self.Distance**3
    def setPos(self,x,y):
        self.x = x
        self.y = y
        self.getDistance()
        self.getPotential()
    def setMass(self,m):
        self.Mass = m

G = 1

# Maillage
dx, x_range = 0.1, 10
dy, y_range = 0.1, 10
dt, tf = 0.1, 10
X,Y = np.meshgrid(
    np.arange(-x_range,x_range,dx),
    np.arange(-y_range,y_range,dy))
t = np.arange(0,tf,dt)
Nt, Nx, Ny = len(t), len(X), len(Y)

A1 = AstralObject()
A1.setPos(3,7)
plt.figure(1)
plt.contourf(X,Y,np.log(abs(A1.Potential)))
plt.plot(A1.x,A1.y,"r*")
plt.show()
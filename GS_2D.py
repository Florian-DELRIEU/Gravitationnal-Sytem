"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import numpy.ma as ma  # masque
import matplotlib.pyplot as plt

def getGRAVITY(body_list): return sum(_.Gravity for _ in body_list)

class AstralObject:
    def __init__(self):
        self.Mass = int()
        self.x = int()
        self.y = int()
        self.Vx = int()
        self.Vy = int()
        self.Ax = int()
        self.Ay = int()
        self.IsMoving = True
        self.Distance = np.array(0)
        self.Grav_x = np.array(0)
        self.Grav_y = np.array(0)
        self.ix = int()  # Indice de la position
        self.iy = int()
        self.setPos(0,0)
        self.setMass(1)
    def getDistance(self):
        self.Distance = ma.masked_equal(np.sqrt((X-self.x)**2 + (Y-self.y)**2),0)
        self.getGravity()
    def getGravity(self):
        self.Grav_x = -G*self.Mass/self.Distance**3 * (X-self.x)
        self.Grav_y = -G*self.Mass/self.Distance**3 * (Y-self.y)
    def getPosIndic(self):
        self.ix = np.where( abs(X[0,:]-self.x) == min(abs(X[0,:]-self.x)))
        self.iy = np.where( abs(Y[:,0]-self.y) == min(abs(Y[:,0]-self.y)))
    def setPos(self,x,y):
        self.x = x
        self.y = y
        self.getDistance()
        self.getPosIndic()
    def setMass(self,m):
        self.Mass = m
        self.getGravity()
# Global Parametres
G = 1  # Constante Gravitationnelle
Body = list()

# Maillage
dx, x_range = 1, 10
dy, y_range = 1, 10
dt, tf = 0.1, 10
X,Y = np.meshgrid(
    np.arange(-x_range,x_range,dx),
    np.arange(-y_range,y_range,dy))
t = np.arange(0,tf,dt)
Nt, Nx, Ny = len(t), len(X), len(Y)


# Testing
for _ in np.arange(2): Body.append(AstralObject())
Body[0].setPos(0,0)
Body[0].setMass(1)
Body[0].IsMoving = False
Body[1].setPos(1,0)
Body[1].setMass(0)

# Plotting
msk_Grav_x = ma.masked_outside(Body[0].Grav_x,0.08,-0.08)  # Masque les valeurs hors des limites
msk_Grav_y = ma.masked_outside(Body[0].Grav_y,0.08,-0.08)
plt.figure(1)
#plt.quiver(X,Y,Body[0].Grav_x,Body[0].Grav_y)
plt.quiver(X,Y,msk_Grav_x,msk_Grav_y)
#plt.plot(Body[0].x,Body[0].y,"r*")
#plt.plot(Body[1].x,Body[1].y,"r*")
plt.show()

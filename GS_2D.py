"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import numpy.ma as ma  # masque
import matplotlib.pyplot as plt

def GRAVITYFIELD(body_list):
    return sum(_.Grav_x for _ in body_list) , sum(_.Grav_y for _ in body_list)

class AstralObject:
    def __init__(self):
        self.Mass = float()
        self.x = float(0)
        self.y = float(0)
        self.Vx = float(0)
        self.Vy = float(0)
        self.Ax = float(0)
        self.Ay = float(0)
        self.radius = float(0)
        self.IsMoving = True
        self.Distance = np.array(0)
        self.msk_Distance = np.array(0)
        self.Grav_x = np.array(0)
        self.Grav_y = np.array(0)
        self.ix = float()  # Indice de la position
        self.iy = float()
        self.setRadius(2.3)
        self.setPos(0,0)
        self.setMass(1)
    def __repr__(self):
        txt = """Astral Body
            - Pos = ({} , {})
            - Mass = {}
        """.format(self.x,self.y,self.Mass)
        return txt
    def getDistance(self):
        self.Distance = np.sqrt((X-self.x)**2 + (Y-self.y)**2)
        if self.radius != 0: msk_value = self.radius
        else:                msk_value = 1e-6
        self.msk_Distance = ma.masked_less(np.sqrt((X-self.x)**2 + (Y-self.y)**2),msk_value)
        self.getGravityfield()
    def getGravityfield(self):
    # Champs de gravite induit de la presence de ce corps
        self.Grav_x = -G*self.Mass/self.msk_Distance**3 * (X-self.x)
        self.Grav_y = -G*self.Mass/self.msk_Distance**3 * (Y-self.y)
    def getPosIndic(self):
        self.ix = np.where( abs(X[0,:]-self.x) == min(abs(X[0,:]-self.x)))
        self.iy = np.where( abs(Y[:,0]-self.y) == min(abs(Y[:,0]-self.y)))
    def setPos(self,x,y):
        self.x = x
        self.y = y
        self.getDistance()
        self.getPosIndic()
    def setRadius(self,r):
        self.radius = r
        self.getDistance()
    def setVel(self,Vx,Vy):
        self.Vx = Vx
        self.Vy = Vy
    def getAcc(self):
    # Gravité des autres corps - celle de lui meme / par sa masse
        self.Ax = (GRAV_x[self.ix, self.iy] - self.Grav_x[self.ix, self.iy])/self.Mass
        self.Ay = (GRAV_y[self.ix, self.iy] - self.Grav_y[self.ix, self.iy])/self.Mass
    def setMass(self,m):
        self.Mass = m
        self.getGravityfield()
    def refresh(self,dt):
        self.getAcc()
        self.setVel( self.Vx+self.Ax*dt , self.Vy+self.Ay*dt )
        self.setPos( self.x+self.Vx*dt , self.y+self.Vy*dt )

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
for _ in np.arange(2): Body.append(AstralObject())  # Ajout des corps celestes
# 2 corps a et b
Body[0].setPos(0,0)
Body[0].setMass(1)
Body[0].IsMoving = False
Body[1].setPos(6,3)
Body[1].setMass(0)
a,b = Body[0],Body[1]

# Simulation
GRAV_x , GRAV_y = GRAVITYFIELD(Body)
a.getAcc()
b.getAcc()


# Plotting
msk_outside_value = 0.1
msk_Grav_x = ma.masked_outside(Body[0].Grav_x,msk_outside_value,-msk_outside_value,True)  # Masque les valeurs hors des limites
msk_Grav_y = ma.masked_outside(Body[0].Grav_y,msk_outside_value,-msk_outside_value,True)
plt.figure(1)
#plt.quiver(X,Y,Body[0].Grav_x,Body[0].Grav_y)
plt.quiver(X,Y,GRAV_x,GRAV_y)
#plt.quiver(X,Y,msk_Grav_x,msk_Grav_y)
plt.plot(Body[0].x,Body[0].y,"r*")
plt.plot(Body[1].x,Body[1].y,"r*")
plt.show()

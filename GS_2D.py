"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt

def GRAVITYFIELD(body_list): pass

class AstralBody:
    def __init__(self):
    # Variable definitions
        self.Mass = float(0)
        self.x = float(0)
        self.y = float(0)
        self.vx = float(0)
        self.vy = float(0)
        self.ax = float(0)
        self.ay = float(0)
        self.Body_list = list()
        self.IsMoving = True
    def refresh(self,dt):
        if self.IsMoving:
            self.Body_list = Body.copy() # Body_list.remove(self) ne marche plus après ...
            self.Body_list.remove(self)
            self.ax, self.ay = 0,0
            for this_body in self.Body_list:
                cur_distance = np.sqrt((this_body.x - self.x)**2 + (this_body.y - self.y)**2)
                self.ax += - G * this_body.Mass / cur_distance**3 * (self.x - this_body.x)
                self.ay += - G * this_body.Mass / cur_distance**3 * (self.y - this_body.y)
                self.vx += self.ax*dt
                self.vy += self.ay*dt
                self.x += self.vx*dt
                self.y += self.vy*dt
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


# Creating body
for _ in np.arange(2):Body.append(AstralBody())  # Ajout des corps celestes
a = Body[0]
b = Body[1]
a.Mass,b.Mass = 1,1
a.IsMoving = False
b.x,b.y = 1,0
b.vx,b.vy = 0,1

plt.figure(1)
#plt.clf()
for this_body in Body:
    plt.plot(this_body.x,this_body.y,"r*")
plt.show()

# Simulation
for _ in t:
    for this_body in Body: this_body.refresh(dt)
    plt.pause(dt)
    plt.plot(b.x,b.y,'b+')

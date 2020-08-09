"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt
plt.ion()

def GRAVITYFIELD(body_list): pass

class AstralBody:
    def __init__(self,Domain):
        self.G = Domain.G
        self.Domain = Domain
    # Variable definitions
        self.Mass = float(0)
        self.x = float(0)
        self.y = float(0)
        self.vx = float(0)
        self.vy = float(0)
        self.ax = float(0)
        self.ay = float(0)
        self.Body_list = Domain.BodyList.copy()
        self.IsMoving = True
        self.Color = "b"
        self.Mark = "o"
        self.Trajectory = list()
    def refresh(self,dt):
        if self.IsMoving:
            self.Body_list = self.Domain.BodyList.copy() # Body_list.remove(self) ne marche plus après ...
            self.Body_list.remove(self)
            self.ax, self.ay = 0,0
            for this_body in self.Body_list:
                cur_distance = np.sqrt((this_body.x - self.x)**2 + (this_body.y - self.y)**2)
                self.ax += - self.G * this_body.Mass / cur_distance**3 * (self.x - this_body.x)
                self.ay += - self.G * this_body.Mass / cur_distance**3 * (self.y - this_body.y)
                self.vx += self.ax*dt
                self.vy += self.ay*dt
                self.x += self.vx*dt
                self.y += self.vy*dt
            self.Trajectory.append((self.x,self.y))
    def __repr__(self):
        txt = """Astral Body
            - Pos = ({} , {})
            - Mass = {}
        """.format(self.x,self.y,self.Mass)
        return txt

class Universe:
    def __init__(self):
        self.G = 1
        self.dx = .1
        self.dy = .1
        self.dt = .01
        self.x_range = 10
        self.y_range = 10
        self.tf = 1
        self.X,self.Y = np.meshgrid(np.arange(-self.x_range,self.x_range,self.dx),
                                    np.arange(-self.y_range,self.y_range,self.dy))
        self.t = np.arange(0,self.tf,self.dt)
        self.BodyList = list()
########################################################################################################################
########################################################################################################################
# Global Parametres
D = Universe()
Body = list()
D.BodyList = Body

# Creating body
for _ in np.arange(2):Body.append(AstralBody(D))  # Ajout des corps celestes
a = Body[0]
a.Color,a.Mark = "r","o"
b = Body[1]
a.Mass,b.Mass = 10,1
a.IsMoving = True
a.x,a.y = 0,0
b.x,b.y = 1,0
a.vx,a.vy = 0,0
b.vx,b.vy = 0,2.5

plt.figure(1)
plt.clf()
for this_body in Body:
    plt.plot(this_body.x,this_body.y,"r*")
plt.show()

# Simulation
for _ in D.t:
    plt.pause(D.dt)
    plt.clf()
    for this_body in Body:
        this_body.refresh(D.dt)
        plt.plot(this_body.x,this_body.y,this_body.Color+this_body.Mark)
        plt.xlim(-3,3)
        plt.ylim(-3,3)
for this_body in Body:
    this_body.Trajectory = np.array(this_body.Trajectory)
    plt.plot(this_body.Trajectory[:,0],this_body.Trajectory[:,1],this_body.Color+"-")
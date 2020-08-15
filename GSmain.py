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
        self.Color = ""
        self.Mark = "o"
        self.Trajectory = list()
    def __repr__(self):
        txt = """Astral Body
            - Pos = ({} , {})
            - Mass = {}
        """.format(self.x,self.y,self.Mass)
        return txt
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
    def setbody(self,x,y,Mass):
        self.x = x
        self.y = y
        self.Mass = Mass
    def setvelocity(self,vx,vy):
        self.vx = vx
        self.vy = vy

class Universe:
    def __init__(self):
        self.G = 1
        self.dx = .1
        self.dy = .1
        self.dt = .1
        self.x_range = 10
        self.y_range = 10
        self.tf = 1
        self.X,self.Y = np.meshgrid(np.arange(-self.x_range,self.x_range,self.dx),
                                    np.arange(-self.y_range,self.y_range,self.dy))
        self.BodyList = list()
        self.t = np.array([])
        self.settime()
    def settime(self):
        self.t = np.arange(0,self.tf,self.dt)
########################################################################################################################
########################################################################################################################
# Global Parametres
D = Universe()
Body = list()
D.BodyList = Body

D.dt = 0.01
D.tf = 5
D.settime()
# Creating body
for _ in np.arange(2):Body.append(AstralBody(D))  # Ajout des corps celestes
a,b = Body[0],Body[1]
#c = Body[2]
a.setbody(0,0,50)
b.setbody(1,0,1)
#c.setbody(10,0,0)
a.IsMoving = False
b.setvelocity(0,np.sqrt(2*D.G*a.Mass)/1)
#c.setvelocity(0,0.3)


# Simulation
plt.figure(1)
FPS = 5
frame = 0
for _ in D.t:
    frame += 1
    if frame == 1/FPS:
        plt.pause(0.01)
        plt.clf()
        for this_body in Body:
            this_body.refresh(D.dt)
            plt.plot(this_body.x,this_body.y,this_body.Color+this_body.Mark)
            plt.title("{} / {}".format(_,D.tf))
            plt.xlim(-5,5)
            plt.ylim(-5,5)
            frame = 0
    else: pass
for this_body in Body:
    if this_body.IsMoving:
        this_body.Trajectory = np.array(this_body.Trajectory)
        plt.plot(this_body.Trajectory[:,0],this_body.Trajectory[:,1],this_body.Color+"-")
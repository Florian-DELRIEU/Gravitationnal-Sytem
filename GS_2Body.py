"""
Programme visant à simuler un system orbital avec 2 corps en utilisant GSmain.
"""
from GSmain import *
from MyPack.FFT import *
from MyPack.Convert import *

# Global Parametres
D = Domain()
D.dt = 0.02
D.tf = 1
D.settime(D.dt,D.tf)
dt = D.dt

# Creating bodies
a = AstralBody(D)
a.setbody(0,0,10)
a.IsMoving = True

b = AstralBody(D)
b.setbody(1,0,0.2)
b.setvelocity(0,np.sqrt(a.Mass))

c = AstralBody(D)
c.setbody(-2,0,0.1)
c.setvelocity(0,-np.sqrt(a.Mass/2))

# Simulation
plt.figure("Trajectory")
Bacc = np.array([])  # for record
Bxy = np.array([])  # for record
for _ in D.t:
    plt.pause(0.01)
    plt.clf()
    for this_body in D.BodyList:
        this_body.refresh(dt)
        this_body.Gvector(0.1)
        plt.plot(this_body.x,this_body.y,this_body.Color+this_body.Mark)
        plt.title("{} / {}".format(_,D.tf))
        plt.xlim(-5,5)
        plt.ylim(-5,5)
    Bxy = np.append(Bxy,np.sqrt(b.x**2 + b.y**2))
for this_body in D.BodyList:
    if this_body.IsMoving:
        this_body.Trajectory = np.array(this_body.Trajectory)
        plt.plot(this_body.Trajectory[:,0],this_body.Trajectory[:,1],this_body.Color+"-")

plt.figure("Acc")
plt.plot(D.t,b.Acceleration,"b-")
plt.figure("Dist")
plt.plot(D.t,Bxy,"b-")
plt.show()

path = "D:\OneDrive\Cours\Python\Etudes\Gravitationnal-Sytem\Datas\ "
A = dict()
A["t"] = D.t
A["x"] = a.Trajectory[0]
A["y"] = a.Trajectory[1]
A["vx"] = a.Speed[0]
A["vy"] = a.Speed[1]
A["ax"] = a.Acceleration[0]
A["ay"] = a.Acceleration[1]
Dict2CSV(A,path+"A.csv")
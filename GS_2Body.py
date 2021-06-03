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
        plt.plot(this_body.Kinetic["x"],this_body.Kinetic["y"],this_body.Color+"-")

plt.figure("Acc")
plt.plot(D.t,np.sqrt(b.Kinetic["ax"]**2+b.Kinetic["ay"]**2),"b-")
plt.figure("Dist")
plt.plot(D.t,np.sqrt(b.Kinetic["x"]**2+b.Kinetic["y"]**2),"b-")
plt.show()

path = "/Users/floriandelrieu/OneDrive/Cours/Python/Etudes/Gravitationnal-Sytem/Datas/"
Dict2CSV(a.Kinetic,path+"a_Kinetic.csv")
Dict2CSV(b.Kinetic,path+"b_Kinetic.csv")
Dict2CSV(c.Kinetic,path+"c_Kinetic.csv")
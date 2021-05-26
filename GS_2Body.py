"""
Programme visant à simuler un system orbital avec 2 corps en utilisant GSmain.
"""
from GSmain import *

# Global Parametres
D = Domain()

# Creating bodies
a = AstralBody(D)
a.setbody(0,0,1)
a.IsMoving = False

b = AstralBody(D)
b.setbody(1,0,1)
b.setvelocity(0,1)

# Simulation
plt.figure("Trajectory")
Bacc = np.array([])  # for record
Bxy = np.array([])  # for record
for _ in D.t:
    plt.pause(1)
    plt.clf()
    for this_body in Body:
        plt.arrow(b.x,b.y,b.ax,b.ay)
        this_body.refresh(D.dt)
        plt.plot(this_body.x,this_body.y,this_body.Color+this_body.Mark)
        plt.title("{} / {}".format(_,D.tf))
        plt.xlim(-5,5)
        plt.ylim(-5,5)
    Bacc = np.append(Bacc,np.sqrt(b.ax**2 + b.ay**2))
    Bxy = np.append(Bxy,np.sqrt(b.x**2 + b.y**2))
for this_body in Body:
    if this_body.IsMoving:
        this_body.Trajectory = np.array(this_body.Trajectory)
        plt.plot(this_body.Trajectory[:,0],this_body.Trajectory[:,1],this_body.Color+"-")

plt.figure("Acc")
plt.plot(D.t,Bacc,"b-")
plt.figure("Dist")
plt.plot(D.t,Bxy,"b-")
plt.show()
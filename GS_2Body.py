from GSmain import *

# Global Parametres
D = Universe()
Body = list()
D.BodyList = Body

D.dt = 0.05
D.tf = 3
D.settime()
# Creating body
for _ in np.arange(2):Body.append(AstralBody(D))  # Ajout des corps celestes
a,b = Body[0],Body[1]

a.setbody(0,0,1)
b.setbody(1,0,1)

a.IsMoving = False
b.setvelocity(0,1)

# Simulation
plt.figure("Trajectory")
for _ in D.t:
    plt.pause(0.1)
    plt.clf()
    for this_body in Body:
        this_body.refresh(D.dt)
        plt.plot(this_body.x,this_body.y,this_body.Color+this_body.Mark)
        plt.title("{} / {}".format(_,D.tf))
        plt.xlim(-5,5)
        plt.ylim(-5,5)
for this_body in Body:
    if this_body.IsMoving:
        this_body.Trajectory = np.array(this_body.Trajectory)
        plt.plot(this_body.Trajectory[:,0],this_body.Trajectory[:,1],this_body.Color+"-")
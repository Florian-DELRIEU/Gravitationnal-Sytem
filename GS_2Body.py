"""
Programme visant à simuler un system orbital avec 2 corps en utilisant GSmain.
"""
from GSmain import *
from MyPack.FFT import *
from MyPack.Convert import *
import time as t

start = t.time()
# Global Parametres
D = Domain()
D.dt = 1e-3
D.tf = 10
D.settime(D.dt,D.tf)
dt = D.dt

# Creating bodies
a = AstralBody(D)
a.setbody(-0.1,0,10)
a.setvelocity(0,np.sqrt(0.1))

b = AstralBody(D)
b.setbody(0.9,0,1)
b.setvelocity(0,np.sqrt(9))

c = AstralBody(D)
c.setbody(2,0,0.5)
c.setvelocity(0,np.sqrt(10/5))

# Simulation
for _ in D.t:
    for this_body in D.BodyList: this_body.refresh(dt)

path = "Datas/"
Dict2CSV(a.Kinetic,path+"a_Kinetic.csv")
Dict2CSV(b.Kinetic,path+"b_Kinetic.csv")

duration = t.time() - start
print("Simulation time {}".format(duration))
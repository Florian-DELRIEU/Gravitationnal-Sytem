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
a.setbody(0,0,10)
a.setvelocity(0,0)

b1 = AstralBody(D)
b1.setbody(1,0,0)
b1.setvelocity(0,np.sqrt(10))

b2 = AstralBody(D)
b2.setbody(2,0,0)
b2.setvelocity(0,np.sqrt(5))

b3 = AstralBody(D)
b3.setbody(5,0,0)
b3.setvelocity(0,np.sqrt(2))

# Simulation
for _ in D.t:
    for this_body in D.BodyList: this_body.refresh(dt)

path = "Datas/"
Dict2CSV(a.Kinetic,path+"a_Kinetic.csv")
Dict2CSV(b1.Kinetic,path+"b1_Kinetic.csv")
Dict2CSV(b2.Kinetic,path+"b2_Kinetic.csv")
Dict2CSV(b3.Kinetic,path+"b3_Kinetic.csv")

duration = t.time() - start
print("Simulation time {}".format(duration))
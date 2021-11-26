from GSmain import AstralBody,Domain
from GSplot import PlotAnimation
from MyPack_1_5.Saves.CSV import Dict2CSV
import os
os.chdir("../Datas/Minimal")

D = Domain()
D.settime(0.01,2)

A = AstralBody(D)
B = AstralBody(D)
A.setbody(-1,0,5)
B.setbody(+1,0,5)
A.setvelocity(0,1)
B.setvelocity(0,-1)

D.run_simulation()

A.SaveKinetic()
B.SaveKinetic("test")

PlotAnimation(["a_kinetic.csv","b_kinetic.csv"],True)
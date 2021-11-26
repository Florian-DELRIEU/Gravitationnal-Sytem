from GSmain import AstralBody,Domain
from GSplot import PlotAnimation
from MyPack_1_5.Saves.CSV import Dict2CSV
import os
os.chdir("../Datas/Minimal")

CSV_list = ["a_kinetic.csv","b_kinetic.csv"]

D = Domain()
D.settime(0.01,2)

A = AstralBody(D)
B = AstralBody(D)
A.setCI((-1,0),(0,1),5)
A.setCI((+1,0),(0,-1),5)

D.run_simulation()

A.SaveKinetic("A")
B.SaveKinetic("B")

PlotAnimation(CSV_list,True)
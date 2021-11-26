from GSmain import AstralBody,Domain
from GSplot import PlotAnimation
from MyPack_1_5.Saves.CSV import Dict2CSV
import os
os.chdir("../Datas/Minimal")

CSV_list = ["a_kinetic.csv","b_kinetic.csv"]

## Initialize
D = Domain(0.01,.5)
A = AstralBody(D,(-1,0),(0,+1),5)
B = AstralBody(D,(+1,0),(0,-1),5)

D.run_simulation()
A.SaveKinetic("A")
B.SaveKinetic("B")

PlotAnimation(CSV_list,True)
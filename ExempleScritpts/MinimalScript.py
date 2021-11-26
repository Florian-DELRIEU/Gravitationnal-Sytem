"""
FIXME
    - PlotAnimation need a CSV list
"""

from GSmain import AstralBody,Domain
from GSplot import PlotAnimation
from MyPack_1_5.Saves.CSV import Dict2CSV
import os
os.chdir("../Datas/Minimal")

## Initialize
D = Domain(0.01,.5)
A = AstralBody(D,(-1,0),(0,+1),5)
B = AstralBody(D,(+1,0),(0,-1),5)

D.run_simulation(save_data=True)

PlotAnimation(CSV_list,True)
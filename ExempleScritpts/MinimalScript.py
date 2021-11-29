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
A = AstralBody(D,CI_pos=(-1,0),CI_speed=(0,+1),mass=5)
A.set_filename("test")
B = AstralBody(D,CI_pos=(+1,0),CI_speed=(0,-1),mass=5)
D.run_simulation(save_data=True)
PlotAnimation(D.CSVList,True)
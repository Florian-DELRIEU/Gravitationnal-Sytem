"""
Programme visant à simuler un system orbital avec 4 corps en utilisant GSmain.
Systeme a étudier
"""
from GSmain import *
from GSplot import *
from MyPack.FFT import *
from MyPack.Convert import *
import time as t
import os

SIMULATION = False
PLOT = True
SAVE_FIGURE = True # Si PLOT == True
path = "Datas/SystemePesant3/"
os.chdir(path)
CSV_List  = [
    "A_Kinetic.csv",
    "A1_Kinetic.csv",
    "A2_Kinetic.csv",
    "A3_Kinetic.csv"
]

if SIMULATION:
    start = t.time()
    # Global Parametres
    D = Domain()
    D.dt = 1e-3
    D.tf = 40
    D.settime(D.dt,D.tf)
    dt = D.dt

    # Creating bodies
    A = AstralBody(D)
    A.setbody(0,0,10)
    A.setvelocity(0,-0.07274182218642697)

    a1 = 1
    a2 = 2
    a3 = 5

    A1 = AstralBody(D)
    A1.setbody(1,0,0.1)
    A1.setvelocity(0,1/a1 * np.sqrt(D.G*A.Mass*a1))

    A2 = AstralBody(D)
    A2.setbody(2,0,0.1)
    A2.setvelocity(0,1/a2 * np.sqrt(D.G*A.Mass*a2))

    A3 = AstralBody(D)
    A3.setbody(5,0,0.1)
    A3.setvelocity(0,1/a3 * np.sqrt(D.G*A.Mass*a3))

    # Simulation
    for i,_ in enumerate(D.t):
        for this_body in D.BodyList: this_body.refresh(dt)
        if i == 0.01*len(D.t): print("1 %")
        if i == 0.1*len(D.t): print("10 %")
        if i == 0.3*len(D.t): print("30 %")
        if i == 0.5*len(D.t): print("50 %")
        if i == 0.7*len(D.t): print("70 %")
        if i == 0.9*len(D.t): print("90 %")

    for i,csv in enumerate(CSV_List): Dict2CSV(D.BodyList[i].Kinetic,path+CSV_List[i])

    duration = t.time() - start
    print("Simulation time {}".format(duration))

if PLOT:
    plt.figure("Trajectory")
    plt.title("Trajectory")
    for i,csv in enumerate(CSV_List): PlotTrajectory(csv,mark="-")
    if SAVE_FIGURE: plt.savefig("Trajectory",dpi=300)

    plt.figure("Speed")
    plt.title("Speed")
    for i, csv in enumerate(CSV_List): PlotSpeed(csv,mark="-")
    if SAVE_FIGURE: plt.savefig("Speed", dpi=300)

    plt.figure("Distance")
    plt.title("Distance")
    for i, csv in enumerate(CSV_List): PlotDistance(csv,mark="-")
    if SAVE_FIGURE: plt.savefig("Distance", dpi=300)

    plt.figure("Numerical")
    plt.title("Numerical")
    for i, csv in enumerate(CSV_List): NumericalRelativeSpeed(csv,CSV_List,mark="-",label=csv.split("_")[0])
    if SAVE_FIGURE: plt.savefig("Numerical", dpi=300)
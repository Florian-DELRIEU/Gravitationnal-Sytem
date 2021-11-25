"""
1 corps non pesant en orbite et faisant des maneuvres autour d'un corps pesant
"""
from GSmain import *
from GSplot import *
from MyPack.FFT import *
from MyPack.Saves.CSV import *
import time as t
import os

path = "../Datas/"
SIMULATION = False
PLOT = True
SAVE_FIGURE = False # Si PLOT == True
ANIME = True

os.chdir(path)
CSVlist = [
        "a_Kinetic.csv",
        "b_Kinetic.csv"
    ]
if SIMULATION:
    start = t.time()
    # Global Parametres
    D = Domain()
    D.dt = 1e-3
    D.tf = 10
    D.settime(D.dt,D.tf)
    dt = D.dt

    # Creating bodies
    A = AstralBody(D)
    A.setbody(0,0,1)
    A.setvelocity(0,0)

    B = AstralBody(D)
    B.setbody(1,0,0)
    B.setvelocity(0,1)

    # Simulation
    for i,_ in enumerate(D.t):
        for this_body in D.BodyList: this_body.refresh(dt)
        if i == 0.01*len(D.t): print("1 %")
        if i == 0.1*len(D.t): print("10 %")
        if i == 0.3*len(D.t): print("30 %")
        if i == 0.5*len(D.t):
            print("50 %")
            B.DoBurn(-0.1,0)
        if i == 0.7*len(D.t): print("70 %")
        if i == 0.9*len(D.t): print("90 %")

    Dict2CSV(A.Kinetic,"A_Kinetic.csv")
    Dict2CSV(B.Kinetic,"B_Kinetic.csv")

    duration = t.time() - start
    print("Simulation time {}".format(duration))

if PLOT:
    plt.figure("Trajectory")
    PlotTrajectory("B_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Trajectory", dpi=300)

    plt.figure("Speed")
    PlotSpeed("B_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Speed", dpi=300)

    plt.figure("Distance")
    PlotDistance("B_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig("Distance", dpi=300)

    plt.figure("Numerical")
    NumericalRelativeSpeed("B_Kinetic.csv",CSVlist=CSVlist)
    if SAVE_FIGURE: plt.savefig("Numerical", dpi=300)

if ANIME:
    plt.figure(3)
    plt.xlim(-2,2)
    plt.ylim(-2,2)
    PlotAnimation(CSVlist,Trajectory=True,PPF=100, range=2)

os.chdir("../")
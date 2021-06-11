"""
1 corps non pesant en orbite et faisant des maneuvres autour d'un corps pesant
"""
from GSmain import *
from GSplot import *
from MyPack.FFT import *
from MyPack.Convert import *
import time as t

SIMULATION = True
PLOT = False
SAVE_FIGURE = False # Si PLOT == True
ANIME = True
path = "Datas/"

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
    A.setbody(0,0,10)
    A.setvelocity(0,0)

    a = 10

    B = AstralBody(D)
    B.setbody(a,0,0)
    B.setvelocity(0,1/a * np.sqrt(D.G*A.Mass*a))

    # Simulation
    for i,_ in enumerate(D.t):
        for this_body in D.BodyList: this_body.refresh(dt)
        if i == 0.01*len(D.t): print("1 %")
        if i == 0.1*len(D.t): print("10 %")
        if i == 0.3*len(D.t): print("30 %")
        if i == 0.5*len(D.t):
            print("50 %")
            B.DoBurn(0,0)
        if i == 0.7*len(D.t): print("70 %")
        if i == 0.9*len(D.t): print("90 %")

    Dict2CSV(B.Kinetic,path+"A_Kinetic.csv")
    Dict2CSV(B.Kinetic,path+"B_Kinetic.csv")

    duration = t.time() - start
    print("Simulation time {}".format(duration))

if PLOT:
    plt.figure("Trajectory")
    PlotTrajectory(path+"B_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Trajectory", dpi=900)

    plt.figure("Speed")
    PlotSpeed(path+"B_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Speed", dpi=900)

    plt.figure("Distance")
    PlotDistance(path+"B_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Distance", dpi=900)

    plt.figure("Numerical")
    NumericalRelativeSpeed(path+"B_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Numerical", dpi=900)

if ANIME:
    CSVlist = [
        path + "a_Kinetic.csv",
        path + "b_Kinetic.csv"
    ]
    plt.figure(3)
    plt.xlim(-15,15)
    plt.ylim(-15,15)
    PlotAnimation(CSVlist,Trajectory=True,PPF=100)
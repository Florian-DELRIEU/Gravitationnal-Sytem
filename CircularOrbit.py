"""
Programme visant à simuler un system orbital avec 2 corps en utilisant GSmain.
"""
from GSmain import *
from GSplot import *
from MyPack.FFT import *
from MyPack.Convert import *
import time as t

SIMULATION = True
PLOT = True
SAVE_FIGURE = False # Si PLOT == True
path = "Datas/"

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
    A.setvelocity(0,0)

    a1 = 1
    a2 = 2
    a3 = 5

    A1 = AstralBody(D)
    A1.setbody(1,0,0)
    A1.setvelocity(0,1/a1 * np.sqrt(D.G*A.Mass*a1))

    A2 = AstralBody(D)
    A2.setbody(2,0,0)
    A2.setvelocity(0,1/a2 * np.sqrt(D.G*A.Mass*a2))

    A3 = AstralBody(D)
    A3.setbody(5,0,0)
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

    Dict2CSV(A1.Kinetic,path+"A1_Kinetic.csv")
    Dict2CSV(A2.Kinetic,path+"A2_Kinetic.csv")
    Dict2CSV(A3.Kinetic,path+"A3_Kinetic.csv")

    duration = t.time() - start
    print("Simulation time {}".format(duration))

if PLOT:
    plt.figure("Trajectory")
    PlotTrajectory(path+"A1_Kinetic.csv")
    PlotTrajectory(path+"A2_Kinetic.csv")
    PlotTrajectory(path+"A3_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Trajectory", dpi=900)

    plt.figure("Speed")
    PlotSpeed(path+"A1_Kinetic.csv")
    PlotSpeed(path+"A2_Kinetic.csv")
    PlotSpeed(path+"A3_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Speed", dpi=900)

    plt.figure("Distance")
    PlotDistance(path+"A1_Kinetic.csv")
    PlotDistance(path+"A2_Kinetic.csv")
    PlotDistance(path+"A3_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Distance", dpi=900)

    plt.figure("Numerical")
    NumericalRelativeSpeed(path+"A1_Kinetic.csv")
    NumericalRelativeSpeed(path+"A2_Kinetic.csv")
    NumericalRelativeSpeed(path+"A3_Kinetic.csv")
    if SAVE_FIGURE: plt.savefig(path + "Numerical", dpi=900)
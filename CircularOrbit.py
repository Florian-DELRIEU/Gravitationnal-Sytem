"""
Programme visant à simuler un system orbital avec 2 corps en utilisant GSmain.
"""
from GSmain import *
from GSplot import *
from MyPack.FFT import *
from MyPack.Convert import *
import time as t

SIMULATION = False
PLOT = False

if SIMULATION:
    start = t.time()
    # Global Parametres
    D = Domain()
    D.dt = 1e-3
    D.tf = 40
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

    path = "Datas/CircularOrbit1/"
    Dict2CSV(a.Kinetic,path+"a_Kinetic.csv")
    Dict2CSV(b1.Kinetic,path+"b1_Kinetic.csv")
    Dict2CSV(b2.Kinetic,path+"b2_Kinetic.csv")
    Dict2CSV(b3.Kinetic,path+"b3_Kinetic.csv")

    duration = t.time() - start
    print("Simulation time {}".format(duration))

if PLOT:
    plt.figure("Trajectory")
    PlotTrajectory(path+"a_Kinetic.csv")
    PlotTrajectory(path+"b1_Kinetic.csv")
    PlotTrajectory(path+"b2_Kinetic.csv")
    PlotTrajectory(path+"b3_Kinetic.csv")

    plt.figure("Speed")
    PlotSpeed(path+"a_Kinetic.csv")
    PlotSpeed(path+"b1_Kinetic.csv")
    PlotSpeed(path+"b2_Kinetic.csv")
    PlotSpeed(path+"b3_Kinetic.csv")

    plt.figure("Distance")
    PlotDistance(path+"a_Kinetic.csv")
    PlotDistance(path+"b1_Kinetic.csv")
    PlotDistance(path+"b2_Kinetic.csv")
    PlotDistance(path+"b3_Kinetic.csv")

    plt.figure("Numerical")
    NumericalRelativeSpeed(path+"a_Kinetic.csv")
    NumericalRelativeSpeed(path+"b1_Kinetic.csv")
    NumericalRelativeSpeed(path+"b2_Kinetic.csv")
    NumericalRelativeSpeed(path+"b3_Kinetic.csv")
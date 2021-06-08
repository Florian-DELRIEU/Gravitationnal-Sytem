"""
Simulation de 2 corps pesant en orbite circulaire
"""
from GSmain import *
from GSplot import *
from MyPack.FFT import *
from MyPack.Convert import *
import time as t

SIMULATION = False
PLOTTING = True

if SIMULATION:
    start = t.time()
    # Global Parametres
    D = Domain()
    D.dt = 1e-4
    D.tf = 20
    D.settime(D.dt,D.tf)
    dt = D.dt

    a = AstralBody(D)
    b = AstralBody(D)
    a.setbody(-1,0,10)
    b.setbody(1,0,10)

    a.setvelocity(0,np.sqrt(b.Mass)/2)
    b.setvelocity(0,-np.sqrt(a.Mass)/2)

    # Simulation
    for i,_ in enumerate(D.t):
        for this_body in D.BodyList: this_body.refresh(dt)
        if i == 0.01*len(D.t): print("1 %")
        if i == 0.1*len(D.t): print("10 %")
        if i == 0.3*len(D.t): print("30 %")
        if i == 0.5*len(D.t): print("50 %")
        if i == 0.7*len(D.t): print("70 %")
        if i == 0.9*len(D.t): print("90 %")

    path = "Datas/"
    Dict2CSV(a.Kinetic,path+"a_Kinetic.csv")
    Dict2CSV(b.Kinetic,path+"b_Kinetic.csv")

    #End of simulation
    duration = t.time() - start
    print("Simulation time {}".format(duration))

if PLOTTING:
    path = "Datas/OrbiteBinaire1_dt1e-2"
    plt.figure("Trajectory")
    PlotTrajectory(path + "a_Kinetic.csv")
    PlotTrajectory(path + "b_Kinetic.csv")

    plt.figure("Speed")
    PlotSpeed(path + "a_Kinetic.csv")
    PlotSpeed(path + "b_Kinetic.csv")

    plt.figure("Distance")
    PlotDistance(path + "a_Kinetic.csv")
    PlotDistance(path + "b_Kinetic.csv")

    plt.figure("Numerical")
    NumericalRelativeSpeed(path + "a_Kinetic.csv")
    NumericalRelativeSpeed(path + "b_Kinetic.csv")
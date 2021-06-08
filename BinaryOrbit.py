"""
Simulation de 2 corps pesant en orbite circulaire
"""
from GSmain import *
from GSplot import *
from MyPack.FFT import *
from MyPack.Convert import *
import time as t

SIMULATION = True
PLOTTING = True

if SIMULATION:
    start = t.time()
    # Global Parametres
    D = Domain()
    D.dt = 1e-3
    D.tf = 30
    D.settime(D.dt,D.tf)
    dt = D.dt

    # Corps A
    a = AstralBody(D)
    a.setbody(-0.1,0,10)
    a.setvelocity(0,-np.sqrt(0.1))
    # Corps B
    b = AstralBody(D)
    b.setbody(0.9,0,1)
    b.setvelocity(0,np.sqrt(9))

    # Simulation
    for _ in D.t:
        for this_body in D.BodyList: this_body.refresh(dt)

    path = "Datas/"
    Dict2CSV(a.Kinetic,path+"a_Kinetic.csv")
    Dict2CSV(b.Kinetic,path+"b_Kinetic.csv")

    #End of simulation
    duration = t.time() - start
    print("Simulation time {}".format(duration))

if PLOTTING:
    path = "Datas/Orbite binaire stable dt1e-2/"
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
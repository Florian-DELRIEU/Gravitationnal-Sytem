"""
Simulation de 2 corps pesant en orbite circulaire de même masse et répartie sur un cerlce de rayon :a:
"""
from GSmain import *
from GSplot import *
from MyPack.FFT import *
from MyPack.Convert import *
import time as t

SIMULATION = True
PLOTTING = True
SAVE_FIGURE = False # Si PLOTTING == True
COMPARE = False
path = "Datas/"


if SIMULATION:
    start = t.time()
    # Global Parametres
    D = Domain()
    D.dt = 1e-2
    D.tf = 20
    D.settime(D.dt,D.tf)
    dt = D.dt

    AB = 1
    a = AstralBody(D)
    b = AstralBody(D)
    a.setbody(-1,0,10)
    b.setbody(1,0,10)
    a.Mark = "c-"
    b.Mark = "r-"
    Vorb_A = np.sqrt(D.G*b.Mass / (2*AB) )
    Vorb_B = np.sqrt(D.G*a.Mass / (2*AB) )
    a.setvelocity(0,Vorb_A)
    b.setvelocity(0,Vorb_B)

    # Simulation
    for i,_ in enumerate(D.t):
        for this_body in D.BodyList: this_body.refresh(dt)
        if i == 0.01*len(D.t): print("1 %")
        if i == 0.1*len(D.t): print("10 %")
        if i == 0.3*len(D.t): print("30 %")
        if i == 0.5*len(D.t): print("50 %")
        if i == 0.7*len(D.t): print("70 %")
        if i == 0.9*len(D.t): print("90 %")

    Dict2CSV(a.Kinetic,path+"a_Kinetic.csv")
    Dict2CSV(b.Kinetic,path+"b_Kinetic.csv")

    #End of simulation
    duration = t.time() - start
    print("Simulation time {}".format(duration))

if PLOTTING:
    plt.figure("Trajectory")
    PlotTrajectory(path + "a_Kinetic.csv",mark="r-")
    PlotTrajectory(path + "b_Kinetic.csv",mark="b-")
    if SAVE_FIGURE: plt.savefig(path+"Trajectory",dpi=900)

    plt.figure("Speed")
    PlotSpeed(path + "a_Kinetic.csv",mark="r-")
    PlotSpeed(path + "b_Kinetic.csv",mark="b-")
    if SAVE_FIGURE: plt.savefig(path+"Speed", dpi=900)

    plt.figure("Distance")
    PlotDistance(path + "a_Kinetic.csv",mark="r-")
    PlotDistance(path + "b_Kinetic.csv",mark="b-")
    if SAVE_FIGURE: plt.savefig(path+"Distance", dpi=900)

    plt.figure("Numerical")
    NumericalRelativeSpeed(path + "a_Kinetic.csv",mark="r-")
    NumericalRelativeSpeed(path + "b_Kinetic.csv",mark="b-")
    if SAVE_FIGURE: plt.savefig(path+"Numerical", dpi=900)

if COMPARE:
    plt.figure(1)
    plt.title("Distance de A par rapport à l'origine")
    path = "Datas/OrbiteBinaire1a/"
    PlotDistance(path + "a_Kinetic.csv", mark="k-",label="case 1A")
    path = "Datas/OrbiteBinaire1b/"
    PlotDistance(path + "a_Kinetic.csv", mark="k--",label="case 1B")

    plt.figure(2)
    plt.title("NRS pour A dans 2 cas")
    path = "Datas/OrbiteBinaire1a/"
    NumericalRelativeSpeed(path + "a_Kinetic.csv", mark="k-", label="case 1A")
    path = "Datas/OrbiteBinaire1b/"
    NumericalRelativeSpeed(path + "a_Kinetic.csv", mark="k--", label="case 1B")
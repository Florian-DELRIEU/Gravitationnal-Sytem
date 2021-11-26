"""
Simulation de 2 corps pesant en orbite circulaire de même masse et répartie sur un cerlce de rayon :a:
"""
from GSmain import *
from GSplot import *
from MyPack_1_5.FFT import *
from MyPack_1_5.Saves.CSV import *
import time as t
import os
os.chdir("../Datas/OrbiteBinaire1c/")
SIMULATION = False
PLOTTING = True
SAVE_FIGURE = True # Si PLOTTING == True
COMPARE = False
ANIME = False
CSV_List = [  # Listes des fichiers CSV de sauvegarde
    "a_Kinetic.csv",
    "b_Kinetic.csv"
]
Mark_List = ["r","b"]

if SIMULATION:
    start = t.time()
    # Global Parametres
    D = Domain()
    D.dt = 1e-3
    D.tf = 20
    D.settime(D.dt,D.tf)
    dt = D.dt

    AB = 10
    a = AstralBody(D)
    b = AstralBody(D)
    a.setbody(-AB/2,0,10)
    b.setbody(AB/2,0,10)
    a.Mark = "c-"
    b.Mark = "r-"
    Vorb_A = 1/AB * np.sqrt(D.G*b.Mass*AB/2)
    Vorb_B = 1/AB * np.sqrt(D.G*a.Mass*AB/2)
    a.setvelocity(0,Vorb_A)
    b.setvelocity(0,-Vorb_B)

    # Simulation
    for i,_ in enumerate(D.t):
        for this_body in D.BodyList: this_body.refresh(dt)
        if i == 0.01*len(D.t): print("1 %")
        if i == 0.1*len(D.t): print("10 %")
        if i == 0.3*len(D.t): print("30 %")
        if i == 0.5*len(D.t): print("50 %")
        if i == 0.7*len(D.t): print("70 %")
        if i == 0.9*len(D.t): print("90 %")

    Dict2CSV(a.Kinetic,"a_Kinetic.csv")
    Dict2CSV(b.Kinetic,"b_Kinetic.csv")

    #End of simulation
    duration = t.time() - start
    print("Simulation time {}".format(duration))

if PLOTTING:
    plt.figure("Trajectory")
    plt.title("Trajectory")
    for i,csv in enumerate(CSV_List): PlotTrajectory(csv,mark=Mark_List[i]+"-")
    if SAVE_FIGURE: plt.savefig("Trajectory",dpi=300)

    plt.figure("Speed")
    plt.title("Speed")
    for i, csv in enumerate(CSV_List): PlotSpeed(csv,mark=Mark_List[i]+"-")
    if SAVE_FIGURE: plt.savefig("Speed", dpi=300)

    plt.figure("Distance")
    plt.title("Distance")
    for i, csv in enumerate(CSV_List): PlotDistance(csv,mark=Mark_List[i]+"-")
    if SAVE_FIGURE: plt.savefig("Distance", dpi=300)

    plt.figure("Numerical")
    plt.title("Numerical")
    for i, csv in enumerate(CSV_List): NumericalRelativeSpeed(csv,CSV_List,mark=Mark_List[i]+"-")
    if SAVE_FIGURE: plt.savefig("Numerical", dpi=300)

if COMPARE:
    plt.figure(1)
    plt.title("Distance de A par rapport à l'origine")
    directory = "Datas/OrbiteBinaire1a/"
    PlotDistance(directory + "a_Kinetic.csv", mark="k-",label="case 1A")
    directory = "Datas/OrbiteBinaire1b/"
    PlotDistance(directory + "a_Kinetic.csv", mark="k--",label="case 1B")

    plt.figure(2)
    plt.title("NRS pour A dans 2 cas")
    directory = "Datas/OrbiteBinaire1a/"
    NumericalRelativeSpeed(directory + "a_Kinetic.csv", mark="k-", label="case 1A")
    directory = "Datas/OrbiteBinaire1b/"
    NumericalRelativeSpeed(directory + "a_Kinetic.csv", mark="k--", label="case 1B")

if ANIME:
    plt.figure(3)
    PlotAnimation(CSV_List,Trajectory=True,PPF=40)
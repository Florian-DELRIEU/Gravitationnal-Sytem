import matplotlib.pyplot as plt
from GSmain import *
from MyPack.Convert import *
import numpy as np

def PlotTrajectory(CSVfile,mark="",grid=True,label=""):
    """
    Extrait les données du :CSVfile: et affiche la trajectoire
    """
    Data = Csv2Dict(CSVfile)
    x = np.array(Data["x"])
    y = np.array(Data["y"])
    plt.plot(x,y,mark,label=label)
    if grid: plt.grid("both")
    if label is not "": plt.legend(loc="upper right")

def PlotDistance(CSVfile,mark="",grid=True,label=""):
    """
    Extrait les données du :CSVfile: et affiche la distance par rapport à l'origine
    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    x = np.array(Data["x"])
    y = np.array(Data["y"])
    plt.plot(t,np.sqrt(x**2+y**2),mark,label=label)
    if grid: plt.grid("both")
    if label is not "": plt.legend(loc="upper right")

def PlotSpeed(CSVfile,mark="",grid=True,label=""):
    """
    Extrait les données du :CSVfile: et affiche la vitesse
    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    vx = np.array(Data["vx"])
    vy = np.array(Data["vy"])
    plt.plot(t,np.sqrt(vx**2+vy**2),mark,label=label)
    if grid: plt.grid("both")
    if label is not "": plt.legend(loc="upper right")

def PlotAcceleration(CSVfile,mark="",grid=True,label=""):
    """
    Extrait les données du :CSVfile: et affiche l'accélération 
    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    ax = np.array(Data["ax"])
    ay = np.array(Data["ay"])
    plt.plot(t,np.sqrt(ax**2+ay**2),mark,label=label)
    if grid: plt.grid("both")
    if label is not "": plt.legend(loc="upper right")

def NumericalRelativeSpeed(CSVfile,CSVlist=list(),mark="",grid=True,label=""):
    """
    Trace le nombre v*dt/a pour chaque corps pour evaluer la précision numérique
    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    dt = t[0] - t[1]
    vx = np.array(Data["vx"])
    vy = np.array(Data["vy"])
    x = np.array(Data["x"])
    y = np.array(Data["y"])
    dist = Distance(CSVfile,CSVlist)
    min_dist_list = list()
    for i,_ in enumerate(dist):
        min_dist_list.append(dist[:,i].min())
    plt.semilogy(t,dist[:,],mark,label=label)
    if grid: plt.grid("both")
    if label is not "": plt.legend(loc="upper right")

def PlotAnimation(CSVlist, Trajectory=False, PPF=10):
    """
    :PPF: Pause per frame (ecart entre chaque frame affiché)
    """
    BodyList = list() # List de dict regroupant les données de tout les corps de la list voulue
    for file in CSVlist:
        Data = Csv2Dict(file)  # Unzip un csv à la fois
        # Extrait toute les données
        t = np.array(Data["Time"])
        x = np.array(Data["x"])
        y = np.array(Data["y"])
        vx = np.array(Data["vx"])
        vy = np.array(Data["vy"])
        ax = np.array(Data["ax"])
        ay = np.array(Data["ay"])
        BodyList.append(Data)  # Ajout dans la liste
    t = BodyList[0]["Time"]
    frame = 0
    for i,_ in enumerate(t):
        frame += 1
        if frame == PPF:
            plt.pause(0.1)
            plt.clf()
            for body in BodyList:
                plt.xlim(-15,15)
                plt.ylim(-15,15)
                plt.plot(body["x"][i],body["y"][i],"o")
                if Trajectory: plt.plot(np.array(body["x"][:i]),np.array(body["y"][:i]),"-")
            frame = 0

def Distance(CSV, CSVList=list()):
    CSVList_temp = CSVList.copy()
    if CSV in CSVList_temp: CSVList_temp.remove(CSV)
    DATA = Unzip(CSVList_temp)
    ListSize = len(CSVList_temp)
    x,y = np.array(Extract(CSV,"x")) , np.array(Extract(CSV,"y"))  #Extrait les coordonées du corps cible
    N = len(x)
    distance_list = list()
    for i,data in enumerate(DATA):
        x_temp = np.array(DATA[i]["x"])
        y_temp = np.array(DATA[i]["y"])
        dist_temp = np.sqrt((x-x_temp)**2 + (y-y_temp)**2)
        distance_list.append(dist_temp)
    return distance_list
#import matplotlib.pyplot as plt
from GSmain import *
from MyPack2.Saves.CSV import *
import numpy as np

def plot_trajectory(CSVfile, mark="", grid=True, label=""):
    """
    Extrait les données du :CSVfile: et affiche la trajectoire
    """
    Data = Csv2Dict(CSVfile)
    x = np.array(Data["x"])
    y = np.array(Data["y"])
    plt.plot(x,y,mark,label=label)
    if grid: plt.grid("both")
    if label != "": plt.legend(loc="upper right")

def plot_distance(CSVfile, mark="", grid=True, label=""):
    """
    Extrait les données du :CSVfile: et affiche la distance par rapport à l'origine
    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    x = np.array(Data["x"])
    y = np.array(Data["y"])
    plt.plot(t,np.sqrt(x**2+y**2),mark,label=label)
    if grid: plt.grid("both")
    if label != "": plt.legend(loc="upper right")

def plot_speed(CSVfile, mark="", grid=True, label=""):
    """
    Extrait les données du :CSVfile: et affiche la vitesse
    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    vx = np.array(Data["vx"])
    vy = np.array(Data["vy"])
    plt.plot(t,np.sqrt(vx**2+vy**2),mark,label=label)
    if grid: plt.grid("both")
    if label != "": plt.legend(loc="upper right")

def plot_acceleration(CSVfile, mark="", grid=True, label=""):
    """
    Extrait les données du :CSVfile: et affiche l'accélération 
    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    ax = np.array(Data["ax"])
    ay = np.array(Data["ay"])
    plt.plot(t,np.sqrt(ax**2+ay**2),mark,label=label)
    if grid: plt.grid("both")
    if label != "": plt.legend(loc="upper right")

def plot_numerical_relative_speed(CSVfile, CSVlist:list, mark="", grid=True, label=""):
    """
    Trace le nombre v*dt/a pour chaque corps pour evaluer la précision numérique
    """
    DATA = Csv2Dict(CSVfile)
    t = np.array(DATA["Time"])
    dt = t[0] - t[1]
    vx = np.array(DATA["vx"])
    vy = np.array(DATA["vy"])
    x = np.array(DATA["x"])
    y = np.array(DATA["y"])
    V = np.sqrt(vx**2 + vy**2)
    dist = np.array(distance_in_list(CSVfile, CSVlist))
    min_dist_list = []
    for i in np.arange(len(dist[0,:])):
        min_dist_list.append(dist[:,i].min())
    numeric_rel_speed = (V * dt) / np.array(min_dist_list)
    plt.semilogy(t,abs(numeric_rel_speed),mark,label=label)
    if grid: plt.grid("both")
    if label != "": plt.legend(loc="upper right")

def plot_animation(CSVlist, Trajectory=False, PPF=10, range=10):
    """
    :PPF: Pause per frame (ecart entre chaque frame affiché)
    """
    BodyList = [] # List de dict regroupant les données de tout les corps de la list voulue
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
                plt.xlim(-range,range)
                plt.ylim(-range,range)
                plt.plot(body["x"][i],body["y"][i],"o")
                if Trajectory: plt.plot(np.array(body["x"][:i]),np.array(body["y"][:i]),"-")
            frame = 0

def distance_in_list(CSV, CSVList:list):
    CSVList_temp = CSVList.copy()
    if CSV in CSVList_temp: CSVList_temp.remove(CSV)
    DATA = UnzipCSV(CSVList_temp)
    ListSize = len(CSVList_temp)
    x,y = np.array(ExtractCSV(CSV,"x")) , np.array(ExtractCSV(CSV,"y"))  #Extrait les coordonées du corps cible
    N = len(x)
    distance_list = []
    for i,data in enumerate(DATA):
        x_temp = np.array(DATA[i]["x"])
        y_temp = np.array(DATA[i]["y"])
        dist_temp = np.sqrt((x-x_temp)**2 + (y-y_temp)**2)
        distance_list.append(dist_temp)
    return distance_list

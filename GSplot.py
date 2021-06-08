import matplotlib.pyplot as plt
from GSmain import *
from MyPack.Convert import *
import numpy as np

def PlotTrajectory(CSVfile,mark="",grid=True,label=""):
    """

    """
    Data = Csv2Dict(CSVfile)
    x = np.array(Data["x"])
    y = np.array(Data["y"])
    plt.plot(x,y,mark,label=label)
    if grid: plt.grid("both")
    if label is not "": plt.legend(loc="upper right")

def PlotDistance(CSVfile,mark="",grid=True,label=""):
    """

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

    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    ax = np.array(Data["ax"])
    ay = np.array(Data["ay"])
    plt.plot(t,np.sqrt(ax**2+ay**2),mark,label=label)
    if grid: plt.grid("both")
    if label is not "": plt.legend(loc="upper right")

def NumericalRelativeSpeed(CSVfile,mark="",grid=True,label=""):
    """
    Trace le nombre v.dt/a pour chaque corps pour evaluer la précision numérique
    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    dt = t[0] - t[1]
    vx = np.array(Data["vx"])
    vy = np.array(Data["vy"])
    x = np.array(Data["x"])
    y = np.array(Data["y"])
    plt.semilogy(t,abs(np.sqrt(vx**2+vy**2)*dt/np.sqrt(x**2+y**2)),mark,label=label)
    if grid: plt.grid("both")
    if label is not "": plt.legend(loc="upper right")
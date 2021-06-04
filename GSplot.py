import matplotlib.pyplot as plt
from GSmain import *
from MyPack.Convert import *
import numpy as np

def PlotTrajectory(CSVfile,mark="",grid=True):
    """

    """
    Data = Csv2Dict(CSVfile)
    x = np.array(Data["x"])
    y = np.array(Data["y"])
    plt.plot(x,y,mark)
    if grid: plt.grid("both")

def PlotDistance(CSVfile,mark="",grid=True):
    """

    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    x = np.array(Data["x"])
    y = np.array(Data["y"])
    plt.plot(t,np.sqrt(x**2+y**2),mark)
    if grid: plt.grid("both")

def PlotSpeed(CSVfile,mark="",grid=True):
    """

    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    vx = np.array(Data["vx"])
    vy = np.array(Data["vy"])
    plt.plot(t,np.sqrt(vx**2+vy**2),mark)
    if grid: plt.grid("both")

def PlotAcceleration(CSVfile,mark="",grid=True):
    """

    """
    Data = Csv2Dict(CSVfile)
    t = np.array(Data["Time"])
    ax = np.array(Data["ax"])
    ay = np.array(Data["ay"])
    plt.plot(t,np.sqrt(ax**2+ay**2),mark)
    if grid: plt.grid("both")


###
path = "Datas\Circulaire a=1, G=1, m1=1 m2=10 dt=0.1/"
plt.figure("Trajectory")
PlotTrajectory(path+"a_mass1.csv")
PlotTrajectory(path+"b_mass10.csv")

plt.figure("Speed")
PlotSpeed(path+"a_mass1.csv")
PlotSpeed(path+"b_mass10.csv")

plt.figure("Distance")
PlotDistance(path+"a_mass1.csv")
PlotDistance(path+"b_mass10.csv")
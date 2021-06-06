from GSplot import *
plt.ion()

path = "Datas/Orbite binaire stable dt1e-2/"
plt.figure("Trajectory")
PlotTrajectory(path+"a_Kinetic.csv")
PlotTrajectory(path+"b_Kinetic.csv")

plt.figure("Speed")
PlotSpeed(path+"a_Kinetic.csv")
PlotSpeed(path+"b_Kinetic.csv")


plt.figure("Distance")
PlotDistance(path+"a_Kinetic.csv")
PlotDistance(path+"b_Kinetic.csv")

plt.figure("Numerical")
NumericalRelativeSpeed(path+"a_Kinetic.csv")
NumericalRelativeSpeed(path+"b_Kinetic.csv")
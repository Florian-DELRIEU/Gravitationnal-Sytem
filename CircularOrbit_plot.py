from GSplot import *

path = "Datas/"
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
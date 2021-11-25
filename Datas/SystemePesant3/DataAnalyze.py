import os
os.chdir("../../")
from MainFiles.GSplot import *
import MyPack.FFT as fft
plt.ion()
os.chdir("Datas/SystemePesant3/")

Plot_psdA = True


Files_list = [
    "A_Kinetic.csv",
    "A1_Kinetic.csv",
    "A2_Kinetic.csv",
    "A3_Kinetic.csv"
]
if Plot_psdA:
    File_used = Files_list[1]
    t,x,y = Extract(File_used,"Time"), Extract(File_used,"x"), Extract(File_used,"y")

    plt.figure("xy")
    plt.clf()
    plt.plot(t,x,"b-",label=File_used.split("_")[0])
    plt.plot(t,y,"r-",label=File_used.split("_")[0])
    plt.legend(loc="upper right")

    plt.figure("PSD xy")
    plt.clf()
    t,x,y = Extract(File_used,"Time"), Extract(File_used,"x"), Extract(File_used,"y")
    plt.plot(fft.freq(t),fft.psd(x,dB=True),"b-",label=File_used.split("_")[0])
    plt.plot(fft.freq(t),fft.psd(y,dB=True),"r-",label=File_used.split("_")[0])
    plt.legend(loc="upper right")

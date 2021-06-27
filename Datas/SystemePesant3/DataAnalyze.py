import os
os.chdir("../../")
from GSmain import *
from GSplot import *
import MyPack.FFT as fft
plt.ion()
os.chdir("Datas/SystemePesant3/")

Plot_PSD = True
Specific_Plot = False

Files_list = [
    "A_Kinetic.csv",
    "A1_Kinetic.csv",
    "A2_Kinetic.csv",
    "A3_Kinetic.csv"
]

if Plot_PSD:
    plt.figure("PSD")
    plt.clf()
    for file in Files_list:
        DATA = Csv2Dict(file)
        t = np.array(DATA["Time"])[1::100]  # Compresse les données par 100 et ne prends pas la 1ere valeur
        Vx, Vy = np.array(DATA["vx"])[1::100], np.array(DATA["vy"])[1::100]
        V = np.sqrt(Vx**2 + Vy**2)
        plt.semilogy(fft.freq(t), fft.psd(V), label=file[:2])  # file[:2] pour ne pas affiché le "_Kinetic.csv" à la fin
        plt.legend(loc="upper right")

if Specific_Plot:
    file = "A1_Kinetic.csv"
    plt.figure(1)
    plt.clf()
    DATA = Csv2Dict(file)
    t = np.array(DATA["Time"])[1::100]  #Compresse les données par 100 et ne prends pas la 1ere valeur
    Vx, Vy = np.array(DATA["vx"])[1::100], np.array(DATA["vy"])[1::100]
    V = np.sqrt(Vx**2 + Vy**2)
    plt.loglog(fft.freq(t), fft.psd(V), label=file[:2])  # file[:2] pour ne pas affiché le "_Kinetic.csv" à la fin
    plt.legend(loc="upper right")

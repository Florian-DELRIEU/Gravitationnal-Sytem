from GSmain import *
from GSplot import *
import MyPack.FFT as psd
plt.ion()

PSD_VitesseA = False
PSD_PositionA = True

if PSD_VitesseA:
    Data = Csv2Dict("A_Kinetic.csv")
    t = np.array(Data["Time"])
    vx = np.array(Data["vx"])
    vy = np.array(Data["vy"])
    V = np.sqrt(vx**2 + vy**2)

    psdV = psd.psd(V)
    freq = psd.freq(V,t)

    plt.title("PSD de la vitesse de l'étoile")
    plt.semilogx(freq,psdV)
    plt.xlabel("Frequence (Hz)")
    plt.ylabel("Amplitude")

if PSD_PositionA:
    Data = Csv2Dict("A_Kinetic.csv")
    t = np.array(Data["Time"])
    x = np.array(Data["x"])
    y = np.array(Data["y"])

    PSDx = psd.psd(x)
    PSDy = psd.psd(y)
    F = psd.freq(x, t)

    plt.title("PSD de la position de l'étoile")
    plt.loglog(F, PSDx)
    plt.xlabel("Frequence (Hz)")
    plt.ylabel("Amplitude")

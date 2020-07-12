"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt

# Maillage
dx, x_range = 0.1, 10
dy, y_range = 0.1, 10
X,Y = np.meshgrid(
    np.arange(-x_range,x_range,dx),
    np.arange(-y_range,y_range,dy))

# Parametres et corps
G = 1 # Constante Grav (6.7e8)
Pos = [
    (0,0), # x,y
    (1,0),]
Mass = [10,1]

Gx_func = lambda x, y:G*Mass[0]/abs(x - Pos[0][0])**3 * (x - Pos[0][0])
Gy_func = lambda x, y:G*Mass[0]/abs(y - Pos[0][1])**3 * (y - Pos[0][1])

plt.plot(Pos[0][0],Pos[0][1],"r*")
plt.plot(Pos[1][0],Pos[1][1],"r*")
plt.show()
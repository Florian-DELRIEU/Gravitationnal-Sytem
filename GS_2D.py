"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt

# Maillage
dx, x_range = 0.1, 10
dy, y_range = 0.1, 10
dt, t_range = 1, 100
X,Y = np.meshgrid(
    np.arange(-x_range,x_range,dx),
    np.arange(-y_range,y_range,dy))
t = np.arange(0,t_range,dt)

# Parametres et corps
G = 1 # Constante Grav (6.7e8)
Pos = [
    (0,0), # x,y
    (10,0),]
Mass = [10,1]

Gx_func = lambda x, y:  - G*Mass[0]/np.sqrt((x - Pos[0][0])**2+(y - Pos[0][1])**2)**3 * (x - Pos[0][0])
Gy_func = lambda x, y:  - G*Mass[0]/np.sqrt((x - Pos[0][0])**2+(y - Pos[0][1])**2)**3 * (y - Pos[0][1])

fig1 = plt.figure(1)
plt.plot(Pos[0][0],Pos[0][1],"r*")
plt.plot(Pos[1][0],Pos[1][1],"r*")
plt.show()

#CI
x,y = Pos[1][0],Pos[1][1]
vx,vy = 0,1
for _ in t:
    ax,ay = Gx_func(x,y) , Gy_func(x,y)
    vx += ax*dt
    vy += ay*dt
    x += vx*dt
    y += vy*dt

    # Refresh plot
    plt.plot(x, y, "b+")
    plt.pause(0.01)
    plt.show()
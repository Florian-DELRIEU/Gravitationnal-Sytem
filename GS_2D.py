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
G = 1 # Constante Grav (6.7e8)
Pos = [
    (0,0), # x,y
    (1,0),
]
Mass = [10,1]
Gravity_func = lambda x,y: G*Mass[0] / ( np.sqrt((x-Pos[0][0])**2+(y-Pos[0][1])**2) )**2
GRAVITY = Gravity_func(X,Y)
GRAVITY_contourlevel = np.logspace(GRAVITY.min(),GRAVITY.max(),30) # [0,.1,2,5,20]
plt.contourf(X,Y,GRAVITY,GRAVITY_contourlevel)
plt.plot(Pos[0][0],Pos[0][1],"r*")
plt.plot(Pos[1][0],Pos[1][1],"r*")
plt.show()
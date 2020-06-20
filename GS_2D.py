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
]
Mass = [1]
Potential = lambda x,y: G*Mass[0] / ( np.sqrt((x-Pos[0][0])**2+(y-Pos[0][1])**2) )**3
POTENT = Potential(X,Y)
POTENT_contour = np.linspace(POTENT.min(),POTENT.max(),10)
plt.contourf(X,Y,POTENT,[0,.1,2,5,20])
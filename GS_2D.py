"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np
import matplotlib.pyplot as plt

# Maillage
dx, x_range = 0.1, 10
dy, y_range = 0.1, 10
dt, tf = 0.1, 10
X,Y = np.meshgrid(
    np.arange(-x_range,x_range,dx),
    np.arange(-y_range,y_range,dy))
t = np.arange(0,tf,dt)
Nt, Nx, Ny = len(t), len(X), len(Y)
G = 1 # Constante Grav (6.7e8)
Pos = [
    (0,0), # x,y
]
Mass = [1]
Pot = lambda x,y: -G*Mass[0] / ( np.sqrt((X-Pos[0][0])**2+(Y-Pos[0][1])**2) )**3

plt.contourf(X,Y,Pot(X,Y))
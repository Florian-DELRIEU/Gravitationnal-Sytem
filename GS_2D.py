"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""
import numpy as np

# Maillage
dx, x_range = 0.1, 10
dy, y_range = 0.1, 10
dt, tf = 0.1, 10
X,Y = np.meshgrid(
    np.arange(-x_range,x_range,dx),
    np.arange(-y_range,y_range,dy))
t = np.arange(0,tf,dt)
Nt, Nx, Ny = len(t), len(X), len(Y)

Pos = [
    (0,0,   3), # x,y and mass
    (10,0,  1)
]
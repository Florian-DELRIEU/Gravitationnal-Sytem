"""
Programme simulant un sytème gravitationnel a N corps en 2D
"""

class AstralObject:
    def __init__(self):
        self.Mass = 1
        self.Vx = 0
        self.Vy = 0
        self.IsMoving = True

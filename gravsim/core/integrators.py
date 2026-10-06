"""Fixed-step symplectic integrators.

Each integrator advances (x, v, a) by ``dt``, where ``a`` is the acceleration at
``x`` (cached between steps: first-same-as-last). Fixed bodies have zero velocity
and zero acceleration, so their positions are left exactly unchanged.

The adaptive DOP853 integrator (scipy) is driven directly by ``simulation.py``.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

AccelFn = Callable[[np.ndarray], np.ndarray]


class Leapfrog:
    """Kick-drift-kick velocity Verlet: 2nd order, symplectic, time-reversible. 1 force evaluation per step."""

    name = "leapfrog"
    order = 2

    def step(self, x, v, a, dt, accel: AccelFn):
        v_half = v + (0.5 * dt) * a
        x_new = x + dt * v_half
        a_new = accel(x_new)
        v_new = v_half + (0.5 * dt) * a_new
        return x_new, v_new, a_new


class Yoshida4:
    """4th-order symplectic composition of three leapfrog steps (Yoshida 1990). 3 force evaluations per step."""

    name = "yoshida4"
    order = 4
    _cbrt2 = 2.0 ** (1.0 / 3.0)
    W1 = 1.0 / (2.0 - _cbrt2)
    W0 = -_cbrt2 / (2.0 - _cbrt2)

    def __init__(self):
        self._lf = Leapfrog()

    def step(self, x, v, a, dt, accel: AccelFn):
        for w in (self.W1, self.W0, self.W1):
            x, v, a = self._lf.step(x, v, a, w * dt, accel)
        return x, v, a


FIXED_STEP_INTEGRATORS = {"leapfrog": Leapfrog, "yoshida4": Yoshida4}
ADAPTIVE_INTEGRATORS = ("dop853",)
INTEGRATORS = tuple(FIXED_STEP_INTEGRATORS) + ADAPTIVE_INTEGRATORS

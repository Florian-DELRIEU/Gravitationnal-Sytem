import numpy as np
import pytest

from gravsim.core.body import Body
from gravsim.core.scenario import Scenario


def two_body(M=1.0, m=1e-3, r=1.0, e=0.0, at="periapsis", radii=(0.0, 0.0), star_fixed=False, zero_momentum=True):
    """Star at the origin, planet at (r, 0) on an apsis of an orbit of eccentricity e."""
    sc = Scenario(name="two-body")
    sc.add(Body("star", M, radius=radii[0], fixed=star_fixed))
    sc.add(Body("planet", m, position=[r, 0.0], radius=radii[1]))
    sc.set_orbital_velocity("planet", "star", e=e, at=at)
    if zero_momentum and not star_fixed:
        sc.zero_total_momentum()
    return sc


def relative_state(traj, i=1, j=0):
    return traj.pos[:, i] - traj.pos[:, j], traj.vel[:, i] - traj.vel[:, j]


def crossing_times(t, rel):
    """Times where the relative position crosses the +x axis counterclockwise (linear interpolation)."""
    x, y = rel[:, 0], rel[:, 1]
    k = np.nonzero((y[:-1] < 0) & (y[1:] >= 0) & (x[:-1] > 0))[0]
    frac = -y[k] / (y[k + 1] - y[k])
    return t[k] + frac * (t[k + 1] - t[k])


@pytest.fixture
def make_two_body():
    return two_body

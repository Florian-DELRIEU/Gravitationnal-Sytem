"""Unit system and physical constants.

Internal units: astronomical unit (AU), solar mass (Msun), Julian year (yr).
In these units Kepler's third law reads P^2 = a^3 / (M + m) when G = 4 pi^2,
which is the convention used here. It differs from the IAU value of G in these
units (39.4769...) by about 4e-5 in relative terms; change ``G`` if exactness
against real ephemerides matters.
"""

import math

G = 4.0 * math.pi**2  # AU^3 / (Msun yr^2)

# --- Conversions to SI ------------------------------------------------------
AU_M = 1.495978707e11  # m (IAU 2012, exact)
DAY_S = 86400.0
YEAR_S = 365.25 * DAY_S  # Julian year
DAY_YR = 1.0 / 365.25
M_SUN_KG = 1.988409870698051e30  # IAU nominal GM_sun / CODATA G
AU_PER_YR_IN_M_S = AU_M / YEAR_S  # 1 AU/yr = 4740.47 m/s

# --- Reference masses (Msun) -------------------------------------------------
M_SUN = 1.0
M_JUP = 1.0 / 1047.348644
M_EARTH = 1.0 / 332946.0487
M_MOON = M_EARTH / 81.30056

# --- Reference radii (AU) ----------------------------------------------------
R_SUN = 6.957e8 / AU_M
R_JUP = 7.1492e7 / AU_M
R_EARTH = 6.3781e6 / AU_M
R_MOON = 1.7374e6 / AU_M

MASS_UNITS = {"Msun": M_SUN, "MS": M_SUN, "Mjup": M_JUP, "MJ": M_JUP, "Mearth": M_EARTH, "ME": M_EARTH, "Mmoon": M_MOON}
LENGTH_UNITS = {"AU": 1.0, "Rsun": R_SUN, "RS": R_SUN, "Rjup": R_JUP, "RJ": R_JUP, "Rearth": R_EARTH, "RE": R_EARTH, "Rmoon": R_MOON, "km": 1e3 / AU_M}
TIME_UNITS = {"yr": 1.0, "day": DAY_YR, "d": DAY_YR}


def au_per_yr_to_m_s(v):
    return v * AU_PER_YR_IN_M_S


def m_s_to_au_per_yr(v):
    return v / AU_PER_YR_IN_M_S


def radius_from_density(mass, density_g_cm3):
    """Radius (AU) of a homogeneous sphere of ``mass`` (Msun) and given density (g/cm^3)."""
    if density_g_cm3 <= 0:
        raise ValueError("density must be positive")
    mass_kg = mass * M_SUN_KG
    rho = density_g_cm3 * 1000.0  # kg/m^3
    return (3.0 * mass_kg / (4.0 * math.pi * rho)) ** (1.0 / 3.0) / AU_M


def to_internal(value, unit, table):
    """Convert ``value`` expressed in ``unit`` using a conversion ``table``."""
    try:
        return value * table[unit]
    except KeyError:
        raise ValueError(f"unknown unit {unit!r}; expected one of {sorted(table)}") from None

"""Conserved quantities and the fidelity gauge.

Impulses change energy, momentum and angular momentum on purpose: their
contribution is subtracted (ledger) so that the gauge only measures numerical
error. A sample taken at an impulse time is the state *before* the impulse.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.forces import GravityModel
from ..core.trajectory import Trajectory


def model_of(traj: Trajectory) -> GravityModel:
    return GravityModel(traj.masses, traj.G, traj.radii, traj.fixed)


def kinetic_energy(traj: Trajectory) -> np.ndarray:
    return 0.5 * np.einsum("n,tnk,tnk->t", traj.masses, traj.vel, traj.vel)


def potential_energy(traj: Trajectory) -> np.ndarray:
    return model_of(traj).potential_energy(traj.pos)


def total_energy(traj: Trajectory) -> np.ndarray:
    return kinetic_energy(traj) + potential_energy(traj)


def linear_momentum(traj: Trajectory) -> np.ndarray:
    return np.einsum("n,tnk->tk", traj.masses, traj.vel)


def angular_momentum(traj: Trajectory, origin=(0.0, 0.0)) -> np.ndarray:
    """Total angular momentum (z component) about ``origin`` ((2,) or (T, 2))."""
    origin = np.asarray(origin, dtype=float)
    r = traj.pos - (origin[:, None, :] if origin.ndim == 2 else origin)
    return np.einsum("n,tn->t", traj.masses, r[..., 0] * traj.vel[..., 1] - r[..., 1] * traj.vel[..., 0])


def barycenter(traj: Trajectory) -> tuple[np.ndarray, np.ndarray]:
    m = traj.masses
    M = m.sum()
    if M == 0:
        raise ValueError("total mass is zero: no barycentre")
    return np.einsum("n,tnk->tk", m, traj.pos) / M, np.einsum("n,tnk->tk", m, traj.vel) / M


def _after(traj: Trajectory, t_event: float) -> np.ndarray:
    """Mask of samples that already include an event at ``t_event``."""
    t = traj.t
    return t > t_event + 1e-12 * np.maximum(1.0, np.abs(t))


def impulse_ledger(traj: Trajectory, origin=(0.0, 0.0)) -> dict[str, np.ndarray]:
    """Cumulative energy, momentum and angular momentum injected by impulses, per sample."""
    n = len(traj)
    dE, dL, dp = np.zeros(n), np.zeros(n), np.zeros((n, 2))
    for ev in traj.impulses:
        mask = _after(traj, ev.t)
        dE[mask] += ev.delta_energy
        dL[mask] += ev.delta_angular_momentum(origin)
        dp[mask] += ev.delta_momentum()
    return {"energy": dE, "angular_momentum": dL, "momentum": dp}


@dataclass
class Fidelity:
    """Relative drifts of the conserved quantities (None when not meaningful)."""

    t: np.ndarray
    energy: np.ndarray | None
    angular_momentum: np.ndarray | None
    momentum: np.ndarray | None
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, float | None]:
        def worst(x):
            return None if x is None else float(np.max(np.abs(x)))
        return {"energy": worst(self.energy), "angular_momentum": worst(self.angular_momentum),
                "momentum": worst(self.momentum)}


def fidelity(traj: Trajectory) -> Fidelity:
    notes = []
    n_fixed = int(traj.fixed.sum())
    if traj.masses.sum() == 0:
        return Fidelity(traj.t, None, None, None, ["aucune masse : rien à conserver"])

    # Energy (conserved even with fixed bodies and during overlaps).
    kin, pot = kinetic_energy(traj), potential_energy(traj)
    ledger = impulse_ledger(traj)
    E = kin + pot - ledger["energy"]
    scale = abs(E[0]) if abs(E[0]) > 1e-12 * (abs(kin[0]) + abs(pot[0])) else abs(kin[0]) + abs(pot[0])
    energy = (E - E[0]) / scale if scale > 0 else None

    # Angular momentum: about the origin, or about the fixed body if there is exactly one.
    if n_fixed == 0:
        origin = np.zeros(2)
    elif n_fixed == 1:
        origin = traj.pos[0, int(np.argmax(traj.fixed))]
        notes.append("moment cinétique calculé autour du corps fixe")
    else:
        origin = None
        notes.append("plusieurs corps fixes : moment cinétique non conservé")
    if origin is not None:
        L = angular_momentum(traj, origin) - impulse_ledger(traj, origin)["angular_momentum"]
        L_scale = np.sum(traj.masses * np.abs(
            (traj.pos[0, :, 0] - origin[0]) * traj.vel[0, :, 1] - (traj.pos[0, :, 1] - origin[1]) * traj.vel[0, :, 0]))
        L_scale = max(abs(L[0]), L_scale)
        ang = (L - L[0]) / L_scale if L_scale > 0 else None
    else:
        ang = None

    # Linear momentum: only without fixed bodies.
    if n_fixed == 0:
        p = linear_momentum(traj) - ledger["momentum"]
        p_scale = float(np.max(np.sum(traj.masses[None, :] * np.hypot(traj.vel[..., 0], traj.vel[..., 1]), axis=1)))
        mom = np.hypot(*(p - p[0]).T) / p_scale if p_scale > 0 else None
    else:
        mom = None
        notes.append("corps fixe : quantité de mouvement non conservée")

    if traj.impulses:
        notes.append(f"{len(traj.impulses)} poussée(s) retirée(s) du bilan")
    if traj.collisions:
        notes.append(f"{len(traj.collisions)} collision(s) : loi de sphère homogène pendant les recouvrements")
    return Fidelity(traj.t, energy, ang, mom, notes)

"""Newtonian gravity between N bodies in the plane.

Pair force law, with s_ij = max(R_i, R_j):
    r >= s_ij : F = G m_i m_j / r^2            (point masses, exact)
    r <  s_ij : F = G m_i m_j r / s_ij^3       (point inside a homogeneous sphere)

The inner law only applies once two bodies overlap (r < R_i + R_j already
counts as a collision), and removes the 1/r^2 singularity without an arbitrary
softening parameter. It is symmetric (action = reaction, momentum conserved)
and derives from the potential below (energy conserved), continuous at r = s:
    r >= s : U = -G m_i m_j / r
    r <  s : U = -G m_i m_j (3 s^2 - r^2) / (2 s^3)
"""

from __future__ import annotations

import numpy as np

_BATCH_ELEMENTS = 2_000_000  # max T*N*N per chunk in batch evaluations


class GravityModel:
    """Precomputed force model for a fixed set of bodies."""

    def __init__(self, masses, G: float, radii=None, fixed=None):
        self.masses = np.asarray(masses, dtype=float)
        n = len(self.masses)
        self.n = n
        self.G = float(G)
        self.radii = np.zeros(n) if radii is None else np.asarray(radii, dtype=float)
        self.fixed = np.zeros(n, bool) if fixed is None else np.asarray(fixed, bool)
        self.any_fixed = bool(self.fixed.any())

        s = np.maximum(self.radii[:, None], self.radii[None, :])
        np.fill_diagonal(s, 0.0)
        self._soft = bool((s > 0).any())
        self._s2 = s * s
        with np.errstate(divide="ignore"):
            self._inv_s3 = np.where(s > 0, 1.0 / s**3, 0.0)
        self._gm = self.G * self.masses
        self._eye = np.eye(n)
        self._gm_off = np.tile(self._gm, (n, 1))  # G m_j in column j, zero on the diagonal (no self-force)
        np.fill_diagonal(self._gm_off, 0.0)
        self._s2_max = float(self._s2.max()) if n else 0.0
        self._iu, self._ju = np.triu_indices(n, 1)
        self._pair_gmm = self.G * self.masses[self._iu] * self.masses[self._ju]
        self._pair_s = s[self._iu, self._ju]

    # --- accelerations -------------------------------------------------------
    def _inv_r3(self, r2):
        n = self.n
        diag = np.arange(n)
        r2[..., diag, diag] = 1.0
        inv_r3 = r2**-1.5
        if self._soft:
            inv_r3 = np.where(r2 < self._s2, self._inv_s3, inv_r3)
        inv_r3[..., diag, diag] = 0.0
        return inv_r3

    def acceleration(self, pos) -> np.ndarray:
        """Accelerations (N, 2) for positions (N, 2). Fixed bodies get zero.

        Hot path of every integrator: written with as few numpy calls as possible (N is small, call overhead
        dominates), and the homogeneous-sphere branch is skipped unless some pair can overlap.
        """
        x, y = pos[:, 0], pos[:, 1]
        dx = x[None, :] - x[:, None]  # dx[i, j] = x_j - x_i
        dy = y[None, :] - y[:, None]
        r2 = dx * dx + dy * dy + self._eye  # 1 on the diagonal: no division by zero (its weight is 0)
        inv = r2**-1.5
        if self._soft and r2.min() < self._s2_max:
            inv = np.where(r2 < self._s2, self._inv_s3, inv)
        w = inv * self._gm_off
        acc = np.empty_like(pos)
        acc[:, 0] = (w * dx).sum(axis=1)
        acc[:, 1] = (w * dy).sum(axis=1)
        if self.any_fixed:
            acc[self.fixed] = 0.0
        return acc

    def acceleration_batch(self, pos) -> np.ndarray:
        """Accelerations (T, N, 2) for positions (T, N, 2)."""
        pos = np.asarray(pos, dtype=float)
        out = np.empty_like(pos)
        chunk = max(1, _BATCH_ELEMENTS // max(1, self.n * self.n))
        for k in range(0, len(pos), chunk):
            p = pos[k:k + chunk]
            d = p[:, None, :, :] - p[:, :, None, :]
            r2 = np.einsum("tijk,tijk->tij", d, d)
            w = self._inv_r3(r2) * self._gm[None, None, :]
            out[k:k + chunk] = np.einsum("tij,tijk->tik", w, d)
        if self.any_fixed:
            out[:, self.fixed] = 0.0
        return out

    # --- potential energy ----------------------------------------------------
    def potential_energy(self, pos) -> np.ndarray | float:
        """Total potential energy for positions (N, 2) or (T, N, 2)."""
        pos = np.asarray(pos, dtype=float)
        if self.n < 2:
            return np.zeros(pos.shape[:-2]) if pos.ndim == 3 else 0.0
        d = pos[..., self._ju, :] - pos[..., self._iu, :]
        r = np.sqrt(np.einsum("...k,...k->...", d, d))
        s = self._pair_s
        with np.errstate(divide="ignore", invalid="ignore"):
            outer = -self._pair_gmm / r
            inner = -self._pair_gmm * (3.0 * s * s - r * r) / (2.0 * s**3)
        u = np.where(r >= s, outer, inner)
        u = np.where(self._pair_gmm == 0.0, 0.0, u)  # test particles: no pair energy
        return u.sum(axis=-1)

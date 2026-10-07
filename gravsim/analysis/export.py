"""Tabular export of a trajectory and its analysis (CSV)."""

from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path

import numpy as np

from ..core.trajectory import Trajectory
from . import diagnostics, frames

_UNITS = "positions en UA, vitesses en UA/an, énergies en Msun UA^2/an^2, temps en an"


def _slug(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_") or "corps"


def analysis_table(traj: Trajectory, frame="inertial", step: int = 1) -> tuple[list[str], np.ndarray]:
    """Columns: t; x, y, vx, vy of every body in ``frame``; energies; barycentre; distances; relative drifts.

    Drifts are NaN where they are not meaningful (e.g. momentum with a fixed body).
    """
    if step > 1:
        traj = traj.window(0, len(traj), step=step)
    fv = frames.view(traj, frame)
    cols: dict[str, np.ndarray] = {"t": traj.t}
    slugs = [_slug(n) for n in traj.names]
    for k, s in enumerate(slugs):
        cols[f"x_{s}"], cols[f"y_{s}"] = fv.pos[:, k, 0], fv.pos[:, k, 1]
        cols[f"vx_{s}"], cols[f"vy_{s}"] = fv.vel[:, k, 0], fv.vel[:, k, 1]
    kin, pot = diagnostics.kinetic_energy(traj), diagnostics.potential_energy(traj)
    cols["E_cinetique"], cols["E_potentielle"], cols["E_totale"] = kin, pot, kin + pot
    if traj.masses.sum() > 0:
        r_cm, v_cm = diagnostics.barycenter(traj)
        cols["x_barycentre"], cols["y_barycentre"] = r_cm[:, 0], r_cm[:, 1]
        cols["vx_barycentre"], cols["vy_barycentre"] = v_cm[:, 0], v_cm[:, 1]
    for (i, a), (j, b) in combinations(list(enumerate(slugs)), 2):
        cols[f"d_{a}_{b}"] = np.hypot(*(traj.pos[:, j] - traj.pos[:, i]).T)
    fid = diagnostics.fidelity(traj)
    nan = np.full(len(traj), np.nan)
    cols["derive_energie"] = fid.energy if fid.energy is not None else nan
    cols["derive_moment_cinetique"] = fid.angular_momentum if fid.angular_momentum is not None else nan
    cols["derive_quantite_mouvement"] = fid.momentum if fid.momentum is not None else nan
    return list(cols), np.column_stack(list(cols.values()))


def events_table(traj: Trajectory) -> list[list]:
    """One row per event: time, type, bodies, description."""
    names = traj.names
    rows = []
    for ev in traj.events:
        if ev.kind == "impulse":
            rows.append([ev.t, "poussee", names[ev.body],
                         f"dv=({ev.dv[0]:.9g};{ev.dv[1]:.9g}) UA/an" + ("" if ev.applied else " ignoree (corps fixe)")])
        elif ev.kind == "collision":
            rows.append([ev.t, "collision", f"{names[ev.i]};{names[ev.j]}",
                         f"vitesse_relative={ev.relative_speed:.9g} UA/an; angle_impact={ev.impact_angle_deg:.4g} deg"])
        elif ev.kind == "separation":
            rows.append([ev.t, "separation", f"{names[ev.i]};{names[ev.j]}", ""])
    return rows


def export_csv(traj: Trajectory, path, frame="inertial", step: int = 1) -> tuple[Path, Path | None]:
    """Write the analysis table to ``path`` and the events (if any) next to it as ``<name>_evenements.csv``."""
    path = Path(path)
    header, data = analysis_table(traj, frame, step)
    label = frame if isinstance(frame, str) else ":".join(str(x) for x in frame)
    np.savetxt(path, data, delimiter=",", header=f"{_UNITS}; referentiel={label}\n" + ",".join(header),
               comments="# ", fmt="%.12g")
    events = events_table(traj)
    if not events:
        return path, None
    ev_path = path.with_name(path.stem + "_evenements.csv")
    with open(ev_path, "w", encoding="utf-8") as fh:
        fh.write("t_an,type,corps,details\n")
        for t, kind, who, text in events:
            fh.write(f"{t:.12g},{kind},{who},{text}\n")
    return path, ev_path

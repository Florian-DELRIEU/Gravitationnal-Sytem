"""Scenario setup, JSON round trip and presets."""

import numpy as np
import pytest

from gravsim.core import units
from gravsim.core.body import Body
from gravsim.core.events import Impulse
from gravsim.core.scenario import Scenario, list_presets, load_preset
from gravsim.core.simulation import Simulation
from gravsim.core.trajectory import Trajectory


def test_polar_and_cartesian_velocity_agree():
    b = Body("x", 1.0)
    b.set_velocity_polar(2.0, 90.0)
    assert b.velocity == pytest.approx([0.0, 2.0], abs=1e-15)
    assert b.speed == pytest.approx(2.0) and b.direction_deg == pytest.approx(90.0)


def test_vectors_are_always_arrays():
    b = Body("x", 1.0, position=[1, 2])
    b.velocity = [3, 4]  # as the interface and the JSON loader do
    b.position = (5, 6)
    assert isinstance(b.velocity, np.ndarray) and isinstance(b.position, np.ndarray)
    assert (b.position - b.velocity).tolist() == [2.0, 2.0]
    with pytest.raises(ValueError):
        b.position = [1, 2, 3]
    sc = Scenario.from_dict({"bodies": [{"name": "A", "mass": 1.0, "position": [0.5, 0], "velocity": [0, 1]}]})
    assert isinstance(sc.bodies[0].position, np.ndarray) and isinstance(sc.bodies[0].velocity, np.ndarray)


def test_json_round_trip(tmp_path):
    sc = Scenario(name="test")
    sc.add(Body("star", 1.0, radius=0.005, color="#ff0"))
    sc.add(Body("p", 1e-3, [1.0, 0.0], radius=1e-4))
    sc.set_orbital_velocity("p")
    sc.impulses.append(Impulse("p", 0.1, 1.0, direction="radial", reference="star"))
    path = tmp_path / "s.json"
    sc.save(path)
    back = Scenario.load(path)
    assert back.names == sc.names
    assert np.allclose(back.velocities, sc.velocities, rtol=0, atol=0)
    assert back.impulses == sc.impulses
    assert back.bodies[0].color == "#ff0"


def test_spec_with_units_density_and_polar_velocity():
    sc = Scenario.from_dict({
        "bodies": [
            {"name": "A", "mass": {"value": 1, "unit": "Mjup"}, "density": 1.33},
            {"name": "B", "mass": 0.0, "position": [{"value": 1000, "unit": "km"}, 0],
             "velocity": {"speed": 3.0, "direction_deg": 180}},
        ]
    })
    assert sc.bodies[0].mass == pytest.approx(units.M_JUP)
    assert sc.bodies[0].radius == pytest.approx(units.R_JUP, rel=0.03)
    assert sc.bodies[1].position[0] == pytest.approx(1e6 / units.AU_M)
    assert sc.bodies[1].velocity == pytest.approx([-3.0, 0.0], abs=1e-15)


@pytest.mark.parametrize("name", list_presets())
def test_presets_load_and_run(name):
    sc = load_preset(name)
    assert len(sc.bodies) >= 2
    if not sc.fixed.any():
        _, v_cm = sc.barycenter()
        assert np.hypot(*v_cm) < 1e-12
    sim = Simulation(sc, "dop853")
    sim.run(20 * sim.recommended_dt)
    assert not sim.trajectory.collisions


def test_preset_periods():
    sc = load_preset("soleil_jupiter")
    rel = sc.bodies[1].position - sc.bodies[0].position
    assert np.hypot(*rel) == pytest.approx(5.2)
    sc = load_preset("terre_lune")
    sim = Simulation(sc, "dop853", output_dt=0.1 * units.DAY_YR)
    sim.run(27.3 * units.DAY_YR)
    rel = sim.trajectory.pos[:, 1] - sim.trajectory.pos[:, 0]
    angle = np.unwrap(np.arctan2(rel[:, 1], rel[:, 0]))
    assert angle[-1] - angle[0] == pytest.approx(2 * np.pi, rel=0.01)  # sidereal month


def test_trajectory_npz_round_trip(tmp_path):
    sc = load_preset("soleil_fixe_comete")
    sc.impulses.append(Impulse("Terre", 0.1, 0.05))
    sim = Simulation(sc, "yoshida4")
    sim.run(0.2)
    path = tmp_path / "t.npz"
    sim.trajectory.save_npz(path)
    back = Trajectory.load_npz(path)
    assert back.names == sim.trajectory.names
    assert np.array_equal(back.pos, sim.trajectory.pos)
    assert back.impulses[0].dv == pytest.approx(sim.trajectory.impulses[0].dv)

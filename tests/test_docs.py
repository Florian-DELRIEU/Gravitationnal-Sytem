"""The examples printed in the documentation actually work."""

import json
import re
from pathlib import Path

from gravsim.core.scenario import Scenario
from gravsim.core.simulation import Simulation

DOCS = Path(__file__).resolve().parent.parent / "docs"


def code_blocks(path: Path, language: str) -> list[str]:
    return re.findall(rf"```{language}\n(.*?)```", path.read_text(encoding="utf-8"), flags=re.S)


def test_scenario_format_example_loads_and_runs():
    blocks = code_blocks(DOCS / "FORMAT_SCENARIO.md", "json")
    full = json.loads(blocks[-1])  # "Exemple complet"
    sc = Scenario.from_dict(full)
    assert sc.names == ["Étoile", "b", "c"] and len(sc.impulses) == 1
    assert sc.bodies[1].radius > 0  # radius from the density
    sim = Simulation(sc, "dop853")
    sim.run(6.0)
    assert len(sim.trajectory.impulses) == 1 and not sim.trajectory.collisions
    body = json.loads(blocks[1])  # the single-body example
    assert Scenario.from_dict({"bodies": [{"name": "Soleil", "mass": 1.0}, body]}).body("Jupiter").speed > 0


def test_user_guide_python_example_runs(capsys):
    blocks = code_blocks(DOCS / "GUIDE_UTILISATEUR.md", "python")
    assert len(blocks) == 1
    exec(compile(blocks[0], "GUIDE_UTILISATEUR.md", "exec"), {})
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "3 planètes détectées"


def test_every_preset_is_listed_in_the_guide():
    from gravsim.core.scenario import list_presets, load_preset

    guide = (DOCS / "GUIDE_UTILISATEUR.md").read_text(encoding="utf-8")
    for stem in list_presets():
        name = load_preset(stem).name.split(" (")[0]
        assert name in guide, f"preset « {name} » absent du guide"

"""Bounded actual-run diagnosis; stop at the first leak, without hashing logs."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw

package = ROOT/"packages/campaign/mainline_models/level_main_00-10.m7.json"
commands = ROOT/"scenarios/campaign/00_10_full_model.json"
sim = Engine.create(Compiler().compile(package), seed=953816614)
for item in json.loads(commands.read_bytes()):
    action = dict(item)
    sim.submit(action, at=action.pop("at"))
start = time.perf_counter()
while sim.session.time < 4500 and not sim.ctx.state()["finished"] and not sim.ctx.state()["leaks"]:
    sim.session.advance(30)
    if sim.session.time % 300 == 0:
        print(json.dumps({"tick": sim.session.time, "kills": sim.ctx.state()["kills"],
            "elapsed": round(time.perf_counter()-start, 2)}), flush=True)
leaks = [thaw(e) for e in sim.session.events if e["type"] == "entity.exited"]
report = {"schema": "ark-sim/leak-diagnostic/v1", "runtime_fingerprint": sim.runtime_fingerprint,
    "program_fingerprint": sim.program.fingerprint, "time": sim.session.time, "state": sim.ctx.state(),
    "leaks": [{"event": e, "entity": thaw(sim.ctx.entity(e["payload"]["target"]))} for e in leaks],
    "actors": [thaw(e) for e in sim.session.world.entities() if "player" in e["tags"]],
    "commands_observed": [thaw(e) for e in sim.session.events if e["type"].startswith("command.")]}
output = ROOT/"validation/campaign/m7_first_leak_20261002.json"
output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
print(json.dumps({"state": report["state"], "leaks": [(x["entity"]["definition_id"], x["event"]["time"]) for x in report["leaks"]]}), flush=True)

"""Use actual movement.speed contract base_speed, preserve wrong-input zero-speed run."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];p=ROOT/'tools/chapter06_environment_consumer/probe_route_v6.py';s=p.read_text().replace('chapter06_environment_v6','chapter06_environment_v7').replace("inputs.attributes.move_speed * 0.5 if 'move_speed' in inputs.attributes else 0","inputs.movement_parameters.base_speed * 0.5");out=p.with_name('probe_route_v7.py');assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)

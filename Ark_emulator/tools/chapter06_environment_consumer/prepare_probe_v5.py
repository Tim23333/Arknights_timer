"""New independent fixture allows system entities' absent movement stat, same source mover1.1."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent;p=ROOT/'tools/chapter06_environment_consumer/probe_route_v4.py';s=p.read_text().replace('chapter06_environment_v4','chapter06_environment_v5').replace("'inputs.attributes.move_speed * 0.5'", "\"inputs.attributes.get('move_speed',0) * 0.5\"");out=p.with_name('probe_route_v5.py');assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)

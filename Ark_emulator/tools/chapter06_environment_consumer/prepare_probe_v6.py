"""Legal declarative membership conditional; preserve previous get-method compile reject."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];p=ROOT/'tools/chapter06_environment_consumer/probe_route_v5.py';s=p.read_text().replace('chapter06_environment_v5','chapter06_environment_v6').replace("inputs.attributes.get('move_speed',0) * 0.5","inputs.attributes.move_speed * 0.5 if 'move_speed' in inputs.attributes else 0");out=p.with_name('probe_route_v6.py');assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)

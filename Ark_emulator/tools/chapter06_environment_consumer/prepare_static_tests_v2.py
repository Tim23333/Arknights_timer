"""Explicit known one-ULP outward border profile; no broad tolerance or core change."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];p=ROOT/'tools/chapter06_environment_consumer/test_declared_static_tile_v1.py';s=p.read_text().replace('import json,sys','import json,sys,math').replace("stopped['col']==1.5","stopped['col']==math.nextafter(1.5,-math.inf)");out=p.with_name('test_declared_static_tile_v2.py');assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)

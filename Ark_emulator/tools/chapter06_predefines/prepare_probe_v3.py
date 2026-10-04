"""Preserve rejected fixture height2; legal highland1 with exact preservation assertion."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];p=ROOT/'tools/chapter06_predefines/test_frost_consumer_v2.py';s=p.read_text().replace('chapter06_predefined_consumer_v2','chapter06_predefined_consumer_v3').replace("'heightType':2","'heightType':1").replace("tile['heightType']==2","tile['heightType']==1");out=p.with_name('test_frost_consumer_v3.py');assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)

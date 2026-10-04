"""Avoid same-actor two-blocking-casts-at0 fixture; initial real resistance Buff for reversal case."""
from pathlib import Path
HERE=Path(__file__).parent
s=(HERE/'review_dynamic_burn_v1.py').read_text().replace('dynamic_burn_independent_v1','dynamic_burn_independent_v2')
s=s.replace('expected_remove,expected_hits):','expected_remove,expected_hits,initial_half=False):')
s=s.replace("p,timer,child,aid=package(multiplier);reg=registry();", "p,timer,child,aid=package(multiplier);\n if initial_half:p['entities'][1]['components']['buffs']={'initial':['buff/peer/dynamic/resistance']}\n reg=registry();")
s=s.replace("[('fire',0),('add',0),('remove',150)],151,780,[765],[(30*n,50+6*n) for n in range(1,26)]", "[('fire',0),('remove',150)],151,780,[765],[(30*n,50+6*n) for n in range(1,26)],initial_half=True")
(HERE/'review_dynamic_burn_v2.py').write_text(s,encoding='utf-8',newline='')

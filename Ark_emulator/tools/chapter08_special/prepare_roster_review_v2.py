from pathlib import Path
HERE=Path(__file__).parent
s=(HERE/'review_roster_burn_v1.py').read_text().replace('dynamic_roster_independent_v1','dynamic_roster_independent_v2')
s=s.replace("'objectives':{},'roster':selected", "'objectives':{},'resources':{'dp':{'initial':10,'capacity':99}},'roster':selected")
(HERE/'review_roster_burn_v2.py').write_text(s,encoding='utf-8',newline='')

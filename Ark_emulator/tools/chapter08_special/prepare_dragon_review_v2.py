from pathlib import Path
HERE=Path(__file__).parent
s=(HERE/'review_dragon_fire_v1.py').read_text().replace('dragon_fire_independent_v1','dragon_fire_independent_v2')
s=s.replace("rows['old_gap']['hits'][-3:]==[(930,230),(960,230),(990,230)]","[x for x in rows['old_gap']['hits'] if x[0]>=930]==[(930,230),(960,230),(990,230),(1020,230)]")
(HERE/'review_dragon_fire_v2.py').write_text(s,encoding='utf-8',newline='')

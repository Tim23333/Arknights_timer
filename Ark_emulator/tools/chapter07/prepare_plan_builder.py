"""New chapter7 offline inventory builder from source-preserving chapter6 reader."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'tools/chapter06/build_source_plan.py';s=p.read_text();s=s.replace('chapter6','chapter7').replace('chapter06','chapter07').replace('main_06-14','main_07-15').replace('main_06-15','main_07-16').replace("('06-14','06-15')","('07-15','07-16')")
start=s.index("            'required_new_consumers':[");end=s.index("            'runtime_created'",start)
s=s[:start]+"""            'selected_display_ids':{r['native_id']:r['code'] for r in selected},
            'required_new_consumers':['Exact chapter7 source actor modes, passives, skills and selected references; no name-derived mechanics','All native predefines/cards, branch/control actions and terrain retained; consumers remain pending','Reference tables are fixed56aee, local assets carry their own distinct version/source hashes'],
"""+s[end:]
out=ROOT/'tools/chapter07/build_source_plan.py';assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True);out.write_text(s,encoding='utf8',newline='');print(out)

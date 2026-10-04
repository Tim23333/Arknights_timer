"""Check public operator and Mon3tr positions against all native trap cells."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter05_public_v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for row in json.loads((OUT/'prepared_commands.json').read_bytes())['cases']:
 p=Path(row['parent']);c=Path(row['commands']);assert sha(p)==row['parent_sha'] and sha(c)==row['commands_sha'];scene=json.loads(p.read_bytes())['scenarioDraft'];commands=json.loads(c.read_bytes())
 cells={(e['position']['row'],e['position']['col']) for e in scene['initialEntities']};inputs={(e['row'],e['col']) for e in commands if e['action']=='deploy'};inputs.update((e['payload']['position']['row'],e['payload']['position']['col']) for e in commands if e.get('ability')=='ability/kalts_summon');assert not cells&inputs
 rows.append({'stage':row['native_id'],'parent_sha':sha(p),'commands_sha':sha(c),'native_predefined_cells':sorted(cells),'operator_and_token_cells':sorted(inputs),'overlap':[],'all_native_instances_checked_including_dormant':True})
dest=OUT/'native_predefined_cell_check.json';assert not dest.exists();dest.write_text(json.dumps({'cases':rows,'actual_runtime_admission_separate':True},indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'cases':rows}))

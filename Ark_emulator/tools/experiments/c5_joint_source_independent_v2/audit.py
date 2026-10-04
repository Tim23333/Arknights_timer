import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
RESULT=[]
for stage,births,variants,rows,cols,dp,devices in [('05-09',51,4,8,11,10,4),('05-10',73,6,8,12,0,10)]:
 base=ROOT/'packages/campaign/chapter05_stage_models/combined_v3'
 npath=base/('level_main_'+stage+'.native_life.json');opath=base/('level_main_'+stage+'.life99999.json')
 n=read(npath);o=read(opath);s=n['scenarioDraft'];actions=[a for w in s['timeline']['waves'] for f in w['fragments'] for a in f['actions']]
 assert sum(a['count'] for a in actions if a['kind']=='spawn')==births
 assert len({a['spawn']['definition'] for a in actions if a['kind']=='spawn'})==variants
 assert (s['map']['rows'],s['map']['cols'],s['resources']['dp']['initial'],len(s['initialEntities']))==(rows,cols,dp,devices)
 for k in ['map','timeline','parameters','objectives','initialEntities','branches','roster','rules']:assert n['scenarioDraft'].get(k)==o['scenarioDraft'].get(k)
 assert n['definitions']==o['definitions']
 assert n['scenarioDraft']['resources']['dp']==o['scenarioDraft']['resources']['dp']
 assert s['resources']['life']=={'initial':3,'capacity':3} and o['scenarioDraft']['resources']['life']=={'initial':99999,'capacity':99999}
 RESULT.append({'stage':stage,'native_sha':sha(npath),'overlay_sha':sha(opath),'births':births,'variants':variants,'rows':rows,'cols':cols,'DP':dp,'devices':devices,'passed':True})
out=ROOT/'validation/campaign/c5_joint_source_independent_v2/stage_verified.json'
with out.open('x',encoding='utf8') as f:json.dump({'results':RESULT,'helper_sha':sha(Path(__file__))},f,ensure_ascii=False,indent=2)
print(json.dumps({'report':str(out),'sha':sha(out),'results':RESULT}))

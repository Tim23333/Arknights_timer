"""Native51/4/8/10 and73/6/9/0 public fixed12 plans, no numeric grants."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';OUT=ROOT/'validation/campaign/chapter05_public_v3';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.build_campaign_runthrough_input import apply
PIN='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==PIN;OUT.mkdir(parents=True,exist_ok=True);rows=[]
 for code,births,variants,slots,dp in [('05-09',51,4,8,10),('05-10',73,6,9,0)]:
  name='level_main_'+code;parent=ROOT/'packages/campaign/chapter05_stage_models/combined_v3'/(name+'.native_life.json');overlay=parent.with_name(name+'.life99999.json');native=json.loads(parent.read_bytes());p=json.loads(overlay.read_bytes());assert p==apply(native,sha(parent));scene=p['scenarioDraft'];assert scene['resources']['dp']['initial']==dp and scene['parameters']['deploy_capacity']==slots and native['scenarioDraft']['resources']['life']=={'initial':3,'capacity':3};assert len(scene['roster'])==12;defs={d['id']:d for d in p['definitions']};Compiler().compile(p)
  ground=(6,1) if code=='05-09' else (6,8);high=[(5,8),(2,2),(5,8),(4,3),(2,2),(5,8)] if code=='05-09' else [(5,2),(5,3),(5,4),(3,4),(3,5),(3,3)];hi=iter(high);base=0 if dp==10 else 300;commands=[];operators=[];aliases={}
  for index,uid in enumerate(scene['roster']):
   d=defs[uid];at=base+390*index;alias='c5_'+code.replace('-','_')+'_'+uid.rsplit('_',1)[-1];isground=d['components']['deployable']['terrain']=='ground';row,col=ground if isground else next(hi);tile=scene['map']['tiles'][row*scene['map']['cols']+col];assert tile['buildableType']&(1 if isground else 2);skill=None
   for aid in d['components']['abilities']:
    a=defs[aid];params={**a.get('parameters',{}),**a.get('activation',{}).get('parameters',{})}
    if a['activation']['mode']=='manual' and not params.get('auto_only',False) and 'summon' not in aid and 'cannon' not in aid:skill=aid;break
   commands.append({'at':at,'action':'deploy','entity':uid,'row':row,'col':col,'facing':'right','alias':alias});aliases[alias]=uid;delay=450 if 'plosis' in uid else 750 if 'amgoat' in uid else 481 if 'kalts' in uid else 600 if 'lisa' in uid else 390 if 'weedy' in uid else 150 if 'cgbird' in uid else 300
   if 'kalts' in uid:
    mon=(6,2) if code=='05-09' else (5,7);t=scene['map']['tiles'][mon[0]*scene['map']['cols']+mon[1]];assert t['buildableType']&1;commands.append({'at':at+30,'action':'skill','source':alias,'ability':'ability/kalts_summon','payload':{'position':{'row':mon[0],'col':mon[1]},'facing':'right'}})
   if skill:commands.append({'at':at+delay,'action':'skill','source':alias,'ability':skill})
   commands.append({'at':at+delay+60 if any(x in uid for x in ('plosis','amgoat','kalts','lisa','weedy')) else at+360,'action':'withdraw','source':alias});operators.append({'unit':uid,'alias':alias,'cell':{'row':row,'col':col},'native_base_tile':tile,'actual_base_cost':d['components']['attributes']['base']['deploy_cost'],'deploy_at':at,'manual_skill':skill})
  commands.sort(key=lambda c:c['at']);folder=ROOT/'scenarios/campaign/chapter05'/name/'combined_v3';folder.mkdir(parents=True,exist_ok=True);cmdpath=folder/'public_fixed12.compact_v1.commands.json';planpath=folder/'public_fixed12.compact_v1.plan.json'
  if cmdpath.exists() or planpath.exists():raise ValueError('Preserve C5 commands')
  cmdpath.write_text(json.dumps(commands,indent=2)+'\n',encoding='utf8',newline='');plan={'role':'Prepared baseline-grid public input; actual admission depends on true HP/DP/SP/control/death/source overlays','core':PIN,'source_parent':str(parent),'source_parent_sha':sha(parent),'overlay':str(overlay),'overlay_sha':sha(overlay),'commands_sha':sha(cmdpath),'native_births':births,'variants':variants,'native_slots':slots,'native_DP':dp,'native_seed':scene['seed'],'first12_window':[base,base+4290],'operators':operators,'policy':'No global numeric grants; native5-10DP0 requires wait300ticks for first cost10 Myrtle. Automatic-only skills have no manual calls. Ballistas actual active/dormant profiles remain untouched.','whole_stage_executed':False};planpath.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf8',newline='');rows.append({'native_id':name,'parent':str(parent),'parent_sha':sha(parent),'overlay':str(overlay),'overlay_sha':sha(overlay),'commands':str(cmdpath),'commands_sha':sha(cmdpath),'plan_sha':sha(planpath),'native_DP':dp,'native_slots':slots,'births':births,'variants':variants,'first12_last_deploy':base+4290})
 dest=OUT/'prepared_commands.json'
 if dest.exists():raise ValueError('Preserve receipt')
 dest.write_text(json.dumps({'core':PIN,'cases':rows,'prepared_only':True,'registry_modified':False},indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'cases':rows}))
if __name__=='__main__':main()

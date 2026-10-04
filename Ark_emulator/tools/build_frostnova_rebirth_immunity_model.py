"""Source operands combining true FrostNova rebirth with typed control immunity."""
import json,hashlib,argparse
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'packages/campaign/chapter04_boss/m86/rebirth_immunity.reference_model.json'
PINS={'packages/campaign/chapter04_boss/m61/rebirth.reference_model.json':'11f14fa086dc2906bb5318003a9b24880a62d570f4f87aff7a42e0fb40fa0a4b','packages/campaign/chapter04_boss/m70/immunity.reference_model.json':'8e0731886294b1ff0d781d397d935b2bf6229740b673e55466ae46e53e11fc34','packages/campaign/skills.chen.json':'04df7b6f7f40f43687c03b0186e02f4e0407ee566231f43b2455d2741719dde6'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 for name,pin in PINS.items():
  if sha(ROOT/name)!=pin:raise ValueError('Frozen source changed '+name)
 p=deepcopy(json.loads((ROOT/next(iter(PINS))).read_bytes()));immunity=json.loads((ROOT/'packages/campaign/chapter04_boss/m70/immunity.reference_model.json').read_bytes());chen=json.loads((ROOT/'packages/campaign/skills.chen.json').read_bytes());unit=p['entities'][0]
 unit['components']['selection_state']=deepcopy(immunity['entities'][0]['components']['selection_state']);unit['components']['buffs']=deepcopy(immunity['entities'][0]['components']['buffs']);unit['metadata']['scope']='Exact FrostNova health/rebirth/ATK and intrinsic control immunity plus initial sleep-immunity removal; normal/skills/blackice remain separate.'
 assert unit['components']['selection_state']['abnormal_immunes']==[0,12,16,25] and unit['components']['rebirth']['retain_buffs']==[] and unit['components']['rebirth']['delay_seconds']==5
 p['buffs'].extend(deepcopy(immunity['buffs']));p['rules'].extend(deepcopy(immunity['rules']))
 next(b for b in p['buffs'] if b['id']=='buff/campaign_chen_stun')['id']='buff/m86/chen_source_stun'
 selected=deepcopy(chen['abilities'][0]);assert selected['metadata']['native_skill_id']=='skchr_chen_1';selected['id']='ability/m86/chen_source_s1';selected['selector']='selector/m86/chen_source_target';selected['metadata']['verification_scope']='Native selected effect/SP/clock operands; caller stats and attack interval supplied by explicit synthetic casting fixture. Not whole canonical Chen.'
 selected['timeline'][0]['effect']['on_success'][0]['buff']='buff/m86/chen_source_stun'
 p['abilities']=[selected];p['selectors']=[{'id':'selector/m86/chen_source_target','kind':'selector','region':{'type':'grid_offsets','offsets':[[0,0],[0,1]],'rotate_with_facing':False},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1}]
 metadata=p['manifest']['metadata'];metadata.update({'builder_sha256':sha(Path(__file__)),'source_locks':PINS,'scope':'M86 source-backed Frost rebirth+immunity and selected Chen S1 effects. No synthetic actor definitions stored in module.','selected_skill_source':{'path':'packages/campaign/skills.chen.json','sha256':PINS['packages/campaign/skills.chen.json'],'original_ability_id':'ability/campaign_chen_s1','source_stun_flag':0,'source_stun_duration_seconds':1.5},'initial_sleep_immunity':'Actual initial frstar_c Buff; removed by true first-health0 rebirth clear with retain_buffs[], never manually phase-switched','model_gaps':[x for x in metadata['model_gaps'] if 'M70' not in x],'client_verified':False,'formal_approved':False,'whole_stage_executed':False});p['manifest']['id']='package/ch4/frstar/rebirth_immunity/reference';return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8');OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:
  if OUT.read_bytes()!=raw:raise ValueError('Rebirth immunity module stale')
 else:OUT.write_bytes(raw)
 print(json.dumps({'path':str(OUT),'sha256':sha(OUT),'source_hp':25000,'source_reborn_seconds':5,'source_reborn_atk':630,'client_verified':False}))

"""Explicit source-backed decision profile; native method bodies remain pending."""
from pathlib import Path
from copy import deepcopy
import json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT.parent/'unpack_work/campaign_m24_enemy_fsm_candidate'
SOURCE=ROOT/'packages/campaign/chapter01_behavior/source.reference.json'
PIN='d5b4c497b6fd7c78b8ba594628549df8b571d947cfba0d70d23d05dcbe7f3ca7'
STAGES={'01-11':'2fd475a0491c86b0ab8d48ff1a17b983e5156d23bc5ea20a77782c8484e77e33','01-12':'9aa6f6b6aceb2eb1f2ced0013025765742f305d2b31dbf045e6c13201424154d'}
OUT=ROOT/'packages/campaign/chapter01_behavior/m24'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core():
 files={str(p.relative_to(RUNTIME/'ark_sim')):sha(p) for p in sorted((RUNTIME/'ark_sim').rglob('*.py'))}
 return hashlib.sha256(json.dumps(files,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def profile(mode,selector,groups,blocked=False):
 return {'mode':mode,'selectors':[{'key':'normal','selector':selector}],
  'cast_groups':[{'key':key,'abilities':ids} for key,ids in groups.items()],
  'parameters':{'target_key':'normal','stop_on_target':True,'blocked_target':blocked,'stop_cast_groups':list(groups)}}
def build(stage):
 assert sha(SOURCE)==PIN;n=json.loads(SOURCE.read_bytes())
 for p,pin in n['source_locks'].items():assert sha(Path(p))==pin
 parent=ROOT/f'packages/campaign/chapter01_stage_models/m21/level_main_{stage}.partial.json';assert sha(parent)==STAGES[stage]
 p=json.loads(parent.read_bytes());units={x['id']:x for x in p['entities']};new=[];proof=[]
 for uid in ('unit/chapter01_w','unit/enemy_1028_mocock','unit/enemy_1028_mocock_2','unit/enemy_1014_rogue'):
  if uid not in units:continue
  u=units[uid];owned=list(u['components']['abilities']);bid='behavior/m24/'+uid.split('/')[-1]
  if uid=='unit/chapter01_w':
   assert len(n['enemies']['enemy_1504_cqbw']['mode_links'])==2
   groups={'normal':['ability/chapter01_w_normal_0','ability/chapter01_w_normal_1'],
       'skill':['ability/chapter01_w_c4_0','ability/chapter01_w_c4_1']}
   cfg={'rule':'rule/ark_behavior_decision','mode_resource':'mode','profiles':[profile(i,f'selector/chapter01_w_normal_{i}',groups) for i in (0,1)]}
  else:
   key=uid.split('/')[-1];links=n['enemies'][key]['mode_links'];assert len(links)==1
   blocked=links[0]['resolved_classes']['_attackTrigger'] is None
   if blocked:assert links[0]['resolved_classes']['_combat']=='MultiMeleeAttack'
   cfg={'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[profile(0,f'selector/{key}/ch1_model',{'normal':owned},blocked)]}
  new.append({'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':cfg,
    'metadata':{'native_body_verified':False,'model_profile':'explicit selector/cast/blocked/visibility/control decision; native transition order pending'}})
  u['components']['behavior']={'machine':bid};proof.append({'unit':uid,'owned_abilities':owned,'decision':cfg})
 p['behaviors']+=new;m=p['manifest']['metadata'];m['m24_decision']={'source_sha256':PIN,'builder_sha256':sha(Path(__file__)),
   'parent_sha256':sha(parent),'runtime':core(),'profiles':proof,'status':'declared_math_profile_native_permission_unverified',
   'client_pending':['Enemy FSM native branch/transition priority and target refresh method body','actual movement during cast/cooldown/target loss','body-width obstacle/separation algorithm'],
   'native_actual_correct':False,'formal_approval':False}
 # Existing enemy FSM gap is deliberately retained. This source/math candidate
 # cannot discharge the user's actual-game correctness requirement.
 assert 'native_enemy_target_free_abnormal_filters_and_move_attack_FSM' in m['pending_model_gaps']
 m['required_runtime']=core();p['manifest']['id']+='/m24_declared_decision';p['scenarioDraft']['id']+='/m24_declared_decision'
 return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
 for stage in STAGES:
  p=OUT/f'level_main_{stage}.decision.partial.json';raw=(json.dumps(build(stage),ensure_ascii=False,indent=2)+'\n').encode()
  if a.check:assert p.read_bytes()==raw
  else:p.write_bytes(raw)
 print(json.dumps({'core':core(),'status':'declared math only; native FSM gap retained'}))

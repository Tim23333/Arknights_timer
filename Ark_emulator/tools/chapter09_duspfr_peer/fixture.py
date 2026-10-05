"""Independent complete Duspfr source module peer; no author fixture imports."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_duspfr_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from tools.chapter09_duspfr_v1.build import providers,BODY,FLAME,TRAIT
CORE='2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0';assert implementation_digest()==CORE
MODULE=ROOT/'packages/campaign/chapter09_consumers/duspfr_v1/module.v1.json';FREEZE=ROOT/'validation/campaign/chapter09_duspfr_v1/freeze.v1.json';REPORT=ROOT/'validation/campaign/chapter09_duspfr_peer';LOG=Path('E:/ArkSimLogs/runs/chapter09_duspfr_peer');REG=providers();HP=33791
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE;assert sha(FREEZE)=='2e0b09cd9ed633291360caf6ba99e882f3692ebce8a3fdebfc91fc234a37965f';assert sha(MODULE)=='0784065767f8995d00c91cc91567a7b6185b1ba254e72eac3cc2e613e0ffb86f'
 frozen=json.loads(FREEZE.read_bytes());assert frozen['core_before']==frozen['core_after']==CORE
 paths=[FREEZE,MODULE,ROOT/'tools/chapter09_duspfr_v1/build.py',ROOT/'tools/chapter09_ability_clock_v1/flame_channel.py',ROOT/'tools/chapter09_pillar_lifecycle_v1/build.py',ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json',ROOT/'packages/campaign/chapter09_source_prepare/source.detail.v1.json']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts]
 return {str(p):sha(p) for p in paths}
START=guard()
def player(hp=HP,res=35,position=(5,5.6)):
 return {'id':'unit/peer/duspfr/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':hp,'atk':13791,'def':137,'mres':res,'block_count':1}},'resources':{'hp':{'role':'health','initial':hp,'capacity':hp}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/peer/kill','ability/peer/move','ability/peer/control_source'],'elemental':{'eligibility_rule':'rule/ch9/duspfr/eligible','elements':{'FIRE':{'capacity':10000,'resistance':0,'recovery_rate':0,'break_duration_seconds':7,'rules':{'elemental.capacity':'rule/ch9/duspfr/capacity','elemental.loss':'rule/ch9/duspfr/loss','elemental.recovery':'rule/ch9/duspfr/recovery','elemental.break_duration':'rule/ch9/duspfr/duration'},'on_break':[],'on_end':[]}}}}}
def scene(atk=700,hp=HP,res=35,pos=(5,5.6),death_at=None,pillar=False,other=False,source_flags=()):
 p=json.loads(MODULE.read_bytes());p['manifest']['requires']=['preset/ark_standard'];body=p['entities'][0];body['components']['attributes']['base']['atk']=atk;body['components']['selection_state']['abnormal_flags']=list(source_flags);target=player(hp,res,pos);p['entities'].append(target)
 p['selectors'].append({'id':'selector/peer/duspfr_source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1});p['abilities'] += [{'id':'ability/peer/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/duspfr_source','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]},{'id':'ability/peer/move','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':{'row':5,'col':6.7}}}]},{'id':'ability/peer/control_source','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/duspfr_source','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/peer/source_control'}}]}]
 p['buffs'].append({'id':'buff/peer/source_control','kind':'buff','duration_seconds':2,'selection_flags':{'abnormal_flags':[0]},'control':{'abilities':False,'attack':False,'move':False,'interrupt':True}})
 initial=[{'definition':BODY,'instanceAlias':'source','position':{'row':5,'col':5}},{'definition':target['id'],'instanceAlias':'player','position':{'row':pos[0],'col':pos[1]}}]
 if other:
  o=deepcopy(body);o['id']='unit/peer/duspfr/other';o['components']['attributes']['base']['atk']=500;o['components']['attributes']['base']['max_hp']=9137;o['components']['resources']['hp'].update(initial=9137,capacity=9137);o['components']['selection_state']['abnormal_flags']=[0];p['entities'].append(o);initial.append({'definition':o['id'],'instanceAlias':'other','position':{'row':4,'col':5}})
 if pillar:initial.append({'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':5,'col':4}})
 p['scenarioDraft']={'id':'scene/peer/duspfr','ruleset':'ruleset/ark_standard','map':{'rows':11,'cols':12},'initialEntities':initial,'commands':[]}
 if death_at is not None:p['scenarioDraft']['commands'].append({'at':death_at,'action':'skill','source':'player','ability':'ability/peer/kill'})
 return p

"""Native cannon receiver invincibility, existing target-side pipeline only."""
import hashlib,json
from pathlib import Path
from ark_sim.contracts import thaw
from tools.chapter10_gunctrl_v2 import build as prior
from tools.chapter10_gunctrl_v1.build import P,SOURCE
ROOT=Path(__file__).resolve().parents[2]
def receiver_invincible(inputs,params,context):
 result=thaw(inputs['effect']['settlement']);result['amount']=0
 for allocation in result.get('allocations',[]):
  if allocation.get('resource',params['health_resource'])==params['health_resource']:
   if 'amount' in allocation:allocation['amount']=0
   if 'delta' in allocation:allocation['delta']=0
 return result
def providers():
 return {**prior.providers(),'source.ch10.gunctrl.invincible':{'callable':receiver_invincible,'version':'native5-target-pipeline-zero-health-preserve-settlement-v1'}}
def build(stage='level_main_10-14',*,manfred_sp_binding=None,require_complete=False):
 p=prior.build(stage,manfred_sp_binding=manfred_sp_binding,require_complete=require_complete);rule='rule/'+P+'receiver_invincible';p['rules'].append({'id':rule,'kind':'rule','contract':'damage.pipeline','parameters':{'health_resource':'hp'},'implementation':{'type':'provider','provider':'source.ch10.gunctrl.invincible'}})
 native=json.loads(SOURCE.read_bytes());raw=next(b for c in native['prefabs']['trap_058_gunctrl']['components'].values() for b in c['raw'].get('_buffs',[]) if b['buffKey']=='gunctrl_c');assert raw['attributes']['abnormalFlags']==[5,7]
 buff=next(x for x in p['buffs'] if x['id']=='buff/'+P+'native_flags');assert buff['selection_flags']['abnormal_flags']==[5,7];buff['damage_hooks']=[{'phase':'after','rule':rule}];buff['metadata']={'native_inline':raw,'enum_consumption':{'INVINCIBLE':5,'HEAL_FREE':7}}
 p['manifest']['id']+='/native_invincible_v3';m=p['manifest']['metadata'];m['source_locks'][str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();m['receiver_invincibility_counter']='validation/campaign/chapter10_gunctrl_independent_v2/counter.invincible.actual.v2.json';m['reference_policy']['invincibility']='Actual initially owned native gunctrl_c INVINCIBLE5 declares after target damage.pipeline. Zero primary amount and HP allocations amount/delta, retain accepted/events and nonHP allocations; source output is untouched. Explicit no_source_damage damage_without_modify=True bypasses target hooks in existing core, so that mode can damage/kill this content model; no native/client claim that bypass honors flag5.'
 return p

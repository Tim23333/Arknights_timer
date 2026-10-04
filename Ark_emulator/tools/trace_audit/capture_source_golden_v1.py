"""Controlled small source actors; retain exact definitions, no oracle runtime calls."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';OUT=ROOT/'validation/trace_audit/source_golden_v1';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
CORE='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
SUPPORTED={'rule/ark_basic_power','rule/ark_healing_power','rule/ark_standard_mitigation','rule/ark_attribute_layers','rule/ark_modifier_layer','rule/ark_resource_capacity','rule/ark_resource_cost','rule/ark_resource_recovery','rule/ark_resource_bounds','rule/ark_deploy_cost','rule/ark_deploy_refund'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==CORE;OUT.mkdir(parents=True,exist_ok=True);source=ROOT/'packages/campaign/chapter05_stage_models/combined_v3/level_main_05-09.life99999.json';assert sha(source)=='c7d18db359f1fbe01bec0073f8e08761d75ae8266a1b4588ba141adc235a7b93';p=json.loads(source.read_bytes());defs={d['id']:d for d in p['definitions']};myrtle='unit/char_151_myrtle';amy='unit/char_002_amiya';amy=next(x for x in p['scenarioDraft']['roster'] if 'amgoat' in x)
 target={'id':'unit/audit_controlled_enemy','kind':'entity','tags':['enemy_fixture'],'components':{'attributes':{'base':{'max_hp':5000,'atk':0,'def':100,'mres':30,'move_speed':0,'block_count':0}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'selection_state':{'side':1,'category':1,'motion':1,'unit_type':1},'spatial':{'radius':.1},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['definitions'].append(target)
 p['scenarioDraft']={'id':'scene/source_audit_golden_v1','ruleset':'ruleset/ark_standard','seed':507006,'objectives':{},'map':{'rows':4,'cols':9,'tiles':[{'tileKey':'tile_road','buildableType':3,'passableMask':3} for _ in range(36)]},'initialEntities':[{'definition':'unit/ch5/ballista/source_level6','instanceAlias':'ballista','position':{'row':1,'col':0},'facing':'right'},{'definition':myrtle,'instanceAlias':'myrtle','position':{'row':1,'col':3},'facing':'right'},{'definition':amy,'instanceAlias':'arts_source','position':{'row':2,'col':3},'facing':'right'},{'definition':target['id'],'instanceAlias':'enemy','position':{'row':2,'col':5}}],'metadata':{'controlled_fixture':'Original numeric/source actor definitions retained; only map/position and stationary enemy test recipient authored.'}}
 inp=OUT/'input.json';journal=OUT/'events.jsonl';assert not inp.exists() and not journal.exists();inp.write_text(json.dumps(p,indent=2)+'\n',encoding='utf8',newline='');s=Engine.create(Compiler().compile(p),event_journal_path=journal);s.session.advance(400)
 rules={};kinds={};damage=[];heal=[]
 with journal.open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line);v=e['payload'];kinds[e['type']]=kinds.get(e['type'],0)+1
   if e['type']=='calculation':
    t=v['trace'];rid=t['rule_id']
    if rid in SUPPORTED:
     pin={'formula_version':'independent-source-arithmetic/v1','contract':t['calculation_id'],'rule_fingerprint':t['rule_fingerprint'],'expression':t['stages'][-1].get('expression'),'provider':t.get('provider'),'evidence':'Explicit standard source definitions + independently written arithmetic oracle; fingerprint binds reviewed rule, not an expected-output calculator.'};assert rid not in rules or rules[rid]==pin;rules[rid]=pin
   if e['type']=='damage.accepted':damage.append(e)
   if e['type']=='healing.accepted':heal.append(e)
 pins=OUT/'oracle_pins.json';pins.write_text(json.dumps({'schema':'ark-sim/source-formula-oracle-pins/v1','source_stage_sha':sha(source),'source_core':CORE,'standard_source_sha':sha(RUNTIME/'ark_sim/content/presets/ark_standard.json'),'source_formula_scope':'Source-reference arithmetic, no client approval. Unknown rule IDs/fingerprints stay pending.','rules':rules},indent=2)+'\n',encoding='utf8',newline='')
 report={'core':CORE,'source_sha':sha(source),'input_sha':sha(inp),'journal_sha':sha(journal),'events':kinds,'damage_events':damage,'healing_events':heal,'rules':list(rules),'oracle_pins_sha':sha(pins),'snapshot':s.snapshot()};dest=OUT/'capture.json';dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');assert implementation_digest()==CORE;print(json.dumps({'events':kinds,'damage':len(damage),'heal':len(heal),'rules':list(rules),'receipt_sha':sha(dest)}))
if __name__=='__main__':main()

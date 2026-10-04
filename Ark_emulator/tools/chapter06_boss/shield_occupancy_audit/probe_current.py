"""Actual fixed story Shield captures active CHAR without deployable."""
from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_buff_no_source_v1_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
 from ark_sim import Compiler,Engine
 from ark_sim.contracts import thaw
 from ark_sim.adapters.api import implementation_digest
 from tools.chapter06.cold.policies import providers
 from tools.chapter06_boss.frstar2_s.build_module import OUT,COLD,I
 from tools.campaign_streaming_evidence import export_events
 base=ROOT/'packages/campaign/chapter06_boss/shield_occupancy_audit';p=json.loads((OUT/'model.json').read_bytes());before=sha(OUT/'model.json')
 npc={'id':'unit/test/shield/active_char_no_deployable','kind':'entity','tags':['player','classification_probe'],'components':{'attributes':{'base':{'max_hp':1000000,'atk':0,'def':300,'mres':50}},'resources':{'hp':{'role':'health','initial':1000000,'capacity':1000000}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(npc)
 p['scenarioDraft']={'id':'scene/shield/current_classification','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':5,'default_tile':{'buildableType':0,'passableMask':1},'tiles':[{'buildableType':1 if (r,c)==(2,3) else 0,'passableMask':1} for r in range(5) for c in range(5)]},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':2,'col':2}},{'definition':npc['id'],'instanceAlias':'npc','position':{'row':2,'col':3}}]}
 path=base/'current.classification.probe.json';path.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());reg=providers();s=Engine.create(Compiler(providers=reg).compile(path,packages=[COLD]),providers=reg,seed=6217);s.session.advance(746)
 selected=[e for e in s.session.events if e['type']=='tile.selection'];died=[e for e in s.session.events if e['type']=='entity.died' and e['payload'].get('source')==s.session.world.resolve('npc')]
 assert selected and thaw(selected[0]['payload'])['selected']==[{'row':2,'col':3}] and not s.ctx.alive('npc') and s.ctx.resources.current('npc','hp')==0
 assert len(died)==1 and died[0]['time']==745
 assert before==sha(OUT/'model.json')
 report={'schema':'ark-sim/ch6-shield-current-occupancy-counter/v1','actual_excludes_existing_npc_char':False,'source_model_sha256':before,'core':implementation_digest(),'fixture_scope':'Minimal active actor with exact realNPCclassification side0 motion1 category1 CHAR1, no deployable; not cloned NPCstats/talents, no slots/change of frozen content','actual':{'captured_cells':thaw(selected[0]['payload'])['selected'],'selection_time':selected[0]['time'],'npc_hp':0,'npc_alive':False,'death_time':died[0]['time']},'source_policy_gap':'deployable-only exclusions differ from intended allfriendlyCHAR reference policy; rawenum2 mapping not independently proven; source investigation report separates native/reference facts','journal':export_events(base/'current.classification.events.jsonl',s),'snapshot':s.snapshot(),'runtime_modified':False,'frozen_model_unchanged':True,'whole_stage_executed':False}
 out=base/'current.classification.counter.json';out.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(out),'actual':report['actual']}))
if __name__=='__main__':main()

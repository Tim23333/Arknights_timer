"""Actual parent: immediate retirement or permanent HP0; no finite depletion lease."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PARENT=(ROOT/'../unpack_work/campaign_c9_foundation_v9_candidate').resolve();sys.path.insert(0,str(PARENT));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_pillar_v1.build_payload import build,providers
def hold_policy(inputs,params,context):return {'action':'none'}

def make(hold=False):
    p=build();p['entities'].append({'id':'unit/depletion_counter/source','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':100,'atk':6000,'def':0,'mres':0}},'resources':{'hp':{'role':'health','initial':100,'capacity':100}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    if hold:
        p['rules'].append({'id':'rule/depletion_counter/hold','kind':'calculation_rule','contract':'lifecycle.death','implementation':{'type':'provider','provider':'reference.depletion_counter.hold'}})
        p['entities'][0]['components']['lifecycle']['rules']={'lifecycle.death':'rule/depletion_counter/hold'}
    p['scenarioDraft']={'id':'scene/depletion_counter','ruleset':'ruleset/ark_standard','map':{'rows':4,'cols':4},'initialEntities':[{'definition':'unit/depletion_counter/source','instanceAlias':'source','position':{'row':1,'col':0}},{'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':1,'col':1}}]}
    registry={**providers(),'reference.depletion_counter.hold':{'callable':hold_policy,'version':'1'}}
    return Engine.create(Compiler(providers=registry).compile(p),providers=registry)
def main():
    guard=implementation_digest();rows=[]
    for hold in (False,True):
        s=make(hold);s.ctx.effects.execute('source',['pillar'],{'op':'damage','damage_type':'true','scale':1});s.session.advance(61)
        rows.append({'existing_pure_death_hold':hold,'actual_hp':s.ctx.resources.current('pillar','hp'),'actual_alive':s.ctx.alive('pillar'),'actual_active':s.ctx.active('pillar'),'actual_state':s.ctx.get('pillar',('runtime','state')),'scheduled_depletion_tasks':[x for x in s.session.scheduler.pending if 'depletion' in x['kind']],'actual_candead_present':any('candead' in x['definition'] for x in s.ctx.buffs._instances(s.session.world.resolve('pillar')))})
    assert rows[0]['actual_hp']==0 and rows[0]['actual_alive'] is False
    assert rows[1]['actual_hp']==0 and rows[1]['actual_alive'] is True and not rows[1]['actual_candead_present'] and not rows[1]['scheduled_depletion_tasks']
    report={'parent_core':guard,'guard_equal':guard==implementation_digest(),'counter_reproduced':True,'expected_source_behavior':'HP exactly0, alive damaged stage; owned two-second expiry only grants candead; later actual hit selects collapse direction','actual_variants':rows,'scope':'Original source payload plus ordinary health damage on frozen parent; no raw logs persisted','source_payload_builder_sha256':hashlib.sha256((ROOT/'tools/chapter09_pillar_v1/build_payload.py').read_bytes()).hexdigest()}
    out=ROOT/'validation/campaign/chapter09_depletion';out.mkdir(parents=True,exist_ok=True);(out/'parent.counter.v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()

from tools.experiments.m42_peer.test_reentry import *
import hashlib
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    before=implementation_digest();p=fixture();p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]
    p['entities'][1]['components']['attributes']['base']['atk']=100;p['entities'][2]['tags'].append('victim')
    p['selectors'].append({'id':'selector/victim','kind':'selector','region':{'type':'all'},'filters':[{'tag':'victim'}]})
    p['abilities'][0]['selector']='selector/victim';p['abilities'][0]['activation']['on_start'].append({'op':'damage','damage_type':'physical'})
    program=Compiler().compile(p);s=Engine.create(program,seed=4242);assert len(s.ctx.get('b',('buffs','instances')))==1
    commands=[{'action':'skill','source':'a','ability':'ability/leave','at':0}];s.submit({k:v for k,v in commands[0].items() if k!='at'},at=0);s.advance(1)
    out=ROOT/'validation/campaign/m42_peer';out.mkdir(exist_ok=True)
    for name,value in [('retire_input.json',p),('retire_commands.json',commands),('retire_final.json',s.snapshot()),('retire_replay.json',s.export_replay())]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    after=implementation_digest();assert before==after
    locks=['tools/experiments/m42_peer/test_reentry.py',str(Path(__file__).relative_to(ROOT)),'../unpack_work/campaign_m42_aura_remove_candidate/ark_sim/domains/buffs.py',
        '../unpack_work/campaign_m42_aura_remove_candidate/ark_sim/domains/lifecycle.py']
    report={'schema':'ark-sim/independent-runtime-counterexample/v1','status':'actual_samecast_stale_aura','core_before':before,'core_after':after,
        'source_locks':{x:sha(ROOT/x) for x in locks},'actual_module':sys.modules['ark_sim'].__file__,'input_sha256':sha(out/'retire_input.json'),
        'commands_sha256':sha(out/'retire_commands.json'),'initial_HP':100,'bare_DEF':10,'aura_DEF_delta':5,'attack':100,'expected_damage':90,
        'actual_damage':[e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted'],'expected_final_HP':10,'actual_final_HP':s.ctx.resources.current('b','hp'),
        'parent_alive_after_command':s.ctx.alive('parent'),'ordered_retire_and_damage':[thaw(e) for e in s.session.events if e['type'] in ('entity.withdraw','damage.accepted')],
        'explanation':'During reconciliation a leaving child on_remove retires the parent source. Old desired/member snapshot survives until the later maintenance, and the next effect in the same ability sees stale DEF.',
        'earlier_invalid_fixture':'Direct child->parent remove reference is a dependency cycle and rejected; original initial.log is fixture evidence only.',
        'actual_client_verified':False,'formal_approved':False}
    (out/'retire_samecast_original_failure.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha256':sha(out/'retire_samecast_original_failure.json'),'actual_HP':report['actual_final_HP'],'core':before}))
if __name__=='__main__':main()

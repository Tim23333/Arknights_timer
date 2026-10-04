"""Independent primary union and live half-open eligibility boundary tests."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m59_area_primary_candidate'
CORE='84b4146bd574dda5dfd833314bee46c4370e583bcc8ef900075911fdafadbd9a'
OUT=ROOT/'validation/campaign/m59_root_peer'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import observations,export_events,write_canonical
from tools.experiments.m53_root_peer.verify import fixture


def make_fixture():
    p=fixture();p['rules'][1]['parameters'].update(include_primary=True)
    effect=p['abilities'][0]['activation'].pop('on_start')[0]
    effect['center_position']={'row':0,'col':0}
    p['abilities'][0]['target_capture']='at_cast';p['abilities'][0]['timeline']=[{'at_seconds':.1,'effect':effect}]
    p['rules'].append({'id':'rule/peer_available','kind':'rule','contract':'targeting.availability',
        'implementation':{'type':'expression','expression':'9 not in inputs.selection_states.candidate.abnormal_flags'}})
    p['entities'][1]['rules']={'targeting.availability':'rule/peer_available'}
    p['buffs']=[{'id':'buff/hidden','kind':'buff','selection_flags':{'abnormal_flags':[9]}},
                {'id':'buff/immune9','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_immunes':[9]}}]
    p['entities'][1]['components']['abilities']=['ability/immune9']
    p['abilities'].append({'id':'ability/immune9','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/immune9'}]},'timeline':[]})
    p['scenarioDraft']['initialEntities'][1]['components']={'buffs':{'initial':['buff/hidden','buff/immune9']}}
    return p


def main():
    import ark_sim
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    guards=[Path(__file__),RUNTIME/'ark_sim/domains/qualified_areas.py',ROOT/'tools/experiments/m53_root_peer/verify.py']
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};cases=[]
    for name,pulse,expected in [('expiry_half_open',False,1000),('renewed_live_immunity',True,930)]:
        p=make_fixture();program=Compiler().compile(p);s=Engine.create(program,seed=59077)
        commands=[{'at':0,'action':'skill','source':'caster','ability':'ability/peer_area'}]
        if pulse:commands.append({'at':2,'action':'skill','source':'main','ability':'ability/immune9'})
        for c in commands:s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
        s.advance(1);directory=OUT/name;directory.mkdir(parents=True,exist_ok=True);cp=directory/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin));s.advance(4);r.advance(4)
        actual=s.ctx.resources.current('main','hp');assert actual==expected,(name,actual,expected)
        assert s.ctx.resources.current('neighbor','hp')==1000
        observed=observations(s);assert observed==observations(r)==observations(replay(program,s.export_replay()))
        for filename,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('snapshot.json',s.snapshot())]:write_canonical(directory/filename,value)
        journal=export_events(directory/'events.jsonl',s);cases.append({'case':name,'HP':actual,'expected_HP':expected,'observations':observed,'journal':journal,'durable_checkpoint_equal':True,'replay_equal':True})
    p=make_fixture();p['rules'][0]['implementation']={'type':'expression','expression':"{'accepted':inputs.candidate.id == ctx.target.id,'reason':'custom captured identity'}"}
    p['scenarioDraft']['initialEntities'][1].pop('components');s=Engine.create(Compiler().compile(p),seed=59077)
    s.submit({'action':'skill','source':'caster','ability':'ability/peer_area'},at=0);s.advance(5)
    assert s.ctx.resources.current('main','hp')==930 and s.ctx.resources.current('neighbor','hp')==1000
    cases.append({'case':'custom_child_rule_receives_captured_target','passed':True})
    write_canonical(OUT/'custom_input.json',p);write_canonical(OUT/'custom_snapshot.json',s.snapshot())
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};assert before==after and implementation_digest()==CORE
    write_canonical(OUT/'final_review.json',{'schema':'ark-sim/primary-area-independent-review/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'cases':cases,'scope':'Fresh sourceATK70, geometry far0,0 and target2,2; half-open immunity expires at packet tick3, public renewal at2; custom child-rule target context; full event/diskCP/replay',
        'whole_stage_executed':False,'actual_client_verified':False})
    print(json.dumps({'passed':True,'cases':len(cases)}))


if __name__=='__main__':main()

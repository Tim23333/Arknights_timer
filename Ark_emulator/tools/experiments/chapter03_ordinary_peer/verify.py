"""Independent ordinary source bindings and per-hit defense with public block."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m54_qualified_visibility_candidate'
CORE='e6e0142c9ef9aa2cdcf35188aba0865efba370346eecf1c50750a45f56974b75'
MODEL=ROOT/'packages/campaign/chapter03_units/ordinary.reference_model.json'
SOURCE=ROOT/'packages/campaign/chapter03_sources/native.reference.json'
OUT=ROOT/'validation/campaign/chapter03_ordinary_peer'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import observations,export_events,write_canonical


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    import ark_sim
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    assert sha(MODEL)=='daa790f1c89da896a34003197b71815643408fad44ad7fec2ceb4e45a59db0c7'
    assert sha(SOURCE)=='d6a1d5294e1419d6ee41022efa1ef93a0ad44b6effb80c4bdfcf7fc3e7cd1e35'
    guards=[MODEL,SOURCE,Path(__file__)];before={str(p):sha(p) for p in guards};source=json.loads(SOURCE.read_bytes());module=json.loads(MODEL.read_bytes())
    cases=[]
    for unit in module['entities']:
        v=source['variants'][unit['metadata']['native_variant_id']];a=v['native_enemy']['resolved']['attributes'];base=unit['components']['attributes']['base']
        assert unit['metadata']['native_reference']==v['native_reference']
        assert (base['max_hp'],base['atk'],base['def'],base['mres'])==(a['maxHp'],a['atk'],a['def'],a['magicResistance'])
        if v['native_enemy']['resolved']['motion']=='FLY':
            assert a['maxHp']==1870 and unit['components']['abilities']==[] and unit['components']['selection_state']['motion']==2
            cases.append({'case':v['variant_id'],'source_bound_no_attack_fly':True,'HP':1870});continue
        native=v['modes'][0]['nodes']['_combat'];r=native['raw'];frames=[e['frame'] for e in native['animation_binding']['events'] if e['name']=='OnAttack']
        assert r['_selectTargetSource']==2 and r['_waitForAttackEvent']==1
        packet=a['atk']/2 if native['native_class']=='MultiMeleeAttack' else a['atk']
        p=json.loads(MODEL.read_bytes())
        p['entities'].append({'id':'unit/peer_guard','kind':'entity','tags':['player'],'components':{
            'spatial':{},'attributes':{'base':{'max_hp':20000,'def':210,'mres':0,'block_count':1}},
            'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},
            'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'abilities':['ability/peer_def']}})
        p.setdefault('buffs',[]).append({'id':'buff/peer_def','kind':'buff','modifiers':[{'attribute':'def','layer':'flat','value':40}]})
        p['abilities'].append({'id':'ability/peer_def','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/peer_def'}]},'timeline':[]})
        p['scenarioDraft']={'id':'scene/peer/ordinary','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3},
            'roster':['unit/peer_guard'],'resources':{'dp':{'initial':1,'capacity':1}},
            'initialEntities':[{'definition':unit['id'],'instanceAlias':'enemy','position':{'row':0,'col':0},
                'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':2},'checkpoints':[]}}]}
        commands=[{'at':0,'action':'deploy','definition':'unit/peer_guard','alias':'guard','position':{'row':0,'col':0}}]
        if len(frames)==2:commands.append({'at':18,'action':'skill','source':'guard','ability':'ability/peer_def'})
        program=Compiler().compile(p);s=Engine.create(program,seed=3883)
        for c in commands:s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
        s.advance(4);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('guard')
        directory=OUT/v['native_reference']['id'];directory.mkdir(parents=True,exist_ok=True)
        cp=directory/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin));end=max(frames)+2;s.advance(end-4);restored.advance(end-4)
        hits=[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']
        expected=[(frame+1,max(packet-(250 if len(frames)==2 and index==1 else 210),packet*.05)) for index,frame in enumerate(frames)]
        assert hits==expected,(v['variant_id'],hits,expected)
        observed=observations(s);assert observed==observations(restored)==observations(replay(program,s.export_replay()))
        for name,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('snapshot.json',s.snapshot())]:write_canonical(directory/name,value)
        journal=export_events(directory/'events.jsonl',s);cases.append({'case':v['variant_id'],'source_frames':frames,'expected':expected,'actual':hits,'observations':observed,'journal':journal,'durable_checkpoint_equal':True,'replay_equal':True})
    after={str(p):sha(p) for p in guards};assert before==after and implementation_digest()==CORE
    report={'schema':'ark-sim/independent-chapter03-ordinary-review/v1','passed':True,'cases':cases,'source_start':before,'source_end':after,'core_start':CORE,'core_end':implementation_digest(),
        'scope':'Independent raw source binding all eight; fresh DEF210 actual public blockers; multi-hit split225 before per-hit DEF and public DEF+40 between f12/f23; diskCP/full log replay',
        'actual_client_verified':False,'whole_stage_executed':False}
    write_canonical(OUT/'final_review.json',report);print(json.dumps({'passed':True,'cases':len(cases)}))


if __name__=='__main__':main()

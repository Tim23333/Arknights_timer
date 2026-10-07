"""Independent capped clock v2 probes; v1 fixtures/assertions remain frozen."""
import copy,json,math,traceback,gc,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.chapter0_source_numeric_peer_v1 import verify as F
F.MODULE=F.ROOT/'packages/campaign/chapter0_consumers/enemies.module.v2.json'
SOURCE=json.loads(F.SOURCE.read_bytes());ROWS=[];FACTS={}
def inventory():
    assert F.sha(F.MODULE)=='15f7c0e7ec22e7cd39d861895e8bcc0986f6912000db4bff3b25c56817bdbf3f'
    old=json.loads((F.MODULE.parent/'enemies.module.v1.json').read_bytes());new=json.loads(F.MODULE.read_bytes());restored=copy.deepcopy(new)
    restored.pop('rules');restored['manifest']['metadata'].pop('clock_binding_v2')
    for a in restored['abilities']:a.pop('rules')
    assert restored==old and len(new['rules'])==14
    for ability in new['abilities']:
        raw=ability['metadata']['native_owned_node']['raw']
        for contract,key in [('ability.windup','timing_parameters'),('ability.duration','duration_parameters')]:
            rule=next(r for r in new['rules'] if r['id']==ability['rules'][contract]);assert rule['contract']==contract and rule['parameters']=={'minimum':.1,'maximum':raw['_maxAnimScale']}
            assert rule['metadata']['client_formula_verified'] is False
    FACTS['inventory']={'old_full_package_restored_equal':True,'only_clock_rules_and_explicit_metadata_changed':True,'native_float32_caps_preserved':True,'rules':14}
def speed(v,ratio):
    key=v['prefab_key'];label=key+'/'+str(ratio);s=F.cpp(F.fixture(key,ratio),label);o=F.oracle(v);raw=v['modes'][0]['nodes']['_combat']['raw'];cap=raw['_maxAnimScale'];divisor=max(.1,min(ratio,cap) if cap>0 else ratio)
    # Independently convert authored integer frames after the declared divisor;
    # quantum is one thirtieth second and native float32 cap remains exact.
    hit=math.ceil(o['hit_frame']/divisor-1e-10);full=math.ceil(o['full_frame']/divisor-1e-10);interval=math.ceil(o['base_interval']*30/ratio-1e-10)
    starts=F.ev(s,'ability.started');hits=F.ev(s,'damage.accepted');ends=F.ev(s,'ability.finished');times=[e['time'] for e in starts];amount=max(o['atk']*o['scale']-83,.05*o['atk']*o['scale'])
    data={'native_cap':cap,'ratio':ratio,'divisor':divisor,'expected_hit_offset':hit,'expected_full_offset':full,'expected_interval':interval,'starts':times,'hit_times':[e['time'] for e in hits],'end_times':[e['time'] for e in ends],'HP':s.ctx.resources.current('first','hp'),'SP':s.ctx.resources.current('first','sp')};FACTS[label]=data
    assert len(times)>=2 and all(b-a==interval for a,b in zip(times,times[1:]));assert data['hit_times']==[t+hit for t in times if t+hit<=130];assert data['end_times']==[t+full for t in times if t+full<=130]
    assert all(h['payload']['amount']==amount for h in hits) and data['HP']==11731-len(hits)*amount and data['SP']==7
def life_fixture(source_dead):
    p=F.fixture('enemy_1007_slime');killer=copy.deepcopy(next(e for e in p['entities'] if e['id']=='unit/peer0/second'));killer['id']='unit/peer0/killer';killer['components']['attributes']['base']['atk']=20000;killer['components']['spatial']['blocking']=False;killer['components']['abilities']=['ability/peer0/terminate'];p['entities'].append(killer)
    target='unit/ch0/enemy_1007_slime' if source_dead else 'unit/peer0/first';p['selectors'].append({'id':'selector/peer0/terminate','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['definition_id'],'equals':target}},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/peer0/terminate','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer0/terminate','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    p['scenarioDraft']['initialEntities'].append({'definition':killer['id'],'instanceAlias':'killer','position':{'row':2,'col':8}})
    p['scenarioDraft']['commands']=[{'at':5,'action':'skill','source':'killer','ability':'ability/peer0/terminate'}]
    if not source_dead:p['scenarioDraft']['commands'].append({'at':12,'action':'deploy','entity':'unit/peer0/second','alias':'second','row':1,'col':0})
    return p
def life(source_dead):
    label='public-source-death-cancel' if source_dead else 'public-target-death-new-blocker';s=F.cpp(life_fixture(source_dead),label,cut=7,end=100);source=s.session.world.resolve('enemy');first=s.session.world.resolve('first');hits=[e for e in F.ev(s,'damage.accepted') if e['payload']['source']==source];data={'source_hits':hits,'death_events':F.ev(s,'entity.died'),'ability_cancelled':F.ev(s,'ability.cancelled'),'pending_jobs':F.thaw(s.session.scheduler.snapshot())};FACTS[label]=data
    if source_dead:
        assert not s.ctx.active(source) and s.ctx.active(first) and not hits and s.ctx.resources.current(first,'hp')==11731
        assert not s.ctx.get(source,('runtime','casts'));assert not any(t['kind'].startswith('domain.ability') and t['payload'].get('source')==source for t in s.session.scheduler.pending)
    else:
        second=s.session.world.resolve('second');assert not s.ctx.active(first) and s.ctx.active(source) and s.ctx.active(second);assert hits and all(e['payload']['target']==second for e in hits)
        assert all(e['time']>=12 for e in hits) and s.ctx.resources.current(second,'hp')==11731-47*len(hits) and s.ctx.resources.current(second,'sp')==7
def main():
    guards={str(p):F.sha(p) for p in [F.MODULE,F.SOURCE,*[p for p in (F.ROOT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]]};jobs=[('v2-exact-projection-and-clock-caps',inventory)]
    for v in SOURCE['variants'].values():
        if v['modes'][0]['nodes']['_combat']['native_class']=='MeleeAttack':
            for ratio in (1.25,.75):jobs.append((v['prefab_key']+'/'+str(ratio),lambda v=v,ratio=ratio:speed(v,ratio)))
    jobs.extend([('public-target-death-new-blocker',lambda:life(False)),('public-source-death-cancel',lambda:life(True))])
    for label,fn in jobs:
        try:fn();ROWS.append({'case':label,'passed':True})
        except Exception as e:ROWS.append({'case':label,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
        print(json.dumps(ROWS[-1]),flush=True);gc.collect()
    result={'schema':'ark-sim/chapter0-capped-clock-independent-peer/v2','core':F.implementation_digest(),'passed':all(r['passed'] for r in ROWS),'cases':ROWS,'facts':FACTS,'full_disk_CP_head':F.PROOFS,'source_guards':guards,'source_unchanged':all(F.sha(p)==h for p,h in guards.items()),'native_formula_verified':False,'clock_policy':'Replaceable source-declared FROM_ATTACK_SPEED / capped divisor model, matching m26 reference; native method bodies not recovered','old_v1_evidence_preserved':True,'whole_stage':False,'client_verified':False}
    out=F.OUT/'clock.actual.v2.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return 0 if result['passed'] and result['source_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())

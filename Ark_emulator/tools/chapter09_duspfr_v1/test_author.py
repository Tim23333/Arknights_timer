import sys,json,copy,traceback,os,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_duspfr_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter09_duspfr_v1.build import build,providers,BODY,FLAME,TRAIT,DEAD,pillar
LOG=Path('E:/ArkSimLogs/runs/chapter09_duspfr_author_v1');OUT=ROOT/'validation/campaign/chapter09_duspfr_v1';RESULTS=[];FACTS={};ARTIFACTS=[];CLEAN=[]
def fixture(*,res=20,hp=20000,atk=500,pos=(3,4),other=False,pillar_actor=False):
    p=build();p['entities'][0]['components']['attributes']['base']['atk']=atk
    target={'id':'unit/duspfr/test/player','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':hp,'atk':9000,'def':100,'mres':res,'block_count':2}},'resources':{'hp':{'role':'health','initial':hp,'capacity':hp}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/duspfr/test/lethal'],'elemental':{'eligibility_rule':'rule/ch9/duspfr/eligible','elements':{'FIRE':{'capacity':1000,'resistance':0,'recovery_rate':0,'break_duration_seconds':10,'rules':{'elemental.capacity':'rule/ch9/duspfr/capacity','elemental.loss':'rule/ch9/duspfr/loss','elemental.recovery':'rule/ch9/duspfr/recovery','elemental.break_duration':'rule/ch9/duspfr/duration'},'on_break':[],'on_end':[]}}}}}
    p['entities'].append(target);p['selectors'].append({'id':'selector/duspfr/test/source','kind':'selector','region':{'type':'radius','radius':2},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1});p['abilities'].append({'id':'ability/duspfr/test/lethal','kind':'ability','activation':{'mode':'manual'},'selector':'selector/duspfr/test/source','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    initial=[{'definition':BODY,'instanceAlias':'source','position':{'row':3,'col':3}},{'definition':target['id'],'instanceAlias':'player','position':{'row':pos[0],'col':pos[1]}}]
    if other:initial.append({'definition':BODY,'instanceAlias':'other','position':{'row':4,'col':3}})
    if pillar_actor:initial.append({'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':3,'col':2}})
    p['scenarioDraft']={'id':'scene/duspfr/full','ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':7},'initialEntities':initial,'commands':[]};return p
def sim(p=None):return Engine.create(Compiler(providers=providers()).compile(p or fixture()),providers=providers(),seed=173)
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def lethal(s):s.ctx.effects.execute('player',['source'],{'op':'damage','damage_type':'true','scale':1})
def eph(s):return s.ctx.get('player',('runtime','elemental'))
def first_flame_packet():
    s=sim();s.advance(18);assert s.ctx.resources.current('player','hp')==20000;s.advance(1);assert s.ctx.resources.current('player','hp')==19952
    accepted=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(accepted)==1 and accepted[0]['time']==18 and accepted[0]['payload']['amount']==48
    FACTS['first_contact']={'tick':18,'hp_loss':48,'native_health_scale':.12,'native_ep_ratio':.06,'elemental_state':eph(s)}
    before=s.ctx.resources.current('player','hp');s.advance(15);assert before-s.ctx.resources.current('player','hp')==48
    assert eph(s)['remaining']['FIRE']==940
    s=sim(fixture(res=50,atk=800));s.advance(19);assert s.ctx.resources.current('player','hp')==19952 and eph(s)['remaining']['FIRE']==952
def separate_trigger_and_target():
    s=sim(fixture(pos=(3,4.5)));s.advance(5);assert not any(e['type']=='ability.started' and e['payload']['ability']==FLAME for e in s.session.events)
    s.ctx.set('player',('spatial','position'),{'row':3,'col':4});s.advance(1);assert any(e['type']=='ability.started' and e['payload']['ability']==FLAME for e in s.session.events)
    for changes in [{'motion':2},{'category':2},{'target_free':True},{'abnormal_flags':[9]}]:
        s=sim();state=s.ctx.get('player',('selection_state',));state.update(changes);s.ctx.set('player',('selection_state',),state);s.advance(1);assert not s.ctx.get('source',('runtime','casts'),{})
def death_parallel_positive_pillar():
    s=sim(fixture(other=True,pillar_actor=True));lethal(s);assert s.ctx.resources.current('source','hp')==0 and s.ctx.alive('source') and not s.ctx.active('source')
    starts=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==s.session.world.resolve('source')];assert len(starts)==5 and all(e['time']==0 for e in starts)
    s.advance(30);assert s.ctx.resources.current('player','hp')==20000 and s.ctx.resources.current('pillar','hp')==5000;s.advance(1)
    assert s.ctx.resources.current('player','hp')==19600 and s.ctx.resources.current('pillar','hp')==4500 and s.ctx.depletion.state('pillar')['stage']=='collapsing'
    assert s.ctx.resources.current('other','hp')==0 and s.ctx.alive('other') and s.ctx.alive('source')
    s.advance(4);assert not s.ctx.alive('source');death=next(e for e in s.session.events if e['type']=='instant_kill.executed' and e['payload'].get('cause')=='duspfr_suicide');assert death['time']==34 and death['payload']['source'] is None
    s.advance(41);assert not s.ctx.alive('pillar') and len([e for e in s.session.world.entities() if e['definition_id']=='unit/ch9/pillar/ruin'])==2
    FACTS['parallel']={'started':5,'start_tick':0,'damage_tick':30,'positive_pillar_hp':4500,'suicide_tick':34,'source_none':True}
def silenced_zero_and_stun_cancel():
    p=fixture();p['buffs'].append({'id':'buff/duspfr/test/silence','kind':'buff','selection_flags':{'abnormal_flags':[12]}});p['entities'][0]['dependencies']=['buff/duspfr/test/silence'];s=sim(p);s.ctx.buffs.apply('player','source','buff/duspfr/test/silence');lethal(s);assert not s.ctx.alive('source') and not any(e['type']=='ability.started' and '/dead_' in e['payload']['ability'] for e in s.session.events)
    s=sim();s.advance(19);s.ctx.set('source',('selection_state','abnormal_flags'),[0]);before=s.ctx.resources.current('player','hp');s.advance(35);assert s.ctx.resources.current('player','hp')==before and not s.ctx.get('source',('runtime','casts'),{})
def public_cpp_head():
    p=fixture(pillar_actor=True);p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'player','ability':'ability/duspfr/test/lethal'}];s=sim(p);s.advance(8);LOG.mkdir(parents=True,exist_ok=True);path=LOG/'deadboom.public.checkpoint.json';path.write_text(json.dumps(s.checkpoint()),encoding='utf8');ARTIFACTS.append({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()});r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=providers());s.advance(80);r.advance(80);assert cp(s)==cp(r);h=replay(s.program,s.export_replay(),providers=providers());assert cp(h)==cp(s)
def blocked_melee_and_route_birth():
    p=fixture(pos=(3,3));body=p['entities'][0]['components'];body['selection_state']['abnormal_flags']=[12];target=next(e for e in p['entities'] if e['id']=='unit/duspfr/test/player');target['components']['deployable']={'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'};p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':'WALK','startPosition':{'row':3,'col':3},'endPosition':{'row':3,'col':6},'checkpoints':[]};s=sim(p);s.ctx.spatial.blocking();assert s.ctx.spatial.blocked_by('source')==s.session.world.resolve('player')
    s.advance(13);assert s.ctx.resources.current('player','hp')==20000;s.advance(1);assert s.ctx.resources.current('player','hp')==19600
    attacks=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['ability'].endswith('blocked_attack')];assert attacks[0]['time']==0
    s.ctx.lifecycle.retire('player','withdrawn');s.advance(1);assert s.ctx.spatial.blocked_by('source') is None;s.advance(50);assert len([e for e in s.session.events if e['type']=='ability.started' and e['payload']['ability'].endswith('blocked_attack')])==1
    assert s.ctx.get('source',('spatial','position'))['col']>3
def repeated_flame_and_flight_cpp():
    p=fixture(hp=50000);target=next(e for e in p['entities'] if e['id']=='unit/duspfr/test/player');target['components']['elemental']['elements']['FIRE']['capacity']=10000;s=sim(p);s.advance(16);checkpoint=cp(s);r=Engine.restore(s.program,checkpoint,providers=providers());s.advance(604);r.advance(604);assert cp(s)==cp(r)
    starts=[e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==FLAME];assert starts==[0,618]
    packets=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(packets)==20 and s.ctx.resources.current('player','hp')==50000-20*48 and eph(s)['remaining']['FIRE']==10000-20*30
    h=replay(s.program,s.export_replay(),providers=providers());assert cp(h)==cp(s);FACTS['repeat_clock']={'first_start':0,'next_start':618,'first_cast_packets':20,'flight_cpp':True,'public_head':True}
def target_cancel_and_current_packet_stats():
    s=sim();s.advance(19);s.ctx.set('source',('attributes','base','atk'),800);s.ctx.set('player',('attributes','base','mres'),50);s.advance(15);assert s.ctx.resources.current('player','hp')==19904 and eph(s)['remaining']['FIRE']==922
    s.ctx.lifecycle.retire('player','withdrawn');s.advance(1);assert not s.ctx.get('source',('runtime','casts'),{})
    stops=[e for e in s.session.events if e['type']=='attachment.finished'];assert stops and stops[-1]['payload']['reason']=='target_invalid'
def health_first_lethal_skips_ep_and_real_fire():
    s=sim(fixture(hp=30));s.advance(19);assert not s.ctx.alive('player') and eph(s)['remaining']['FIRE']==1000
    p=fixture(res=40);target=next(e for e in p['entities'] if e['id']=='unit/duspfr/test/player');target['components']['elemental']['elements']['FIRE']['capacity']=30
    p['buffs'].append({'id':'buff/duspfr/test/fire_res','kind':'buff','modifiers':[{'attribute':'mres','layer':'flat','value':-20}]});p['rules'].append({'id':'rule/duspfr/test/fire_no_source','kind':'rule','contract':'damage.pipeline','metadata':{'input_bindings':{'resistance':{'entity':'target','attribute':'mres'}}},'implementation':{'type':'graph','nodes':[{'id':'settle','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount * (1-inputs.effect.resistance*.01),'allocations':[],'events':[]}"}],'output':'nodes.settle'}})
    profile=target['components']['elemental']['elements']['FIRE'];profile['on_break']=[{'op':'apply_buff','buff':'buff/duspfr/test/fire_res'},{'op':'no_source_damage','fixed_amount':1200,'damage_type':'arts','attack_type':'NONE','damage_without_modify':False,'ignore_for_sp':True,'node_is_env_damage':False,'env_blackboard_injected':False,'environmental':False,'origin':{'native':'FIRE_break'},'rules':{'damage.pipeline':'rule/duspfr/test/fire_no_source'}}];profile['on_end']=[{'op':'remove_buff','buff':'buff/duspfr/test/fire_res'}]
    s=sim(p);s.advance(19);assert s.ctx.resources.current('player','hp')==20000-36-960 and eph(s)['break'] is not None
    events=[e for e in s.session.events if e['type']=='damage.accepted'];assert events[-1]['payload']['source'] is None and events[-1]['payload']['amount']==960
def owned_fault_and_static_callback_rejection():
    p=fixture();aid=next(a for a in p['abilities'] if a['id']=='ability/ch9/duspfr/dead_Damage');aid['activation']['on_start']=[{'op':'random','stream':'owned_fail','probability':1,'on_success':[{'op':'modify_resource','resource':'missing','amount':1}]}];s=sim(p);before=cp(s)
    try:lethal(s)
    except ValueError:pass
    else:raise AssertionError('faulted owned parallel start accepted')
    assert cp(s)==before and not s.ctx.depletion._callbacks and not s.ctx.depletion._attacks and not s.ctx.depletion._deliveries
    s=sim();lethal(s);before=cp(s);owner=s.session.world.resolve('source');cast=next(c for c in s.ctx.get(owner,('runtime','casts')).values() if c['ability'].endswith('dead_Damage'))
    try:s.ctx.effects.execute(owner,[owner],{'op':'retire','target':'source'},cast=copy.deepcopy(cast))
    except ValueError:pass
    else:raise AssertionError('static owned cast borrowed terminal authority')
    s.ctx.abilities.handle_effect(s.session,{'source':owner,'cast':cast['id'],'effect':{'op':'retire','target':'source'},'condition':None});assert cp(s)==before
    s=sim();s.ctx.buffs.remove('source',TRAIT);lethal(s);assert not s.ctx.alive('source') and not any(e['type']=='ability.started' and '/dead_' in e['payload']['ability'] for e in s.session.events)
def cleanup():
    if LOG.exists() and any(LOG.iterdir()):
        r=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs_v2.py'),'--run-dir',str(LOG),'--apply','--minimum-age-minutes','0','--completed-pid',str(os.getpid())],capture_output=True,text=True,encoding='utf8');assert r.returncode==0;CLEAN.append(json.loads(r.stdout))
def main():
    guard=implementation_digest();source_paths=[Path(__file__),ROOT/'tools/chapter09_duspfr_v1/build.py',ROOT/'tools/chapter09_ability_clock_v1/flame_channel.py',ROOT/'tools/chapter09_linked_elemental/fixture_v2.py',ROOT/'tools/chapter09_pillar_lifecycle_v1/build.py',ROOT/'tools/chapter09_pillar_v1/build_payload.py',ROOT/'packages/campaign/chapter09_consumers/linked_elemental/duspfr.consumer.requirements.v1.json',ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json',ROOT/'packages/campaign/chapter09_source_prepare/source.detail.v1.json',ROOT/'packages/campaign/chapter09_consumers/pillars/source.closure.v1.json'];source_before={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths};module_before=hashlib.sha256(json.dumps(build(),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for fn in [first_flame_packet,separate_trigger_and_target,death_parallel_positive_pillar,silenced_zero_and_stun_cancel,public_cpp_head,blocked_melee_and_route_birth,repeated_flame_and_flight_cpp,target_cancel_and_current_packet_stats,health_first_lethal_skips_ep_and_real_fire,owned_fault_and_static_callback_rejection]:
        try:fn();RESULTS.append({'case':fn.__name__,'passed':True})
        except Exception as error:RESULTS.append({'case':fn.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
        finally:cleanup()
    source_after={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths};module_after=hashlib.sha256(json.dumps(build(),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();equal=guard==implementation_digest() and source_before==source_after and module_before==module_after
    report={'core_before':guard,'core_after':implementation_digest(),'source_before':source_before,'source_after':source_after,'module_before':module_before,'module_after':module_after,'source_guard_equal':equal,'actual_exit':0 if all(x['passed'] for x in RESULTS) and equal else 1,'results':RESULTS,'facts':FACTS,'artifacts':ARTIFACTS,'cleanup':CLEAN,'raw_deleted':all(not Path(x['path']).exists() for x in ARTIFACTS)};(OUT/'author.initial.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())

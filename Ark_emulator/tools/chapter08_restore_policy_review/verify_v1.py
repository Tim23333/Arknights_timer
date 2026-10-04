"""Fresh source-defined Boss births/firstdown endpoint policies, no HP grant."""
import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_wave_track_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_joint_v4.build_bsnake_partial_join_v1 import providers
CORE='4bf1cc96ae41f2850b645c25d772ada1d472f7b0202127fff340a4fc2b0b04c3';BASE=ROOT/'packages/campaign/chapter08_consumers/bsnake';MODULE=BASE/'four_modes.wave_source.v5.json';STAGE=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v3.json';OUT=ROOT/'validation/campaign/chapter08_restore_policy_independent_v1';OWNER='unit/ch8/bsnake/cadb87696bef4de2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def same(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b
def audit():
    assert sha(MODULE)=='944c66226964c3eac64f6e00295e37839489a12da378377724e34f43cbe67613' and sha(STAGE)=='8bac031f347e428def20828cd5790adc25101544303941588c578b123dcaaf6a'
    module=json.loads(MODULE.read_bytes());stage=json.loads(STAGE.read_bytes());old=json.loads((STAGE.parent/'level_main_08-17.native_draft.v1.json').read_bytes());native=json.loads((ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json').read_bytes())['stages']['level_main_08-17']['native_document'];defs={v['id']:v for v in stage['definitions']}
    assert len(defs)==len(stage['definitions'])==336 and len(stage['scenarioDraft']['timeline']['waves'])==4
    assert same(stage['scenarioDraft'],old['scenarioDraft'])
    for d in module['definitions']:assert same(d,defs[d['id']]),d['id']
    changes=[];olddefs={v['id']:v for v in old['definitions']}
    for key,value in defs.items():
        if not same(value,olddefs[key]):changes.append(key)
    assert changes==['rule/ch8/bsnake/first_restore'],changes
    source=json.loads((BASE/'source.closure.v1.json').read_bytes());unit=defs[OWNER]['components'];assert unit['attributes']['base']['max_hp']==50000 and unit['attributes']['base']['atk']==770
    assert unit['rebirth']['restore_ratio']==source['RebornTalent']['raw']['_hpRechargeRatio']==.5
    assert unit['rebirth']['delay_seconds']==source['consumer_merged_BB12']['reborn.duration']['value']==5
    assert unit['rebirth']['max_count']==2
    borns=sum(a.get('count',1) for w in stage['scenarioDraft']['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn');assert borns==44
    assert len(stage['scenarioDraft']['map']['tiles'])==len(native['mapData']['tiles'])
    return {'stage_definitions':336,'native_births':44,'same_scenario_as_prior_v1':True,'only_definition_change_from_prior_stage':changes,'source_original_hp50000_atk770_recharge05_duration5_preserved':True,'stage_sha256':sha(STAGE),'module_sha256':sha(MODULE),'declared_policy':'First100%effectivecapacity75000 after5s ascurrentPRTS reference. hpRecharge.5 raw kept; its native mapping remains unresolved, no new native method claim.'}
def package(born,kill):
    p=json.loads(MODULE.read_bytes());p['definitions'].append({'id':'unit/independent/restore/controller','kind':'entity','tags':['controller'],'components':{'attributes':{'base':{'max_hp':3210,'atk':50000,'def':19,'mres':7}},'resources':{'hp':{'initial':3210,'capacity':3210,'role':'health'}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':1},'spatial':{},'abilities':['ability/independent/firstdown'],'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['definitions'].append({'id':'selector/independent/native_boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}]})
    p['definitions'].append({'id':'ability/independent/firstdown','kind':'ability','selector':'selector/independent/native_boss','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    p['definitions'].append({'id':'unit/independent/restore/recipient','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':6200,'atk':0,'def':456,'mres':29,'one_minus_status_resistance':1}},'resources':{'hp':{'initial':6200,'capacity':6200,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    # Real source Flame actor and native registration roots; no arbitrary dummy or sourceHP replacement.
    flame=json.loads((ROOT/'packages/campaign/chapter08_consumers/flame/module.v4.joint.json').read_bytes());known={d['id']:d for d in p['definitions']}
    for name,values in flame.items():
        if name not in ('entities','abilities','buffs','rules','selectors','projectiles'):continue
        for d in values:
            if d['id'] in known:assert same(d,known[d['id']])
            else:p['definitions'].append(d);known[d['id']]=d
    loop=json.loads((BASE.parent/'flame/loop.profile.v3.json').read_bytes())
    boss_spawn={'kind':'spawn','count':1,'delay_seconds':born/30,'managed':True,'blocks_wave':True,'blocks_fragment':False,'spawn':{'definition':OWNER,'instanceAlias':'boss','position':{'row':4,'col':13}}}
    recipient={'kind':'spawn','count':1,'delay_seconds':151/30,'managed':False,'blocks_wave':False,'blocks_fragment':False,'spawn':{'definition':'unit/independent/restore/recipient','instanceAlias':'recipient','position':{'row':4,'col':14}}}
    p['scenarioDraft']={'id':'scene/independent/full_restore/'+str(born)+'/'+str(kill),'ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':15},'branches':loop['runtime_branch'],
        'initialEntities':deepcopy(loop['initial_entities'])+[{'definition':'unit/independent/restore/controller','instanceAlias':'controller','position':{'row':0,'col':0}}],
        'commands':[{'at':kill,'action':'skill','source':'controller','ability':'ability/independent/firstdown'}],
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[boss_spawn]}]},{'fragments':[{'actions':[recipient]}]}]}}
    p['manifest']['metadata']['independent_fixture']='Exact newv5 Boss definition unchanged; allied-side controller ATK50000 is explicit non-native testability fixture, publictrue firstdown only. Spawnedrecipient afterwave track151ticks probes readyskills under mode2; no99999sourceHP, noHPgrant, no abbreviated5s or28s.'
    return p
def pure_attrs(s):
    a=s.ctx.entity('boss')['components']['attributes'];result={}
    for name in ('max_hp','atk'):
        result[name]=s.ctx.rules.evaluate('attributes.effective',{'base':a['base'][name],'modifier_layers':[m for m in a['modifiers'] if m['attribute']==name],'order':[{'layer':x} for x in ('flat','direct_ratio','final_ratio')]},rule_id='rule/ark_attribute_layers').value
    return result
def state(s):return {'hp':s.ctx.resources.current('boss','hp'),'active':s.ctx.active('boss'),'mode':s.ctx.resources.current('boss','mode'),'attrs':pure_attrs(s)}
def domain(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def run(born,kill):
    p=package(born,kill);reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=1048);folder=OUT/(str(born)+'_'+str(kill));folder.mkdir(parents=True,exist_ok=True)
    s.session.advance(kill+1);waiting=state(s);assert waiting=={'hp':0,'active':False,'mode':0,'attrs':{'max_hp':75000,'atk':1155}},waiting
    boundary=kill+73;s.session.advance(boundary-s.session.time);cp=folder/'checkpoint_waiting.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg)
    s.session.advance(kill+150-s.session.time);before=state(s);assert before['hp']==0 and not before['active']
    s.session.advance(1);after=state(s);assert after=={'hp':75000,'active':True,'mode':2,'attrs':{'max_hp':75000,'atk':1155}},after
    end=kill+214;s.session.advance(end-s.session.time);r.session.advance(end-boundary);head=replay(s.program,s.export_replay(),providers=reg)
    assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
    starts=[(e['time'],e['payload']['ability']) for e in s.session.events if e['type']=='ability.started'];assert not [(t,a) for t,a in starts if kill<t and ('/normal/' in a or '/ignite/' in a or '/explode/' in a)]
    volleys=[e['time'] for e in s.session.events if e['type']=='source.bsnake.screen.volley'];assert volleys==[kill+210],volleys
    launches=[e for e in s.session.events if e['type']=='projectile.launched'];assert len(launches)==7
    (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
    with (folder/'events.jsonl').open('wb') as f:
        for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False)+'\n').encode())
    return {'born':born,'kill':kill,'waiting':waiting,'before_endpoint':before,'after_150ticks':after,'screen_first_volley':volleys,'actual_launch_count7':len(launches),'mode2_skill_gate_no_normal_or_skills':True,'CP':True,'head':True,'all_events':True,'files':{str(p):sha(p) for p in folder.iterdir()}}
def pure_recovery():
    reg=providers();p=package(37,48);s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);rows=[]
    for cap in (1,12345,75000,81234.5):
        for count in (1,2):
            value=s.ctx.rules.evaluate('resource.recovery',{'current':0,'delta':0,'delta_seconds':0,'attributes':{},'parameters':{'capacity':cap,'ratio':.5}},rule_id='rule/ch8/bsnake/first_restore',context={'rebirth':{'count':count}}).value
            assert value==(cap if count==1 else 0);rows.append({'capacity':cap,'count':count,'value':value})
    return rows
def main():
    assert implementation_digest()==CORE;OUT.mkdir(exist_ok=True);a=audit();(OUT/'source.audit.json').write_bytes((json.dumps(a,ensure_ascii=False,indent=2)+'\n').encode());rows=[run(b,k) for b,k in ((37,48),(80,650))];pure=pure_recovery();assert implementation_digest()==CORE
    out=OUT/'report.json';assert not out.exists();out.write_bytes((json.dumps({'status':'two_actual_full_firstrestore_cases_and8pure_capacities_passed','core':CORE,'audit':a,'rows':rows,'pure_recovery':pure,'source_policy':'CurrentPRTS100%first/effective75000, declaredreference; rawrecharge.5 unproven mapping preserved. Old37500 evidence not relabelled.'},ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()

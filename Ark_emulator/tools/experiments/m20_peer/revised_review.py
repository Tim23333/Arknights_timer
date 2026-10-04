"""Fresh db6134 peer expectations; all initial failures remain separate."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.experiments.m20_peer import probe as h
from tools.experiments.m20_peer import behavior_probe as b
from copy import deepcopy
import json
import hashlib
from ark_sim import Engine,Compiler
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
EXPECTED='db6134da42647f1691f8b6fb5318fa8bbbcc455b26b1dc59841d6c1eba95bdcc'
def roundtrip(s):
    r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def direct_behavior_boundary():
    p=h.fixture();p['entities'][0]['components']['behavior']={'machine':'behavior/latent'}
    p['behaviors']=[{'id':'behavior/latent','kind':'behavior','initial':'sleep','states':{'sleep':{},'awake':{'on_enter':[{'op':'emit','event':'must_not_run'}]}},'transitions':[]}]
    s=h.make(p);cp=s.checkpoint()
    assert s.ctx.behavior.plan(2)=={'move':False,'attack':False} and s.checkpoint()==cp
    try:s.ctx.behavior.transition(2,'awake')
    except ValueError:pass
    else:raise AssertionError('direct behavior transition initialized inactive actor')
    assert s.checkpoint()==cp
def late_activation_emission_snapshot():
    p=h.fixture();p['entities'][0]['components']['resources']['sp'].pop('recovery_rate')
    p['buffs']=[{'id':'buff/grants','kind':'buff','events':[{'event':'signal','target':'event_target',
       'effects':[{'op':'modify_resource','resource':'sp','delta':1,'parameters':{'respect_recovery_freeze':True}}]}]}]
    p['entities'][1]['components']['buffs']={'initial':['buff/grants']}
    before={'op':'emit','target':2,'event':'signal'};activate=p['abilities'][1]['activation']['on_start'][0]
    p['abilities'][1]['activation']['on_start']=[before,activate,deepcopy(before)]
    s=h.make(p);h.command(s,'ability/activate',1);s.advance(2)
    assert s.ctx.active(2) and s.ctx.resources.current(2,'sp')==1 # first emission is ineligible, later emission +1
    roundtrip(s)
def generic_inactive_effects_do_not_write_schedule_or_sample():
    p=h.fixture();p['entities'][0]['components']['behavior']={'machine':'behavior/latent'}
    p['behaviors']=[{'id':'behavior/latent','kind':'behavior','initial':'sleep','states':{'sleep':{},'awake':{}},'transitions':[]}]
    p['buffs']=[{'id':'buff/probe','kind':'buff','duration_seconds':1}]
    p['entities'].append({'id':'unit/child','kind':'entity','tags':['ally'],'components':{'spatial':{}}})
    effects=[{'op':'modify_resource','target':2,'resource':'sp','delta':5},{'op':'state','target':2,'state':'awake'},
      {'op':'move','target':2,'position':{'row':0,'col':1}}, {'op':'apply_buff','target':2,'buff':'buff/probe'},
      {'op':'random','target':2,'stream':'imp','probability':1,'on_success':[{'op':'emit','event':'inactive_random'}]},
      {'op':'schedule','target':2,'delay_seconds':.1,'effect':{'op':'emit','event':'inactive_scheduled'}},
      {'op':'spawn','target':2,'definition':'unit/child','position':{'row':0,'col':1},'owner':'target'}]
    p['abilities'][0]['activation']['on_start']=effects
    s=h.make(p);before_rng=s.checkpoint()['kernel']['random'];h.command(s,'ability/grant',1);s.advance(8)
    assert s.ctx.resources.current(2,'sp')==0 and s.ctx.get(2,('behavior','state')) is None
    assert s.ctx.get(2,('spatial','position'))=={'row':0,'col':0} and not s.ctx.get(2,('buffs','instances'))
    assert not [e for e in s.session.events if e['type'] in ('inactive_random','inactive_scheduled','random.branch')]
    assert not [e for e in s.session.world.entities() if e['definition_id']=='unit/child']
    assert s.checkpoint()['kernel']['random']==before_rng
    assert len([e for e in s.session.events if e['type']=='effect.inactive_rejected'])==7
    roundtrip(s)
def native_wrapper_capacity_and_source_equal():
    from tools.build_chapter01_dormant_model import build,OUT,SOURCE
    p=build();assert json.loads(OUT.read_bytes())==p
    n=json.loads(SOURCE.read_bytes());raw=next(c['raw'] for c in n['prefab']['components'].values() if c['native_class']=='Character')
    npc=next(e for e in p['entities'] if e['id']=='unit/ch1_predefined_adnach_e0_l20')
    assert type(raw['_occupiedRemainingCharacterCnt']) is int and raw['_occupiedRemainingCharacterCnt']==npc['components']['deployable']['capacity']==1
    assert npc['metadata']['predefined_activation_profile']['payment'].startswith('preplaced free')
    # Keep actual NPC/skill/roster definitions, but isolate its registered capacity consumer.
    p['scenarioDraft'].pop('timeline');p['scenarioDraft']['waves']=[];p['scenarioDraft']['objectives']={}
    p['scenarioDraft']['parameters']['deploy_capacity']=1
    p['entities'].append({'id':'unit/slot_probe','kind':'entity','tags':['player'],'components':{'spatial':{},
      'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'both'}}})
    p['scenarioDraft']['roster'].append('unit/slot_probe')
    p['abilities'].append({'id':'ability/peer_activate','kind':'ability','activation':{'mode':'manual','on_start':[
      {'op':'activate_predefined','target':'battle','parameters':{'key':'char_211_adnach'}}]},'timeline':[]})
    p['entities'].append({'id':'unit/director','kind':'entity','tags':['ally'],'components':{'spatial':{},'abilities':['ability/peer_activate']}})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':0}})
    # A predefine does not go through ordinary high-ground deployment eligibility.
    s=h.make(p);ref=s.ctx.state()['predefined_registry']['char_211_adnach'];assert not s.ctx.active(ref)
    s.submit({'action':'deploy','definition':'unit/slot_probe','position':{'row':3,'col':2},'alias':'early'},at=0)
    s.submit({'action':'withdraw','source':'early'},at=1);h.command(s,'ability/peer_activate',2)
    s.submit({'action':'deploy','definition':'unit/slot_probe','position':{'row':3,'col':3},'alias':'late'},at=3)
    s.advance(4);assert s.ctx.active(ref) and s.ctx.get(ref,('deployable','capacity'))==1
    rejected=[e for e in s.session.events if e['type']=='command.rejected'];assert len(rejected)==1 and rejected[0]['payload']['reason']=='capacity'
    assert len([e for e in s.session.events if e['type']=='entity.activated' and e['payload']['target']==ref])==1
    roundtrip(s)
if __name__=='__main__':
    files=[Path(__file__),Path(h.__file__),Path(b.__file__),h.ROOT/'tools/build_chapter01_dormant_model.py',
      h.ROOT/'packages/campaign/chapter01_stage_models/m20/level_main_01-11.dormant.partial.json',h.ROOT/'packages/campaign/chapter01_predefines/native.reference.json']
    def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    start=hashes();core=implementation_digest();assert core==EXPECTED
    cases=[]
    funcs=[('original_SP',h.inactive_direct_sp),('original_freeze',h.inactive_snapshot_freeze),('original_behavior',b.case),
      ('registration_lifetime',h.registration_is_not_alias_and_lifetime_starts_at_activation),('double_paid',h.double_activation_rolls_back_public_paid_command),
      ('direct_behavior',direct_behavior_boundary),('late_activation_snapshot',late_activation_emission_snapshot),
      ('generic_inactive_effects',generic_inactive_effects_do_not_write_schedule_or_sample),('native_NPC_capacity',native_wrapper_capacity_and_source_equal)]
    for name,fn in funcs:
        h.LAST=None
        try:fn();c={'case':name,'result':'passed'}
        except Exception as error:c={'case':name,'result':'failed','error':repr(error)}
        if h.LAST is not None:
            s=h.LAST;c.update({'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'initial_scenario':thaw(s.program.scenario),
               'commands':s.export_replay(),'snapshot':s.snapshot(),'events':[thaw(e) for e in s.session.events]})
        cases.append(c)
    end=hashes();stable=start==end and implementation_digest()==core;passed=stable and all(c['result']=='passed' for c in cases)
    out=h.ROOT/'validation/campaign/m20_dormant_peer_db6134.json';out.write_text(json.dumps({'passed':passed,'provisional':True,
      'formal_approval':False,'review_receipt':False,'core_start':core,'core_end':implementation_digest(),'identity_stable':stable,
      'source_start':start,'source_end':end,'runtime_module':h.ark_sim.__file__,'cases':cases},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':passed,'core':core,'cases':[{k:v for k,v in c.items() if k in ('case','result','error')} for c in cases]}))
    raise SystemExit(0 if passed else 1)

"""Independent provisional dormant boundary probes; candidate can still change."""
import json
import hashlib
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];CANDIDATE=ROOT.parent/'unpack_work/campaign_m20_dormant_candidate'
sys.path.insert(0,str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==CANDIDATE/'ark_sim'
sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
LAST=None
def fixture():
    return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':[
      {'id':'unit/latent','kind':'entity','tags':['ally','player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':100}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'},'sp':{'initial':0,'capacity':20,'recovery_rate':1}},'abilities':[]}},
      {'id':'unit/director','kind':'entity','tags':['ally'],'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'atk':10}},
        'resources':{'hp':{'initial':50,'capacity':100,'role':'health'},'sp':{'initial':10,'capacity':20}},'abilities':['ability/grant','ability/activate','ability/emit','ability/heal']}}],
      'abilities':[{'id':'ability/grant','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':2,'resource':'sp','delta':3}]},'timeline':[]},
       {'id':'ability/activate','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'activate_predefined','target':'battle','parameters':{'key':'latent-key'}}]},'timeline':[]},
       {'id':'ability/emit','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'emit','target':'source','event':'signal'}]},'timeline':[]},
       {'id':'ability/heal','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'heal','target':'source','scale':1}]},'timeline':[]}],
      'scenarioDraft':{'id':'scenario/independent_dormant','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},'initialEntities':[
        {'definition':'unit/latent','registration_key':'latent-key','active':False,'position':{'row':0,'col':0}},
        {'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':2}}],'waves':[],'objectives':{}}}
def make(p):
    global LAST
    LAST=Engine.create(Compiler().compile(p),seed=2020);return LAST
def command(s,ability,at):s.submit({'action':'skill','source':'director','ability':ability},at=at)
def inactive_direct_sp():
    s=make(fixture());command(s,'ability/grant',1);s.advance(2)
    actual=s.ctx.resources.current(2,'sp')
    assert actual==0,f'dormant explicit battle SP effect leaked {actual}; expected0 before initialization'
def inactive_snapshot_freeze():
    p=fixture();p['entities'][0]['components']['resources']['sp']['recovery_freeze_rule']='rule/latent_freeze'
    p['rules']=[{'id':'rule/latent_freeze','kind':'calculation_rule','contract':'resource.recovery_freeze',
        'metadata':{'recovery_freeze_authority':'final_override'},'implementation':{'type':'expression','expression':'False if inputs.owner.components.runtime.active else 1/0'}}]
    p['buffs']=[{'id':'buff/listener','kind':'buff','events':[{'event':'healing.accepted',
       'effects':[{'op':'modify_resource','resource':'sp','delta':1,'parameters':{'respect_recovery_freeze':True}}]}]}]
    p['entities'][1]['components']['buffs']={'initial':['buff/listener']}
    s=make(p);command(s,'ability/heal',1);s.advance(2)
    assert s.ctx.resources.current('director','hp')==60,'active heal rejected by dormant custom freeze snapshot evaluation'
    assert s.ctx.resources.current('director','sp')==11 and s.ctx.resources.current(2,'sp')==0
def registration_is_not_alias_and_lifetime_starts_at_activation():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['registration_key']='director'
    p['abilities'][1]['activation']['on_start'][0]['parameters']['key']='director'
    p['scenarioDraft']['initialEntities'][0]['parameters']={'lifetime_seconds':1}
    s=make(p);assert s.session.world.resolve('director')==3 and s.ctx.state()['predefined_registry']['director']==2
    command(s,'ability/activate',5);s.advance(5);assert s.ctx.alive(2) and not s.ctx.active(2)
    s.advance(1);assert s.ctx.active(2) and s.ctx.get(2,('runtime','lifetime','expires_at'))==35
    cp=s.checkpoint();s.advance(30);assert not s.ctx.alive(2)
    r=Engine.restore(s.program,cp);r.advance(30);assert r.snapshot()==s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def double_activation_rolls_back_public_paid_command():
    p=fixture();fx=p['abilities'][1]['activation']['on_start'][0]
    p['abilities'][1]['activation']['on_start']=[fx,dict(fx)]
    p['abilities'][1]['activation']['costs']=[{'resource':'sp','amount':2}]
    s=make(p);command(s,'ability/activate',1);s.advance(2)
    assert not s.ctx.active(2) and s.ctx.resources.current('director','sp')==10
    assert not [e for e in s.session.events if e['type'] in ('entity.created','entity.activated') and e['payload']['target']==2]
    assert len([e for e in s.session.events if e['type']=='command.rejected'])==1
    r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert r.snapshot()==s.snapshot()==replay(s.program,s.export_replay()).snapshot()
if __name__=='__main__':
    start=implementation_digest();cases=[]
    for name,fn in [('inactive_explicit_sp',inactive_direct_sp),('inactive_freeze_snapshot',inactive_snapshot_freeze),
      ('registration_lifetime',registration_is_not_alias_and_lifetime_starts_at_activation),('double_paid_activation',double_activation_rolls_back_public_paid_command)]:
        LAST=None
        try:fn();result={'case':name,'result':'passed'}
        except Exception as error:result={'case':name,'result':'failed','error':repr(error)}
        if LAST is not None:result.update({'program':LAST.program.fingerprint,'runtime':LAST.runtime_fingerprint,
          'initial_scenario':thaw(LAST.program.scenario),'commands':LAST.export_replay(),'snapshot':LAST.snapshot(),
          'events':[thaw(e) for e in LAST.session.events]})
        cases.append(result)
    end=implementation_digest();out=ROOT/'validation/campaign/m20_dormant_peer_initial.json'
    out.write_text(json.dumps({'provisional':True,'formal_approval':False,'fixed_identity_receipt':False,'core_at_start':start,'core_at_completion':end,
      'runtime_module':ark_sim.__file__,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':cases},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'core_start':start,'core_end':end,'cases':[{k:v for k,v in c.items() if k in ('case','result','error')} for c in cases]}))

"""True-death native stationary AoE on two public players, no dummy/live-source workaround."""
import json,hashlib
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter06.cold.policies import providers
from tools.chapter06_units.snslime.build_module import ROOT,OUT
COLD=ROOT/'packages/campaign/chapter06_cold/model.json'

def package():
    p=json.loads(OUT.read_bytes());unit=p['entities'][0]
    for name in ('killer','friend'):
        p['entities'].append({'id':'unit/test/snslime/'+name,'kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'atk':5000 if name=='killer' else 0,'def':100,'mres':0,'attack_speed_ratio':1,'block_count':1 if name=='killer' else 0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'deployable':{'base_cost':5,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/test/snslime/kill'] if name=='killer' else []}})
    p['selectors'].append({'id':'selector/test/snslime/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/test/snslime/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/snslime/enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical','scale':1}}]})
    p['scenarioDraft']={'id':'scene/ch6/snslime/required','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':5},'resources':{'dp':{'initial':30,'capacity':99},'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':unit['id'],'instanceAlias':'slime','position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}}],'roster':['unit/test/snslime/killer','unit/test/snslime/friend']}
    return p
def public_inputs(s):
    for name,col in [('killer',0),('friend',1)]:s.submit({'action':'deploy','definition':'unit/test/snslime/'+name,'alias':name,'position':{'row':0,'col':col}},at=0)
    s.submit({'action':'skill','source':'killer','ability':'ability/test/snslime/kill'},at=2)

def test_required_native_true_death_splash_two_targets_with_cold_ten_each():
    s=Engine.create(Compiler(providers=providers()).compile(package(),packages=[COLD]),seed=6267,providers=providers());public_inputs(s)
    error=None
    try:s.session.advance(34)
    except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)}
    members={name:{'hp':s.ctx.resources.current(name,'hp'),'flags':s.ctx.spatial.selection_state(name,DEFAULT_STATE)['abnormal_flags'],'buffs':s.ctx.get(name,('buffs','instances'),[])} for name in ('killer','friend')}
    events=[e for e in s.session.events if e['type'] in ('damage.accepted','projectile.launched','projectile.hit','projectile.invalid','entity.died')]
    report={'schema':'ark-sim/ch6-snslime-required-death-aoe-source/v1','core':implementation_digest(),'module_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'source_alive':s.ctx.alive('slime'),'source_hp':s.ctx.resources.current('slime','hp'),'time':s.session.time,'error':error,'actual_members':members,'events':events,'expected':{'source_alive':False,'source_hp':0,'splash_per_member':500,'atk_scale':2,'source_atk':300,'member_def':100,'cold_flag':23,'freeze_seconds':10,'impact_tick':32,'expiry_tick':332},'required_consumer_passed':error is None and all(m['hp']==9500 and 23 in m['flags'] for m in members.values()),'dynamic_actual_area_descendant_authorization_required':True,'whole_stage_executed':False,'client_verified':False}
    dest=OUT.parent/'retained_v16'/'required.death_aoe.actual.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((json.dumps(thaw(report),ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    assert error is None,'Retained source AoE payload context rejected actual descendant targets: '+str(error)
    assert not s.ctx.alive('slime') and s.ctx.resources.current('slime','hp')==0
    assert all(m['hp']==9500 and 23 in m['flags'] for m in members.values()),'Each actual native-qualified area member requires physical500 and Cold10'

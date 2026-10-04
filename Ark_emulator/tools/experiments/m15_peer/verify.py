"""Independent EMP/retire slice witnesses; terrain/whole-device approval absent."""
import argparse
from collections import Counter
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[3]
CANDIDATE=ROOT.parent/'unpack_work/campaign_m15_device_candidate'
CORE='177edecfbac20278c7209babd75c159a5a2e9d4b5ce0e31c1137d726c3c7c33e'
PACKAGE=ROOT/'packages/campaign/chapter01_devices/emp.partial.json'
SOURCE=ROOT/'packages/campaign/chapter01_devices/emp.source.json'
PIN='98f668b2f130a4e47e27151d92cbf3d1ad59789e147ec4adc80a98a14679e854'
DUMP=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs'
LAST=None


def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def retire(reason='dead',target='source'):return {'op':'retire','target':target,'parameters':{'reason':reason}}
def component(source,kind):return next(c['raw'] for c in source['components'].values() if c['native_class']==kind)


def source_contract():
    n,p=read(SOURCE),read(PACKAGE);text=DUMP.read_text(encoding='utf8')
    for name,value in [('INVINCIBLE',5),('STUNNED',0),('ON_CAST_END',3),('BEFORE_SPELL_START',1),('FROM_OWNER',1),('TRAP_OR_ITEM',2),('ALLY',1)]:
        assert re.search(r'public const [\w.]+ '+name+r' = '+str(value)+r';',text)
    m=component(n['skill_prefab'],'MeleeAttack');s=component(n['skill_prefab'],'AdvancedSelector');a=component(n['skill_prefab'],'ActionToOwner')
    assert m['_selector']=={'m_FileID':0,'m_PathID':int(next(k for k,c in n['skill_prefab']['components'].items() if c['native_class']=='AdvancedSelector'))}
    assert (m['_selectTargetSource'],m['_selectTargetTiming'],m['_preDelay'],m['_cooldown'],m['_damageType'],m['_atkScale'])==(1,1,.75,1.5,2,1)
    assert s['_targetSide']==2 and s['_targetMotion']==1 and s['_targetCategory']==1 and s['_limitTargetNum']==0
    assert a['_runActionOnEvent']==3 and a['_onlyRunOnce']==1
    nodes=json.loads(a['_actions']['SerializedState']);assert len(nodes)==1 and all(nodes[0][k] for k in ('_withdrawSource','_switchToDeadState','_force'))
    assert m['_activeBuffs'][0]['attributes']['abnormalFlags']==[0] and m['_activeBuffs'][0]['durationKey']=='stun'
    phase=n['character']['phases'][0];low,high=phase['attributesKeyFrames'];factor=Fraction(10-low['level'],high['level']-low['level'])
    stats={k:float(Fraction(str(low['data'][k]))+(Fraction(str(high['data'][k]))-Fraction(str(low['data'][k])))*factor) for k in ('maxHp','atk','cost','blockCnt')}
    assert stats=={'maxHp':100,'atk':1000,'cost':5,'blockCnt':0}
    assert n['level_config']['alias'] is None and n['level_config']['direction']=='UP' and n['native_position']=={'row':2,'col':5} and n['V2_position']=={'row':5,'col':5}
    grids=n['range_table']['range']['grids'];assert {(g['row'],g['col']) for g in grids}=={(r,c) for r in (-1,0,1) for c in (-1,0,1)}
    assert sha(Path(n['range_table']['path']))==n['range_table']['sha256']
    for source in (n['prefab']['source'],n['skill_prefab']['source']):assert sha(ROOT.parent/source['path'])==source['sha256']
    assert p['manifest']['metadata']['model_gaps'] and not p['manifest']['metadata']['formal_approval']
    return {'actual_enum_dump_sha256':sha(DUMP),'native_stats':stats,'raw_fields':{'packet_delay':.75,'cast_model_end':1.5,'before_spell_reselect':1,'ON_CAST_END':3,'INVINCIBLE':5,'STUNNED':0,'target_category':1},'ground_category_filter_pending':True,'terrain_overlay_pending':True}


def scene(dp=50,sp=None):
    p=read(PACKAGE);p['scenarioDraft']['initialEntities'][0]['instanceAlias']='device'
    if sp is not None:p['scenarioDraft']['initialEntities'][0]['components']={'resources':{'sp':{'initial':sp}}}
    p['scenarioDraft']['resources']['dp']['initial']=dp
    p['entities'].append({'id':'unit/peer_enemy','kind':'entity','tags':['enemy','ground'],'components':{
        'attributes':{'base':{'max_hp':3000,'atk':1000,'def':0,'mres':20}},'spatial':{},'resources':{'hp':{'initial':3000,'capacity':3000,'role':'health'}},
        'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/peer_enter','ability/peer_exit']+['ability/peer_hit_'+k for k in ('physical','arts','true')]}})
    p['selectors']+=[{'id':'selector/peer_device','kind':'selector','region':{'type':'all'},'filters':[{'tag':'device'},{'state':'alive'}],'limit':1}]
    for name,pos in [('enter',{'row':4,'col':5}),('exit',{'row':5,'col':7})]:
        p['abilities'].append({'id':'ability/peer_'+name,'kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':pos}}]})
    for kind in ('physical','arts','true'):p['abilities'].append({'id':'ability/peer_hit_'+kind,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer_device','timeline':[{'at':0,'effect':{'op':'damage','damage_type':kind}}]})
    for alias,row,col in [('leave',5,6),('enter',5,7),('diagonal',4,4)]:p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer_enemy','instanceAlias':alias,'position':{'row':row,'col':col}})
    return p


def make(data):
    global LAST
    from ark_sim import Compiler,Engine
    LAST=Engine.create(Compiler().compile(data),seed=1517);return LAST


def command(s,source,ability,at):s.submit({'action':'skill','source':source,'ability':ability},at=at)
def finish(s,expected,roundtrip=True):
    from ark_sim import Engine
    from ark_sim.contracts import thaw
    from ark_sim.tools.replay import replay
    if roundtrip:
        cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
    return {'expected':expected,'checkpoint_equal':True if roundtrip else 'API-only','replay_equal':True if roundtrip else 'API-only',
        'program_fingerprint':s.program.fingerprint,'runtime_fingerprint':s.runtime_fingerprint,'fixture_initial_state':thaw(s.program.scenario),'commands':s.export_replay(),
        'state':s.ctx.state(),'events':[thaw(e) for e in s.session.events if e['type'] in ('damage.accepted','damage.rejected','entity.died','entity.retired','entity.withdrawn','ability.finished','ability.interrupted','combat.kill','command.accepted','command.rejected','buff.applied','buff.removed','resource.changed')]}


def packet_reselect_and_half_open():
    s=make(scene());command(s,'device','ability/chapter01_emp/burst',150)
    command(s,'leave','ability/peer_exit',170);command(s,'enter','ability/peer_enter',171);s.advance(173)
    assert not [e for e in s.session.events if e['type']=='damage.accepted'];s.advance(1)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==2 and {e['payload']['target'] for e in hits}=={s.session.world.resolve(a) for a in ('enter','diagonal')}
    assert all(e['time']==173 and abs(e['payload']['amount']-800)<1e-8 for e in hits)
    assert s.ctx.resources.current('leave','hp')==3000 and s.ctx.resources.current('enter','hp')==2200
    assert s.ctx.resources.current('system/battle','dp')==40 and s.ctx.resources.current('device','sp')==0
    s.advance(22);assert not s.ctx.alive('device') and s.ctx.resources.current('device','hp')==100
    ended=[e for e in s.session.events if e['type']=='ability.finished' and e['payload']['source']==s.session.world.resolve('device')]
    died=[e for e in s.session.events if e['type']=='entity.died'];assert len(ended)==len(died)==1 and ended[0]['time']==died[0]['time']==195 and ended[0]['id']<died[0]['id']
    assert s.ctx.state()['kills']==0 and not [e for e in s.session.events if e['type']=='combat.kill']
    s.advance(186);assert s.ctx.buffs.controls('enter')['move'] is False
    s.advance(1);assert s.ctx.buffs.controls('enter')['move'] is True
    return finish(s,{'packet173_reselect_enter_and_diagonal_800_each':True,'cast_end195_then_self_retire_HP100_noCombatKill':True,'stun_expires383':True})


def incoming_and_failed_payments():
    reports=[]
    for kind in ('physical','arts','true'):
        s=make(scene());command(s,'leave','ability/peer_hit_'+kind,0);s.advance(1)
        assert s.ctx.resources.current('device','hp')==100 and len([e for e in s.session.events if e['type']=='damage.rejected'])==1
        reports.append(finish(s,{'channel':kind,'actual_target_hook_rejects_HP_damage':True}))
    for when,dp in [(0,50),(150,9)]:
        s=make(scene(dp));command(s,'device','ability/chapter01_emp/burst',when);s.advance(when+1)
        assert s.ctx.resources.current('system/battle','dp')==dp and s.ctx.resources.current('device','sp')==(0 if when==0 else 5)
        assert s.ctx.alive('device') and len([e for e in s.session.events if e['type']=='command.rejected'])==1
        reports.append(finish(s,{'SP_or_DP_failure_atomic':True,'when':when,'DP':dp}))
    return reports


def retirement_before_packet_cleans_jobs():
    s=make(scene());command(s,'device','ability/chapter01_emp/burst',150);s.submit({'action':'withdraw','source':'device'},at=160);s.advance(220)
    uid=s.session.world.resolve('device');assert not s.ctx.alive(uid) and s.ctx.resources.current(uid,'hp')==100
    assert not [e for e in s.session.events if e['type'] in ('damage.accepted','ability.finished','entity.died')]
    assert len([e for e in s.session.events if e['type']=='ability.interrupted'])==1
    assert not [t for t in s.session.scheduler.pending if t['kind'].startswith('domain.ability') and t['payload'].get('source')==uid]
    return finish(s,{'withdraw160_cancels_packet173_and_finish195':True,'HP100_not_death_callback':True})


def generic_data():
    p=scene(sp=5);p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1]
    p['entities'].append({'id':'unit/no_policy','kind':'entity','tags':['enemy','ground'],'components':{'attributes':{'base':{'max_hp':80}},'spatial':{},'resources':{'hp':{'initial':80,'capacity':80,'role':'health'}}}})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/no_policy','instanceAlias':'plain','position':{'row':0,'col':0}})
    p['selectors'].append({'id':'selector/plain','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
    return p


def generic_idempotent_no_policy_enemy_dead():
    p=generic_data();p['entities'][0]['components']['abilities'].append('ability/peer_retire')
    p['abilities'].append({'id':'ability/peer_retire','kind':'ability','activation':{'mode':'manual'},'selector':'selector/plain','timeline':[{'at':0,'effect':retire(target='selected')}],'parameters':{'x':0}})
    s=make(p);command(s,'device','ability/peer_retire',0);command(s,'device','ability/peer_retire',2);s.advance(3)
    assert not s.ctx.alive('plain') and s.ctx.resources.current('plain','hp')==80 and s.ctx.state()['kills']==1
    assert len([e for e in s.session.events if e['type']=='entity.died'])==1 and not [e for e in s.session.events if e['type']=='combat.kill']
    return finish(s,{'no_lifecycle_policy_still_retires':True,'enemy_reason_dead_counts_once_preservesHP80_noCombatKill':True})


def failure_after_retire_atomic():
    s=make(generic_data());before=s.checkpoint()
    try:s.ctx.effects.execute('device',['plain'],{'op':'retire','parameters':{'reason':'dead'},'effects':[{'op':'modify_resource','resource':'missing','delta':1}]})
    except ValueError:pass
    else:raise AssertionError('missing resource did not fail')
    assert before==s.checkpoint() and s.ctx.alive('plain') and s.ctx.state()['kills']==0
    return finish(s,{'lifecycle_retire_killcount_tasks_events_roll_back_with_child_failure':True},False)


def reserved_battle_and_control_context():
    from ark_sim import Compiler
    cases=[]
    for target in ('battle','system/battle'):
        p=generic_data();p['abilities'][0]['events'][0]['effects'][0]['target']=target
        try:Compiler().compile(p)
        except ValueError as e:cases.append({'target':target,'error':str(e)})
        else:raise AssertionError('reserved battle compiled')
    s=make(generic_data());cp=s.checkpoint()
    try:s.ctx.effects.execute('device',['system/battle'],retire(target=1))
    except ValueError:pass
    else:raise AssertionError('numeric battle ID retired')
    assert cp==s.checkpoint()
    return {'compile_rejections':cases,'runtime_numeric_battle_rejected_atomically':True,'API_only':True}


CASES={'source_contract':source_contract,'packet_reselect_halfopen':packet_reselect_and_half_open,'incoming_payments':incoming_and_failed_payments,
    'owner_retired_jobs':retirement_before_packet_cleans_jobs,'generic_retire_idempotent_no_policy':generic_idempotent_no_policy_enemy_dead,
    'generic_retire_failure_atomic':failure_after_retire_atomic,'reserved_battle':reserved_battle_and_control_context}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/m15_emp_retire_peer_initial.json');args=parser.parse_args()
    sys.path.insert(0,str(CANDIDATE));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    assert Path(ark_sim.__file__).resolve().parent==CANDIDATE/'ark_sim' and implementation_digest()==CORE and sha(PACKAGE)==PIN
    files=[Path(__file__),PACKAGE,SOURCE,DUMP];before={str(p):sha(p) for p in files};cases=[]
    for name,fn in CASES.items():
        try:cases.append({'case':name,'result':'passed','actual':fn()})
        except Exception as error:
            cases.append({'case':name,'result':'failed','error':repr(error),'failure_context':{'checkpoint':LAST.checkpoint(),'fixture_initial':thaw(LAST.program.scenario)} if LAST else None})
    end={str(p):sha(p) for p in files};stable=before==end and implementation_digest()==CORE;passed=stable and all(c['result']=='passed' for c in cases)
    value={'schema':'ark-sim/bounded-device-peer-review/v1','passed':passed,'implementation_sha256':CORE,'input_package_sha256':PIN,'runtime_module':ark_sim.__file__,
        'source_at_start':before,'source_at_completion':end,'identity_stable':stable,'cases':cases,
        'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(Path(__file__)),'result':'passed' if passed else 'failed'}],
        'scope':'EMPskill/generic retirement slice only; terrain overlay/category/native callbacks unapproved','formal_approval':False,'review_receipt':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':passed,'cases':[(c['case'],c['result'],c.get('error')) for c in cases]}));return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())

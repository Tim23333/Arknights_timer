"""Fresh independent V3 elemental boundary fixtures; no author/root fixture imports."""
import sys, json, hashlib, traceback, copy, subprocess, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=(ROOT/'../unpack_work/campaign_c9_foundation_v5_candidate').resolve()
sys.path.insert(0,str(CAND))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import Simulation, implementation_digest
from ark_sim.domains.elemental import validate,validate_effect
from ark_sim.contracts import digest
EXPECTED='5f16643b454380bf188df055cd7225fb2a1f9118314fd15f274aff943f8ae353'
OUT=ROOT/'validation/campaign/chapter09_cache_atomic_v5'
LOG=Path('E:/ArkSimLogs/runs/chapter09_cache_atomic_v5')
LOG.mkdir(parents=True,exist_ok=True)
RESULTS=[]
ARTIFACTS=[]
CLEANUPS=[]

def rule(contract,expr):
    return {'id':'peer/'+contract,'kind':'calculation_rule','contract':contract,'implementation':{'type':'expression','expression':expr}}
def data():
    rules=[rule('elemental.capacity','inputs.parameters.capacity'),rule('elemental.loss','inputs.request.raw_amount'),rule('elemental.recovery','min(inputs.capacity, inputs.current + inputs.delta_seconds * inputs.parameters.recovery_rate)'),rule('elemental.break_duration','inputs.parameters.break_duration_seconds'),rule('elemental.eligibility','True'),rule('elemental.packet','7')]
    elements={k:{'capacity':cap,'resistance':0,'recovery_rate':0,'break_duration_seconds':.1,'rules':{c:'peer/'+c for c in ('elemental.capacity','elemental.loss','elemental.recovery','elemental.break_duration')}} for k,cap in [('alpha',19),('beta',31)]}
    comp={'attributes':{'base':{'atk':13,'def':0,'magic_resistance':0,'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{}}
    target=copy.deepcopy(comp); target['elemental']={'eligibility_rule':'peer/elemental.eligibility','elements':elements}
    return {'schemaVersion':2,'rules':rules,'entities':[{'id':'peer/source','kind':'entity','tags':['player'],'components':comp},{'id':'peer/owner','kind':'entity','tags':['enemy'],'components':target}], 'scenarioDraft':{'id':'peer/scenario','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},'initialEntities':[{'definition':'peer/source','instanceAlias':'src','position':{'row':0,'col':0}},{'definition':'peer/owner','instanceAlias':'dst','position':{'row':0,'col':3}}]}}
def sim(d=None):return Engine.create(Compiler().compile(d or data()),seed=517)
def refs(s):return s.session.world.resolve('src'),s.session.world.resolve('dst')
def state(s):return s.ctx.get(refs(s)[1],('runtime','elemental'))
def ep(s,k='alpha',amount=1,**kw):
    a,b=refs(s);return s.ctx.elemental.apply(a,b,{'op':'elemental_damage','element':k,'amount':amount},**kw)
def change(s,path,value):s.ctx.set(refs(s)[1],path,value)
def checkpoint(s):return s.checkpoint()
def test(name,fn):
    try:fn();RESULTS.append({'case':name,'passed':True})
    except Exception as e:RESULTS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    finally:
        if any(LOG.glob('*.json')):cleanup()
def cleanup():
    completed=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs_v2.py'),'--apply','--run-dir',str(LOG),'--minimum-age-minutes','0','--completed-pid',str(os.getpid())],check=True,capture_output=True,text=True,encoding='utf8')
    CLEANUPS.append(json.loads(completed.stdout.strip()))

def double_threshold():
    for first,second in [('alpha','beta'),('beta','alpha')]:
        s=sim();caps={'alpha':19,'beta':31};ep(s,first,caps[first]-1);assert state(s)['remaining'][first]==1
        assert ep(s,first,1)['break'];before=checkpoint(s);assert ep(s,second,caps[second])['reason']=='break_locked';assert checkpoint(s)==before
        assert state(s)['break']['element']==first
        change(s,('elemental','elements','alpha','capacity'),7);change(s,('elemental','elements','beta','capacity'),43)
        s.session.advance(4);assert state(s)['break'] is None and state(s)['remaining']=={'alpha':7,'beta':43}
def noop():
    s=sim();before=checkpoint(s);ep(s,amount=0);assert checkpoint(s)==before
    ep(s,amount=19);before=checkpoint(s)
    for k in ('alpha','beta'):
        ep(s,k,1);assert checkpoint(s)==before
def dirty():
    s=sim();ep(s,amount=1);change(s,('elemental','elements','alpha','capacity'),7);ep(s,'beta',1);assert state(s)['remaining']=={'alpha':7,'beta':30}
def replace_rules():
    d=data();expr={'elemental.capacity':'inputs.parameters.capacity * 2','elemental.loss':'inputs.request.raw_amount * 3','elemental.recovery':'min(inputs.capacity, inputs.current + 5)','elemental.break_duration':'0.2','elemental.packet':'7'}
    for r in d['rules']:
        if r['contract'] in expr:r['implementation']['expression']=expr[r['contract']]
    d['scenarioDraft']['scheduledEffects']=[{'at':10000,'effect':{'op':'elemental_damage','target':2,'element':'alpha','amount_rule':'peer/elemental.packet'}}]
    s=sim(d);assert state(s)['remaining']=={'alpha':38,'beta':62};ep(s,amount=2);assert state(s)['remaining']['alpha']==32;s.session.advance(2);assert state(s)['remaining']['alpha']==37
    a,b=refs(s);s.ctx.elemental.apply(a,b,{'op':'elemental_damage','element':'alpha','amount_rule':'peer/elemental.packet'});assert state(s)['remaining']['alpha']==16
    ep(s,amount=6);assert state(s)['break']['due']==8
    d=data();next(r for r in d['rules'] if r['contract']=='elemental.eligibility')['implementation']['expression']='False';s=sim(d);before=checkpoint(s);assert ep(s)['reason']=='eligibility';after=checkpoint(s)
    for k in ('world','scheduler','random'):assert before['kernel'][k]==after['kernel'][k]
def expiry_forge():
    s=sim();ep(s,amount=19);before=checkpoint(s);s.ctx.elemental.expire(s.session,{'target':refs(s)[1],'generation':state(s)['generation']});assert checkpoint(s)==before
    lease=state(s)['break'];s.session.schedule('domain.elemental.expire',{'target':refs(s)[1],'generation':lease['generation']},0,phase=lease['phase']);s.session.advance(1);assert state(s)['break'] is not None
def death_retire():
    for reason in ('retired','dead'):
        s=sim();ep(s,amount=19);a,b=refs(s);s.ctx.lifecycle.retire(b,reason);assert state(s)['break'] is None
        s.session.advance(6);assert not [e for e in s.session.events if e['type']=='elemental.break.ended']
        new=s.ctx.lifecycle.create('peer/owner',{'row':0,'col':3},alias='new');assert s.ctx.get(new,('runtime','elemental'))['remaining']=={'alpha':19,'beta':31}
def generation():
    s=sim();ep(s,amount=19);change(s,('runtime','lifecycle_generation'),1);s.session.advance(1);assert state(s)['break'] is None
    s.session.advance(6);assert not [e for e in s.session.events if e['type']=='elemental.break.ended']
def callback_fault():
    d=data();p=d['entities'][1]['components']['elemental']['elements']['alpha'];p['on_break']=[{'op':'random','stream':'peer_fault','probability':1,'on_success':[{'op':'modify_resource','resource':'hp','amount':-3}]},{'op':'elemental_damage','element':'undeclared','amount':1}]
    s=sim(d);before=checkpoint(s)
    try:ep(s,amount=19)
    except ValueError:pass
    else:raise AssertionError('late callback fault absent')
    assert checkpoint(s)==before
def cp_head():
    s=sim();ep(s,'beta',4);ep(s,amount=19);cp=checkpoint(s);path=LOG/'peer.checkpoint.json';path.write_text(json.dumps(cp),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_text()))
    s.session.advance(9);r.session.advance(9);assert checkpoint(s)==checkpoint(r)
    ARTIFACTS.append({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'checkpoint_equal':True,'head_sha256':digest(checkpoint(s))})
    return
def invalid():
    for value in (True,False,'1',None,float('inf'),float('-inf'),float('nan'),-1):
        s=sim();before=checkpoint(s)
        try:ep(s,amount=value)
        except (ValueError,TypeError):pass
        else:raise AssertionError('invalid amount accepted '+repr(value))
        assert checkpoint(s)==before
    for target in (True,0,-1,1.2,'src'):
        try:validate_effect({'op':'elemental_damage','element':'alpha','amount':1,'target':target})
        except ValueError:pass
        else:raise AssertionError('invalid target accepted')

def projectile_data(policy='retain',lethal=False):
    d=data()
    for contract,provider in [('projectile.trajectory','model.projectile.trajectory'),('projectile.collision','model.projectile.collision')]:
        r=rule(contract,'0');r['implementation']={'type':'provider','provider':provider};d['rules'].append(r)
    d['projectiles']=[{'id':'peer/bolt','kind':'projectile','motion':{'rule':'peer/projectile.trajectory','parameters':{'mode':'homing','speed':30}},'collision':{'rule':'peer/projectile.collision','parameters':{'enabled':False}},'lifetime_seconds':1,'max_hits':1,'stop_after_max':True,'stop_after_first':True,'can_hit_same_target':False,'attach_at_launch':False,'lifecycle':{'source_invalid':policy,'source_hidden':'retain','target_invalid':'cancel','target_hidden':'cancel','finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':False,'hit_on_expire':False}}]
    packet={'op':'elemental_attack','health_effect':{'op':'damage','damage_type':'true','scale':150/13 if lethal else 1,'projectile_definition':'peer/bolt'},'element_effect':{'op':'elemental_damage','element':'alpha','amount':4}}
    d['abilities']=[{'id':'peer/fire','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':packet}]}]
    d['entities'][0]['components']['abilities']=['peer/fire'];d['entities'][1]['components']['lifecycle']={'policy':'policy/ark_lifecycle'}
    return d,packet
def projectile_real():
    for policy in ('retain','cancel'):
        d,packet=projectile_data(policy);s=sim(d);a,b=refs(s);s.ctx.effects.execute(a,[b],packet)
        assert state(s)['remaining']['alpha']==19 and s.ctx.resources.current(b,'hp')==100
        s.ctx.lifecycle.retire(a,'retired');before=checkpoint(s)
        fake={'projectile_impact':True,'launch_snapshot':s.ctx.capture_view(a)}
        assert s.ctx.elemental.apply(a,b,packet['element_effect'],cast=fake)['reason']=='source_invalid';assert checkpoint(s)==before
        cp=checkpoint(s);r=Engine.restore(s.program,cp);s.session.advance(5);r.session.advance(5);assert checkpoint(s)==checkpoint(r)
        assert state(s)['remaining']['alpha']==(15 if policy=='retain' else 19)
        assert s.ctx.resources.current(b,'hp')==(87 if policy=='retain' else 100)
        if policy=='retain':
            types=[e['type'] for e in s.session.events];assert types.index('damage.accepted')<types.index('elemental.loss.accepted')
    d,packet=projectile_data(lethal=True);s=sim(d);a,b=refs(s);s.ctx.effects.execute(a,[b],packet);s.session.advance(5)
    assert not s.ctx.active(b) and state(s)['remaining']['alpha']==19
def rebirth():
    d=data();c=d['entities'][1]['components'];c['lifecycle']={'policy':'policy/ark_lifecycle'};c['rebirth']={'resource':'hp','max_count':1,'delay_seconds':.2,'restore_ratio':1,'restore_rule':'peer/restore'}
    rr=rule('resource.recovery','inputs.parameters.capacity * inputs.parameters.ratio');rr['id']='peer/restore';d['rules'].append(rr)
    s=sim(d);ep(s,amount=19);a,b=refs(s);s.ctx.effects.execute(a,[b],{'op':'damage','damage_type':'true','scale':150/13});assert not s.ctx.active(b)
    s.session.advance(8);assert s.ctx.active(b) and state(s)['break'] is None
    assert not [e for e in s.session.events if e['type']=='elemental.break.ended'];assert ep(s,'beta',1)['accepted']
def invalid_profiles_rules():
    for key in ('capacity','break_duration_seconds'):
        for value in (0,-1,True,float('nan'),float('inf')):
            p=data()['entities'][1]['components']['elemental'];p['elements']['alpha'][key]=value
            try:validate(p)
            except (ValueError,TypeError):pass
            else:raise AssertionError('invalid profile accepted')
    for contract,expr in [('elemental.loss','-1'),('elemental.loss','1e309'),('elemental.eligibility','1'),('elemental.break_duration','0')]:
        d=data();next(r for r in d['rules'] if r['contract']==contract)['implementation']['expression']=expr;s=sim(d);before=checkpoint(s)
        try:ep(s,amount=19)
        except (ValueError,TypeError):pass
        else:raise AssertionError('invalid calculation accepted '+contract+' '+expr)
        assert checkpoint(s)==before

def joint_data(hp=2200,res=55,ignore_sp=False):
    d=data();t=d['entities'][1]['components'];t['attributes']['base'].update(max_hp=hp,magic_resistance=res);t['resources']['hp'].update(initial=hp,capacity=hp);t['lifecycle']={'policy':'policy/ark_lifecycle'}
    t['resources']['sp']={'initial':0,'capacity':20,'recovery_rule':'peer/sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}
    d['rules'].append({'id':'peer/sp','kind':'calculation_rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}})
    d['rules'].append({'id':'peer/fire_pipeline','kind':'calculation_rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'settle','expression':"{'accepted': True, 'amount': inputs.effect.fixed_amount * (1 - inputs.effect.resistance / 100), 'allocations': [], 'events': []}"}],'output':'nodes.settle'},'metadata':{'input_bindings':{'resistance':{'entity':'target','attribute':'magic_resistance'}}}})
    d['buffs']=[{'id':'peer/res_penalty','kind':'buff','modifiers':[{'attribute':'magic_resistance','layer':'flat','value':-13}]}]
    packet={'op':'no_source_damage','fixed_amount':875,'damage_type':'arts','attack_type':'NORMAL','damage_without_modify':False,'ignore_for_sp':ignore_sp,'node_is_env_damage':False,'env_blackboard_injected':False,'environmental':False,'origin':{'fixture':'fresh_joint_fire'},'rules':{'damage.pipeline':'peer/fire_pipeline'}}
    p=t['elemental']['elements']['alpha'];p['on_break']=[{'op':'apply_buff','buff':'peer/res_penalty'},packet];p['on_end']=[{'op':'remove_buff','buff':'peer/res_penalty'}]
    return d,packet
def joint_fire():
    failures=[]
    for hp,res,ignore in [(2200,55,False),(1800,17,True)]:
        d,packet=joint_data(hp,res,ignore);s=sim(d);a,b=refs(s);ep(s,'beta',9);ep(s,amount=19)
        expected=875*(1-(res-13)/100);assert abs(s.ctx.resources.current(b,'hp')-(hp-expected))<1e-9
        accepted=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(accepted)==1;tag=accepted[0]['payload'];assert tag['source'] is None and tag['source_policy']=='none' and tag['attack_type']=='NORMAL'
        origin=tag['origin']['elemental_break'];assert origin['owner']==b and origin['generation']==state(s)['generation'];assert origin['provenance']['source']==a
        assert s.ctx.attributes.value(b,'magic_resistance')==res-13;before=checkpoint(s);assert ep(s,'beta',31)['reason']=='break_locked';assert checkpoint(s)==before
        LOG.mkdir(parents=True,exist_ok=True);path=LOG/('fresh_fire_'+str(res)+'.checkpoint.json');path.write_text(json.dumps(checkpoint(s)),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_bytes()))
        s.session.advance(5);r.session.advance(5)
        cpp_equal=checkpoint(s)==checkpoint(r);forward_head=digest(checkpoint(s));restored_head=digest(checkpoint(r))
        if not cpp_equal:
            from ark_sim.tools.compare import first_difference
            counter={'core':implementation_digest(),'fresh_fixture_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'difference':first_difference(checkpoint(s),checkpoint(r)),'trigger':'after FIRE callback and before checkpoint, call ctx.attributes.value(target, magic_resistance)','observed_res':res-13,'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'forward_head_sha256':digest(checkpoint(s)),'restored_head_sha256':digest(checkpoint(r)),'hp_forward':s.ctx.resources.current(b,'hp'),'hp_restored':r.ctx.resources.current(b,'hp'),'sp_forward':s.ctx.resources.current(b,'sp'),'sp_restored':r.ctx.resources.current(b,'sp')}
            OUT.mkdir(parents=True,exist_ok=True);(OUT/('counter.res_'+str(res)+'_read_before_cp.v2.json')).write_text(json.dumps(counter,ensure_ascii=False,indent=2),encoding='utf8')
            ARTIFACTS.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'checkpoint_equal':False,'forward_head_sha256':digest(checkpoint(s)),'restored_head_sha256':digest(checkpoint(r))})
            failures.append(counter['difference'])
        assert s.ctx.attributes.value(b,'magic_resistance')==res and state(s)['remaining']=={'alpha':19,'beta':31}
        assert s.ctx.resources.current(b,'sp')==(0 if ignore else 1)
        types=[e['type'] for e in s.session.events];assert types.index('elemental.break.started')<types.index('buff.applied')<types.index('damage.accepted')<types.index('elemental.break.ended')
        if cpp_equal:ARTIFACTS.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'head_sha256':forward_head,'restored_head_sha256':restored_head,'checkpoint_equal':True})
        cleanup()
    assert not failures,'actual CPP/head mismatches '+str(failures)
def lethal_fire():
    d,packet=joint_data(hp=100,res=21);d['entities'][1]['components']['elemental']['elements']['alpha']['on_break'].append({'op':'emit','event':'peer.after_lethal'})
    s=sim(d);ep(s,amount=19);a,b=refs(s);assert not s.ctx.active(b) and state(s)['break'] is None
    s.session.advance(6);types=[e['type'] for e in s.session.events];assert 'elemental.break.cancelled' in types and 'elemental.break.ended' not in types and 'peer.after_lethal' not in types
def joint_fault():
    d,packet=joint_data();p=d['entities'][1]['components']['elemental']['elements']['alpha'];p['on_break'] += [{'op':'random','stream':'fresh_joint_fault','probability':1,'on_success':[{'op':'modify_resource','resource':'sp','amount':2}]},{'op':'elemental_damage','element':'not_declared','amount':1}]
    s=sim(d);before=checkpoint(s)
    try:ep(s,amount=19)
    except ValueError:pass
    else:raise AssertionError('joint late callback did not fault')
    assert checkpoint(s)==before
def no_source_protocol():
    from ark_sim.domains.no_source_damage import validate_request
    d,packet=joint_data();s=sim(d);a,b=refs(s)
    for field,value in [('damage_type',True),('attack_type',1),('fixed_amount',True),('fixed_amount',float('inf'))]:
        e=copy.deepcopy(packet);e[field]=value
        try:validate_request(e)
        except ValueError:pass
        else:raise AssertionError('invalid no-source request accepted')
    for kw in ({'source':a},{'source':None,'cast':{'projectile_impact':True}},{'source':None,'ability':{'id':'fake'}}):
        before=checkpoint(s)
        try:s.ctx.effects.execute(kw.pop('source'),[b],packet,**kw)
        except ValueError:pass
        else:raise AssertionError('actor protocol state accepted')
        assert checkpoint(s)==before

def main():
    assert implementation_digest()==EXPECTED
    for name,fn in [('two_element_threshold_order_and_reset',double_threshold),('locked_and_zero_exact_noop',noop),('custom_capacity_dirty_sync',dirty),('replace_all_pure_rules',replace_rules),('forged_expiry_task',expiry_forge),('death_retire_recreate',death_retire),('owner_generation_change',generation),('late_callback_rng_tasks_world_events_rollback',callback_fault),('durable_checkpoint_head',cp_head),('strict_types_finite',invalid),('real_retained_cancel_compound_projectile_health_before_ep',projectile_real),('rebirth_cancels_lease_and_restores_qualification',rebirth),('invalid_profiles_and_calculation_results',invalid_profiles_rules)]:test(name,fn)
    for name,fn in [('fresh_joint_fire_res_order_sp_multi_lock_cpp_head',joint_fire),('fresh_joint_lethal_cancels_lease_and_callbacks',lethal_fire),('fresh_joint_late_fault_full_rollback',joint_fault),('joint_no_source_strict_protocol',no_source_protocol)]:test(name,fn)
    assert implementation_digest()==EXPECTED
    import ark_sim
    receipt={'candidate_core':implementation_digest(),'expected_core':EXPECTED,'candidate_import_path':str(Path(ark_sim.__file__).resolve()),'candidate_guard_before_after_equal':True,'fixture_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':RESULTS,'passed':all(r['passed'] for r in RESULTS),'actual_exit':0 if all(r['passed'] for r in RESULTS) else 1,'fixture_imports_author_or_root':False,'scope':'fresh independent mechanisms; no full-suite reuse','checkpoint_head_kind':'continued checkpoint equality; direct effect and attribute queries are not automatically recorded in exportReplay','public_replay_claim_for_low_level_queries':False,'artifacts':ARTIFACTS,'cleanup':CLEANUPS,'raw_payload_deleted':all(not Path(a['path']).exists() for a in ARTIFACTS)}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'report.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(receipt,ensure_ascii=False));return 0 if receipt['passed'] else 1
if __name__=='__main__':raise SystemExit(main())

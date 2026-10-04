import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def fixture():
    unit=lambda name,tags,buffs=[]:{'id':'unit/'+name,'kind':'entity','tags':tags,'components':{'spatial':{},'attributes':{'base':{'max_hp':100,'def':10}},'resources':{'hp':{'initial':100,'capacity':100}},'buffs':{'initial':buffs}}}
    p={'manifest':{'requires':['preset/ark_standard']},'entities':[unit('parent',['emitter'],['buff/parent']),unit('a',['member']),unit('b',['member'])],
       'buffs':[{'id':'buff/parent','kind':'buff','aura':{'selector':'selector/members','buff':'buff/child'}},
                {'id':'buff/child','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':5}]}],
       'selectors':[{'id':'selector/members','kind':'selector','region':{'type':'circle','radius':2},'filters':[{'tag':'member'},{'state':'alive'}]}],
       'abilities':[{'id':'ability/leave','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':0,'col':3}}]},'timeline':[]}],
       'scenarioDraft':{'id':'scene/peer/remove','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':4},
          'initialEntities':[{'definition':'unit/parent','instanceAlias':'parent','position':{'row':0,'col':0}},
                             {'definition':'unit/a','instanceAlias':'a','position':{'row':0,'col':1}},
                             {'definition':'unit/b','instanceAlias':'b','position':{'row':0,'col':2}}]}}
    p['entities'][1]['components']['abilities']=['ability/leave'];return p

def test_child_cleanup_callback_removes_parent_without_recreating_ghost_sibling():
    p=fixture();p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]
    p['entities'][1]['components']['attributes']['base']['atk']=100
    p['entities'][2]['tags'].append('victim')
    p['selectors'].append({'id':'selector/victim','kind':'selector','region':{'type':'all'},'filters':[{'tag':'victim'}]})
    p['abilities'][0]['selector']='selector/victim'
    p['abilities'][0]['activation']['on_start'].append({'op':'damage','damage_type':'physical'})
    s=Engine.create(Compiler().compile(p),seed=4242);assert len(s.ctx.get('b',('buffs','instances')))==1;s.submit({'action':'skill','source':'a','ability':'ability/leave'},at=0);s.advance(1)
    assert not s.ctx.alive('parent')
    assert s.ctx.resources.current('b','hp')==10
    assert s.ctx.get('a',('buffs','instances'))==[] and s.ctx.get('b',('buffs','instances'))==[]

def test_outer_remove_on_remove_installs_replacement_parent_without_stale_child():
    p=fixture();p['buffs'][0]['on_remove']=[{'op':'apply_buff','target':'source','buff':'buff/replacement'}]
    p['buffs'] += [{'id':'buff/replacement','kind':'buff','aura':{'selector':'selector/members','buff':'buff/newchild'}},
                    {'id':'buff/newchild','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':20}]}]
    p['entities'][0]['components']['abilities']=['ability/switch'];p['abilities'].append({'id':'ability/switch','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'remove_buff','target':'source','buff':'buff/parent'}]},'timeline':[]})
    program=Compiler().compile(p);s=Engine.create(program,seed=4244);s.submit({'action':'skill','source':'parent','ability':'ability/switch'},at=0);s.advance(1)
    for ref in ('a','b'):assert [i['definition'] for i in s.ctx.get(ref,('buffs','instances'))]==['buff/newchild']
    assert s.ctx.buffs._removal_depth==0 and not s.ctx.buffs._reconciling and s.snapshot()==replay(program,s.export_replay()).snapshot()

def hit_fixture():
    p=fixture();p['entities'][1]['components']['attributes']['base']['atk']=100;p['entities'][2]['tags'].append('victim')
    p['selectors'].append({'id':'selector/victim','kind':'selector','region':{'type':'all'},'filters':[{'tag':'victim'}]})
    p['abilities'][0]['selector']='selector/victim';p['abilities'][0]['activation']['on_start'].append({'op':'damage','damage_type':'physical'})
    return p

def test_same_definition_other_source_parent_is_preserved():
    p=hit_fixture();p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/parent','instanceAlias':'other','position':{'row':0,'col':1}})
    program=Compiler().compile(p);s=Engine.create(program,seed=4501);assert len(s.ctx.get('b',('buffs','instances')))==2
    s.submit({'action':'skill','source':'a','ability':'ability/leave'},at=0);s.advance(1)
    assert not s.ctx.alive('parent') and s.ctx.alive('other') and s.ctx.resources.current('b','hp')==15
    children=s.ctx.get('b',('buffs','instances'));assert len(children)==1 and children[0]['source']==s.session.world.resolve('other')
    assert s.snapshot()==replay(program,s.export_replay()).snapshot()

def test_remote_source_retire_does_not_require_center_to_retire(tmp_path):
    p=hit_fixture();p['entities'][0]['components']['buffs']={'initial':[]}
    p['entities'].append({'id':'unit/caster','kind':'entity','tags':['director'],'components':{'spatial':{},'abilities':['ability/parent_on']}})
    p['selectors'].append({'id':'selector/center','kind':'selector','region':{'type':'all'},'filters':[{'tag':'emitter'}]})
    p['abilities'].append({'id':'ability/parent_on','kind':'ability','selector':'selector/center','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/parent'}]},'timeline':[]})
    p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/caster','instanceAlias':'caster','position':{'row':0,'col':3}})
    program=Compiler().compile(p);s=Engine.create(program,seed=4502);s.submit({'action':'skill','source':'caster','ability':'ability/parent_on'},at=0)
    s.submit({'action':'skill','source':'a','ability':'ability/leave'},at=1);s.advance(1);assert len(s.ctx.get('b',('buffs','instances')))==1
    path=tmp_path/'remote.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(2);r.advance(2)
    assert s.ctx.alive('parent') and not s.ctx.alive('caster') and s.ctx.resources.current('b','hp')==10
    assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()

def test_child_callback_moves_center_and_recomputes_remaining_members_before_packet():
    p=hit_fixture();p['scenarioDraft']['map']['cols']=7;p['abilities'][0]['activation']['on_start'][0]['position']['col']=4
    p['buffs'][1]['on_remove']=[{'op':'move','target':'source','position':{'row':0,'col':6}}]
    program=Compiler().compile(p);s=Engine.create(program,seed=4503);s.submit({'action':'skill','source':'a','ability':'ability/leave'},at=0);s.advance(1)
    assert s.ctx.alive('parent') and s.ctx.get('parent',('spatial','position'))['col']==6
    assert s.ctx.resources.current('b','hp')==10 and s.ctx.get('b',('buffs','instances'))==[]
    assert len(s.ctx.get('a',('buffs','instances')))==1 and s.snapshot()==replay(program,s.export_replay()).snapshot()

def test_same_tick_expiry_callbacks_cannot_retain_sibling_or_repeat_retire():
    p=fixture();p['buffs'][0]['duration_seconds']=.1;p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]
    s=Engine.create(Compiler().compile(p),seed=4504);s.advance(4)
    assert not s.ctx.alive('parent') and s.ctx.get('b',('buffs','instances'))==[] and s.ctx.get('a',('buffs','instances'))==[]
    assert len([e for e in s.session.events if e['type']=='entity.withdraw'])==1
    assert s.ctx.buffs._removal_depth==0 and not s.ctx.buffs._reconciling and not s.ctx.buffs._reconcile_requested

def test_real_on_remove_rule_failure_after_retire_and_rng_rolls_every_partition_back():
    p=fixture();p['rules']=[{'id':'rule/failure','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1 / 0'}}]
    p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}},
        {'op':'random','stream':'imp','probability':1,'on_success':[{'op':'modify_resource','resource':'hp','delta':-1}]},
        {'op':'modify_resource','resource':'hp','amount_rule':'rule/failure'}]
    s=Engine.create(Compiler().compile(p),seed=4505);before=s.checkpoint()
    for _ in range(2):
        with pytest.raises(Exception):s.ctx.movement.displace('a','a',{'position':{'row':0,'col':3}},None)
        assert s.checkpoint()==before and s.ctx.buffs._removal_depth==0 and not s.ctx.buffs._reconciling and not s.ctx.buffs._reconcile_requested

def test_normal_random_aura_internal_child_install_does_not_resample():
    p=fixture();p['selectors'][0].update(ordering='random',limit=1,parameters={'random_stream':'imp'})
    s=Engine.create(Compiler().compile(p),seed=4506)
    draws=[e for e in s.session.events if e['type']=='random.sample']
    # During a single explicit reconciliation, internal installation creates
    # exactly one owned child and does not schedule a second random selection.
    before=s.session.random.snapshot();s.ctx.buffs.reconcile();after=s.session.random.snapshot()
    assert len(after['samples'])-len(before['samples'])==1
    assert sum(len(s.ctx.get(ref,('buffs','instances'))) for ref in ('a','b'))==1
    assert not s.ctx.buffs._reconcile_requested

def test_child_immediate_effect_retires_source_without_orphan_instance():
    p=fixture();p['buffs'][1]['effects']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]
    s=Engine.create(Compiler().compile(p),seed=4507)
    assert not s.ctx.alive('parent') and s.ctx.get('a',('buffs','instances'))==[] and s.ctx.get('b',('buffs','instances'))==[]
    assert len([e for e in s.session.events if e['type']=='entity.withdraw'])==1

def fail_after_center_moves(inputs,parameters,context):
    if inputs['source']['components']['spatial']['position']['col']>=6:raise RuntimeError('actual peer provider after movement failure')
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return BUILTIN_PROVIDERS['ark.selector.grid'](inputs,parameters,context)
fail_after_center_moves.version='independent_m45_fail_v1'

def test_second_pass_provider_failure_restores_world_rng_events_jobs_and_reentry_flags():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    p=fixture();p['scenarioDraft']['map']['cols']=7;p['selectors'][0]['provider']='peer.failed'
    p['buffs'][1]['on_remove']=[{'op':'random','stream':'imp','probability':1,'on_success':[{'op':'modify_resource','resource':'hp','delta':-1}]},
        {'op':'move','target':'source','position':{'row':0,'col':6}}]
    providers={**BUILTIN_PROVIDERS,'peer.failed':fail_after_center_moves};program=Compiler(providers=providers).compile(p);s=Engine.create(program,seed=4508,providers=providers);before=s.checkpoint()
    for _ in range(2):
        with pytest.raises(RuntimeError,match='actual peer provider'):s.ctx.movement.displace('a','a',{'position':{'row':0,'col':4}},None)
        assert s.checkpoint()==before and s.ctx.buffs._removal_depth==0 and not s.ctx.buffs._reconciling and not s.ctx.buffs._reconcile_requested

def alternating_members(inputs,parameters,context):
    candidates=sorted(inputs['candidates'],key=lambda row:row['id']);index=int(inputs['source']['components']['spatial']['position']['col'])%2
    return [candidates[index]['id']] if len(candidates)>index else []
alternating_members.version='independent_m45_bounded_callback_v1'

def test_nonconverging_real_callback_budget_rolls_back_without_double_children():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    p=fixture();p['scenarioDraft']['map']['cols']=10;p['entities'][0]['components']['buffs']={'initial':[]}
    p['entities'][0]['components']['abilities']=['ability/enable'];p['abilities'].append({'id':'ability/enable','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/parent'}]},'timeline':[]})
    p['selectors'][0]['provider']='peer.alternating';p['buffs'][1]['effects']=[{'op':'move','target':'source','offset':{'row':0,'col':1}}]
    providers={**BUILTIN_PROVIDERS,'peer.alternating':alternating_members}
    from ark_sim.contracts import thaw
    ruleset=thaw(Compiler().compile(fixture()).ruleset);ruleset.update(id='ruleset/budget',reaction_budget=2)
    program=Compiler(providers=providers).compile(p,ruleset=ruleset)
    s=Engine.create(program,seed=4509,providers=providers);before=s.checkpoint()
    with pytest.raises(ValueError,match='reconciliation budget'):s.ctx.effects.execute('parent',['parent'],{'op':'apply_buff','buff':'buff/parent'})
    assert s.checkpoint()==before and s.ctx.buffs._removal_depth==0 and not s.ctx.buffs._reconciling and not s.ctx.buffs._reconcile_requested

def test_public_samecast_exact_disk_restore_and_replay(tmp_path):
    p=hit_fixture();p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]
    program=Compiler().compile(p);s=Engine.create(program,seed=4510);s.submit({'action':'skill','source':'a','ability':'ability/leave'},at=3);s.advance(2)
    path=tmp_path/'samecast.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(4);r.advance(4)
    assert s.ctx.resources.current('b','hp')==10 and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()

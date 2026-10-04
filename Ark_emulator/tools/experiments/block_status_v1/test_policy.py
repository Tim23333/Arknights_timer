import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.selection import DEFAULT_STATE


def fixture():
    entity={'id':'unit/mover','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'move_speed':.5,'block_cost':1}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2}}}
    guard={'id':'unit/guard','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'block_count':3}},'abilities':['ability/free'],
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'deployable':{'cost':0,'terrain':1}}}
    buff={'id':'buff/free','kind':'buff','duration_seconds':.1,'active_rule':'rule/active',
        'selection_flags':{'abnormal_flags':[3]}}
    rules=[{'id':'rule/status','kind':'rule','contract':'blocking.eligibility','implementation':{'type':'provider','provider':'model.blocking.status'},
        'parameters':{'block_free_flag':3,'base_rule':'rule/ark_block_eligibility'},'dependencies':['rule/ark_block_eligibility']},
        {'id':'rule/active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'True'}}]
    ability={'id':'ability/free','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/free','target':2}}]}
    return {'definitions':[entity,guard,buff,ability,*rules],'scenarioDraft':{'id':'scene/status','ruleset':'ruleset/ark_standard',
        'objectives':{},'map':{'rows':1,'cols':4},'rules':{'blocking.eligibility':'rule/status'},
        'initialEntities':[{'definition':'unit/mover','instanceAlias':'mover','position':{'row':0,'col':0},
            'route':{'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}},
            {'definition':'unit/guard','instanceAlias':'guard','position':{'row':0,'col':1},'deployed':True}]}}


def test_dynamic_status_buff_removes_and_restores_real_blocking_relation_exact_expiry():
    s=Engine.create(Compiler().compile(fixture()),seed=511);s.advance(1)
    assert s.ctx.get('mover',('runtime','blocked_by'))==s.session.world.resolve('guard')
    s.ctx.buffs.apply('guard','mover','buff/free');assert s.ctx.get('mover',('runtime','blocked_by')) is None
    s.advance(3)
    assert s.ctx.get('mover',('runtime','blocked_by'))==s.session.world.resolve('guard')


def test_invalid_blockfree_flag_strict_bool_cannot_change_world():
    p=fixture();next(d for d in p['definitions'] if d['id']=='rule/status')['parameters']['block_free_flag']=True
    s=Engine.create(Compiler().compile(p),seed=511);before=s.checkpoint()
    with pytest.raises(ValueError,match='typed'):s.ctx.spatial.blocking()
    assert s.checkpoint()==before


def test_graph_can_wrap_status_provider_and_use_declared_custom_base():
    p=fixture();p['definitions'].append({'id':'rule/wrapper','kind':'rule','contract':'blocking.eligibility',
        'implementation':{'type':'graph','nodes':[{'id':'status','rule':'rule/status',
            'inputs':{k:'inputs.'+k for k in ('blocker','target','positions','paths','states')}}],'output':'nodes.status'}})
    p['scenarioDraft']['rules']['blocking.eligibility']='rule/wrapper'
    s=Engine.create(Compiler().compile(p),seed=511);s.advance(1)
    assert s.ctx.get('mover',('runtime','blocked_by'))==s.session.world.resolve('guard')
    s.ctx.buffs.apply('guard','mover','buff/free');assert s.ctx.get('mover',('runtime','blocked_by')) is None
    s.advance(3);assert s.ctx.get('mover',('runtime','blocked_by'))==s.session.world.resolve('guard')
    p=fixture();rule=next(d for d in p['definitions'] if d['id']=='rule/status')
    rule['parameters']['base_rule']='rule/reject';rule['dependencies']=['rule/reject']
    p['definitions'].append({'id':'rule/reject','kind':'rule','contract':'blocking.eligibility',
        'implementation':{'type':'graph','nodes':[{'id':'no','expression':"{'accepted':False,'reason':'custom_base'}"}],'output':'nodes.no'}})
    s=Engine.create(Compiler().compile(p),seed=511);s.advance(1)
    assert s.ctx.get('mover',('runtime','blocked_by')) is None

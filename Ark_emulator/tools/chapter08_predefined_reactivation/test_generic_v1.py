"""Bounded reactivation creates new actors and preserves oldsource identities."""
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def package():
    return {'schemaVersion':2,'manifest':{'id':'package/reuse/author','requires':['preset/ark_standard']},
        'entities':[{'id':'unit/device','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'},'sp':{'initial':0,'capacity':25}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}},
            {'id':'unit/director','kind':'entity','components':{'spatial':{},'abilities':['ability/activate','ability/retire']}}],
        'selectors':[{'id':'selector/device','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['definition_id'],'equals':'unit/device'}},{'state':'alive'}]}],
        'abilities':[{'id':'ability/activate','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'activate_predefined','target':'battle','parameters':{'key':'device1'}}]},'timeline':[]},
            {'id':'ability/retire','kind':'ability','selector':'selector/device','activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdrawn'}}]},'timeline':[]}],
        'scenarioDraft':{'id':'scene/reuse','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/device','active':False,'registration_key':'device1','reactivation':{'max_activations':2,'after_reasons':['withdrawn']},'position':{'row':0,'col':1}},
            {'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':0}}]}}

def test_actual_publicreuse_newHP_SP_actor_oldidentity_CP_head(tmp_path):
    p=package();s=Engine.create(Compiler().compile(p));old=s.ctx.state()['predefined_registry']['device1']
    for aid,t in [('activate',0),('retire',2),('activate',3),('retire',5),('activate',6)]:s.submit({'action':'skill','source':'director','ability':'ability/'+aid},at=t)
    s.advance(3);cp=tmp_path/'reuse3.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h));s.advance(5);r.advance(5);head=replay(s.program,s.export_replay())
    assert s.checkpoint()==r.checkpoint()==head.checkpoint() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    new=s.ctx.state()['predefined_registry']['device1'];assert old!=new and not s.ctx.active(old)
    assert s.ctx.resources.current(new,'hp')==100 and s.ctx.resources.current(new,'sp')==0
    assert s.ctx.state()['predefined_reactivation']['device1']['activations']==2
    assert [e['time'] for e in s.session.events if e['type']=='command.rejected']==[6]

def test_active_duplicate_activation_rejects_atomic_without_creating_extraactor():
    s=Engine.create(Compiler().compile(package()));s.ctx.lifecycle.activate_predefined('device1');before=s.checkpoint()
    with pytest.raises(ValueError,match='alreadyactive'):s.ctx.lifecycle.activate_predefined('device1')
    assert s.checkpoint()==before

@pytest.mark.parametrize('field,value',[('max_activations',True),('max_activations',0),('after_reasons',[]),('after_reasons',['alive'])])
def test_badprofiles_compile_reject(field,value):
    p=package();p['scenarioDraft']['initialEntities'][0]['reactivation'][field]=value
    with pytest.raises(ValueError):Compiler().compile(p)

def test_default_registration_still_singleuse():
    p=package();p['scenarioDraft']['initialEntities'][0].pop('reactivation');s=Engine.create(Compiler().compile(p));ref=s.ctx.lifecycle.activate_predefined('device1');s.ctx.lifecycle.retire(ref,'withdrawn');before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.lifecycle.activate_predefined('device1')
    assert s.checkpoint()==before

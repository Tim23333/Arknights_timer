from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def make():
    caster=lambda name:{'id':'unit/'+name,'kind':'entity','tags':['player'],'components':{'spatial':{},'resources':{'sp':{'initial':10,'capacity':10}},'abilities':['ability/hold']}}
    p={'manifest':{'requires':['preset/ark_standard']},'entities':[caster('a'),caster('b'),{'id':'unit/target','kind':'entity','tags':['target'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1000,'atk':10}}}}],
        'buffs':[{'id':'buff/shared','kind':'buff','duration_seconds':10,'stacking':{'mode':'refresh','identity':['definition','target']},'modifiers':[{'attribute':'atk','layer':'flat','value':3}]}],
        'selectors':[{'id':'selector/t','kind':'selector','region':{'type':'all'},'filters':[{'tag':'target'}],'limit':1}],
        'abilities':[{'id':'ability/hold','kind':'ability','selector':'selector/t','duration_seconds':5,'activation':{'mode':'manual','costs':[{'resource':'sp','amount':1}],
            'on_start':[{'op':'apply_buff','buff':'buff/shared','bind_to_cast':True}]},'timeline':[]}],
        'scenarioDraft':{'id':'scene/rootleases','ruleset':'ruleset/ark_standard','objectives':{},'resources':{'dp':{'initial':10,'capacity':10}},'map':{'rows':1,'cols':3},'initialEntities':[
            {'definition':'unit/a','instanceAlias':'a','position':{'row':0,'col':0}}, {'definition':'unit/b','instanceAlias':'b','position':{'row':0,'col':1}}, {'definition':'unit/target','instanceAlias':'t','position':{'row':0,'col':2}}]}}
    return Engine.create(Compiler().compile(p),seed=93007)


def test_cross_source_duplicate_lease_rolls_refresh_payment_and_entire_boundary():
    s=make();s.ctx.abilities.start('a','ability/hold');before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.abilities.start('b','ability/hold')
    assert s.checkpoint()==before
    instances=s.ctx.get('t',('buffs','instances'));assert len(instances)==1 and instances[0]['source']==s.session.world.resolve('a')


def test_after_actual_cancel_second_source_acquires_new_lease_public_cp_replay(tmp_path):
    s=make();s.submit({'action':'skill','source':'a','ability':'ability/hold'},at=0);s.submit({'action':'withdraw','source':'a'},at=1);s.submit({'action':'skill','source':'b','ability':'ability/hold'},at=2)
    s.session.advance(3);buffs=s.ctx.get('t',('buffs','instances'));assert len(buffs)==1 and buffs[0]['source']==s.session.world.resolve('b')
    path=tmp_path/'cp.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin));s.session.advance(3);r.session.advance(3)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()

"""Fresh Root tests for persistence without trusting claimed cache values."""
from copy import deepcopy
import json

import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import digest
from ark_sim.tools.replay import replay
from tools.chapter09_joint.test_fire_callback_v1 import package as fire_package


def package():
    p=fire_package()
    target=p['entities'][1]['components']
    target['resources']['sp']={'initial':0,'capacity':30,'recovery_rule':'rule/root/sp',
        'recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}
    p['rules'].append({'id':'rule/root/sp','kind':'rule','contract':'resource.recovery',
        'implementation':{'type':'expression','expression':'inputs.current+inputs.parameters.amount'}})
    return p


@pytest.mark.parametrize('time',[0,7])
def test_pending_SP_after_real_FIRE_attribute_read_CP_preserves_every_event(time,tmp_path):
    p=package();program=Compiler().compile(p);s=Engine.create(program,seed=9133)
    s.session.advance(time)
    source=s.session.world.resolve('source');target=s.session.world.resolve('receiver')
    s.ctx.elemental.apply(source,target,{'op':'elemental_damage','element':'fire','amount':7.5})
    assert s.ctx.attributes.value(target,'mres')==20
    before=s.session.checkpoint();cp=s.checkpoint()
    assert s.session.checkpoint()==before,'Checkpoint save must not create events or mutate kernel'
    path=tmp_path/'root.pending_sp.checkpoint.json';path.write_text(json.dumps(cp),encoding='utf8')
    r=Engine.restore(program,json.loads(path.read_bytes()))
    s.session.advance(5);r.session.advance(5)
    assert s.checkpoint()==r.checkpoint()
    assert list(s.session.events)==list(r.session.events)
    assert s.ctx.resources.current(target,'hp')==2040
    assert s.ctx.resources.current(target,'sp')==1


@pytest.mark.parametrize('field,value',[('value',999),('source_event_id',1),('view_version',999),('owner',False)])
def test_forged_cache_even_rehashed_digest_cannot_change_live_math(field,value):
    program=Compiler().compile(package());s=Engine.create(program,seed=953)
    assert s.ctx.attributes.value('receiver','mres')==40
    cp=deepcopy(s.checkpoint());entry=next(row for row in cp['attribute_cache']['entries'] if row['attribute']=='mres')
    entry[field]=value;entry['record_digest']=digest({key:item for key,item in entry.items() if key!='record_digest'})
    with pytest.raises((ValueError,KeyError,TypeError)):
        Engine.restore(program,cp)


def test_public_commands_head_and_CPP_after_callbacks_have_same_cached_sources(tmp_path):
    p=package();p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/fire/packet'}]
    program=Compiler().compile(p);s=Engine.create(program,seed=918)
    s.session.advance(3);cp=s.checkpoint();r=Engine.restore(program,cp)
    s.session.advance(5);r.session.advance(5);h=replay(program,s.export_replay())
    assert s.checkpoint()==r.checkpoint()==h.checkpoint()
    assert list(s.session.events)==list(r.session.events)==list(h.session.events)

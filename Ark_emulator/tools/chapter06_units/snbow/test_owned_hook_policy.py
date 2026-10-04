"""Supported live-owner hook lifetime policy; native postdeath choice is unresolved."""
import json,hashlib
import pytest
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter06_units.snbow.test_module import fixture,deploy,cold,packets,hp
from tools.chapter06_units.snbow.build_module import OUT,CORE

@pytest.mark.parametrize('retire,expected',[(False,335),(True,190)])
def test_public_owned_hook_lifetime_supported_policy_negative_control(retire,expected):
    s=fixture();deploy(s);cold(s)
    if retire:s.submit({'action':'skill','source':'target','ability':'ability/test/snbow/kill'},at=13)
    s.session.advance(16)
    actual={'source_alive':s.ctx.alive('archer'),'source_hp':hp(s,'archer'),'source_buffs':s.ctx.get('archer',('buffs','instances'),[]),'target_flags':s.ctx.spatial.selection_state('target',DEFAULT_STATE)['abnormal_flags'],'damage_packets':packets(s)}
    p=OUT/'owned_hook_policy';p.mkdir(parents=True,exist_ok=True)
    (p/('dead' if retire else 'live')).with_suffix('.actual.json').write_bytes((json.dumps({'schema':'ark-sim/ch6-snbow-owned-hook-reference-policy/v1','core':CORE,'actual':actual,'expected_current_policy':expected,'source_model_sha256':hashlib.sha256((OUT/'model.json').read_bytes()).hexdigest(),'native_postdeath_hook_lifetime_verified':False,'reference_replaceable':True,'required_alive_frozen_mechanism_passed':not retire and expected==335,'no_dummy_or_source_activation':True,'whole_stage_executed':False,'client_verified':False},ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    assert 16 in actual['target_flags'] and packets(s)==[(15,s.session.world.resolve('target'),expected)]
    assert s.ctx.alive('archer')==(not retire)

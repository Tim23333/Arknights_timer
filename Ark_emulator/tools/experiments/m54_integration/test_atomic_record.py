from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m54_qualified_visibility_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.domains.deployment import prepare,record
from ark_sim.domains.providers import BUILTIN_PROVIDERS


def floor(inputs,params,context):
    value=max(inputs['candidate'],1)
    return {'accepted':True,'value':value,'overflow':inputs['candidate']-value}
floor.version='m51_direct_stock_floor1'


def test_direct_record_failure_owns_its_transaction_and_preserves_world():
    p={'entities':[{'id':'unit/u','kind':'entity','components':{'spatial':{},'attributes':{'base':{'max_hp':1}},
        'resources':{'hp':{'initial':1,'capacity':1}},'deployable':{'base_cost':0,'terrain':'ground','stock':{'resource':'stock','amount':1}}}}],
        'rules':[{'id':'rule/floor','kind':'rule','contract':'resource.bounds','implementation':{'type':'provider','provider':'test.floor'}}],
        'scenarioDraft':{'id':'scene/direct_record','ruleset':'ruleset/ark_standard','objectives':{},'roster':['unit/u'],
            'map':{'rows':1,'cols':2},'resources':{'dp':{'initial':10,'capacity':10},'stock':{'initial':1,'capacity':1,'bounds_rule':'rule/floor'}}}}
    providers={**BUILTIN_PROVIDERS,'test.floor':floor};s=Engine.create(Compiler(providers=providers).compile(p),providers=providers)
    plan=prepare(s.ctx,'unit/u',{'row':0,'col':1});actor=s.ctx.lifecycle.create('unit/u',{'row':0,'col':1},deployed=True);before=s.checkpoint()
    with pytest.raises(ValueError,match='must be exact'):record(s.ctx,actor,plan)
    assert s.checkpoint()==before

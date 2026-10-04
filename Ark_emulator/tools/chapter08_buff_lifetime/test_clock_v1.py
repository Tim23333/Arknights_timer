"""Actual nominal30.5seconds dynamic rate, CP/head and stale timer ownership."""
import sys,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_buff_lifetime_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_buff_lifetime.policies_v1 import providers

def package():
    return {'schemaVersion':2,'manifest':{'id':'package/bufflife/source','requires':['preset/ark_standard']},
        'rules':[{'id':'rule/life','kind':'rule','contract':'buff.lifetime_rate','parameters':{'attribute':'one_minus_status_resistance','minimum':.001,'maximum':1000},'implementation':{'type':'provider','provider':'reference.c8.dynamic_buff_rate'}}],
        'buffs':[{'id':'buff/timer','kind':'buff','duration_seconds':30.5,'lifetime':{'rule':'rule/life','parameters':{},'count_when_inactive':True},
            'modifiers':[{'attribute':'atk','layer':'flat','value':10}]},
            {'id':'buff/resist','kind':'buff','modifiers':[{'attribute':'one_minus_status_resistance','layer':'final_ratio','value':-.5}]}],
        'entities':[{'id':'unit/owner','kind':'entity','components':{'attributes':{'base':{'atk':100,'one_minus_status_resistance':1,'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'abilities':['ability/install','ability/resist','ability/unresist']} }],
        'abilities':[{'id':'ability/install','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'self','buff':'buff/timer'}]},'timeline':[]},
            {'id':'ability/resist','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'self','buff':'buff/resist'}]},'timeline':[]},
            {'id':'ability/unresist','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'remove_buff','target':'self','buff':'buff/resist'}]},'timeline':[]}],
        'scenarioDraft':{'id':'scene/bufflife','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'initialEntities':[{'definition':'unit/owner','instanceAlias':'owner','position':{'row':0,'col':0}}]}}

def proof(p,tmp_path,commands,split,end):
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg)
    for aid,at in commands:s.submit({'action':'skill','source':'owner','ability':aid},at=at)
    s.advance(split);cp=tmp_path/'actual.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(end-split);r.advance(end-split);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events);return s

def timer_removes(s):return [e for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']=='buff/timer']

def test_unchanged_rate1_expires915_exact_CP_head(tmp_path):
    s=proof(package(),tmp_path,[('ability/install',0)],450,920);assert [e['time'] for e in timer_removes(s)]==[915]
    assert s.ctx.attributes.value('owner','atk')==100

def test_rate2_after300_consumes_previous_interval_before_new_rate_expiry608(tmp_path):
    s=proof(package(),tmp_path,[('ability/install',0),('ability/resist',300)],301,620);assert [e['time'] for e in timer_removes(s)]==[608]

def test_resistance_removed450_continues_remaining_expiry765(tmp_path):
    s=proof(package(),tmp_path,[('ability/install',0),('ability/resist',300),('ability/unresist',450)],451,800);assert [e['time'] for e in timer_removes(s)]==[765]

def test_refresh_at400_resets_nominal30_5_after_elapsedsettlement_expiry858(tmp_path):
    s=proof(package(),tmp_path,[('ability/install',0),('ability/resist',300),('ability/install',400)],401,880);assert [e['time'] for e in timer_removes(s)]==[858]

def test_manual_duplicate_callback_does_not_advance_clock():
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(package()),providers=reg);s.submit({'action':'skill','source':'owner','ability':'ability/install'},at=0);s.advance(2);i=s.ctx.get('owner',('buffs','instances'))[0];before=s.checkpoint()
    payload={'target':i['target'],'instance':i['id'],'generation':i['generation']};s.ctx.buffs.lifetime(s.session,payload);assert s.checkpoint()==before

@pytest.mark.parametrize('value',[True,-1,float('inf')])
def test_rate_output_invalid_atomic_application(value):
    p=package();p['rules'][0]['implementation']={'type':'provider','provider':'test.bad_rate'}
    def bad(inputs,params,context):return value
    reg={**providers(),'test.bad_rate':{'callable':bad,'version':'1'}};s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.buffs.apply('owner','owner','buff/timer')
    assert s.checkpoint()==before

"""Unshortened source30.5s parent/1s child/ramp with actual public commands."""
import json
import pytest

from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_boss.build_dragon_fire_v1 import OUT,TIMER,CHILD,application,build,sha
from tools.chapter08_boss.dragon_fire_policies_v1 import providers


def package():
    assert sha(OUT)=='eaf1a220f4a77fb598228cbb31342c96e587e1a6190662bd1f27ea7ad9c86b02'
    p=json.loads(OUT.read_bytes())
    p['entities']=[{'id':'unit/ch8/fire/source','kind':'entity','tags':['enemy'],'components':{
        'attributes':{'base':{'atk':1500,'max_hp':50000}},'resources':{'hp':{'initial':50000,'capacity':50000,'role':'health'}},
        'spatial':{},'abilities':['ability/ch8/fire/apply'],'lifecycle':{'policy':'policy/ark_lifecycle'}}},
        {'id':'unit/ch8/fire/target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'atk':0,'max_hp':10000,'def':999,'mres':99}},
            'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
    p['selectors']=[{'id':'selector/ch8/fire/player','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}]}]
    p['abilities']=[{'id':'ability/ch8/fire/apply','kind':'ability','selector':'selector/ch8/fire/player',
        'activation':{'mode':'manual','on_start':[application()]},'timeline':[]}]
    p['scenarioDraft']={'id':'scene/ch8/fire/author','ruleset':'ruleset/ark_standard','seed':81617,'map':{'rows':1,'cols':2},
        'initialEntities':[{'definition':'unit/ch8/fire/source','instanceAlias':'source','position':{'row':0,'col':0}},
            {'definition':'unit/ch8/fire/target','instanceAlias':'target','position':{'row':0,'col':1}}]}
    return p


def proof(p,tmp_path,end=950,commands=(0,),split=400,extra_providers=None):
    reg={**providers(),**(extra_providers or {})};program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg)
    for at in commands:s.submit({'action':'skill','source':'source','ability':'ability/ch8/fire/apply'},at=at)
    s.advance(split);cp=tmp_path/'actual.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg)
    s.advance(end-split);r.advance(end-split);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot()
    assert list(s.session.events)==list(r.session.events)==list(head.session.events)
    return s


def hits(s):return [e for e in s.session.events if e['type']=='damage.accepted']


def test_exact_source_rebuild_numericBB_not_flame():
    assert json.loads(OUT.read_bytes())==build()
    m=json.loads(OUT.read_bytes())['manifest']['metadata']
    assert m['source_DB_skill']['prefabKey']=='DragonFire' and m['source_DB_skill']['cooldown']==19


def test_full30packets56_to230_trueBUFF_ignoreSP_parent915_childretained(tmp_path):
    s=proof(package(),tmp_path)
    h=hits(s)
    assert [e['time'] for e in h]==list(range(30,901,30))
    assert [e['payload']['amount'] for e in h]==[50+6*n for n in range(1,31)]
    assert all(e['payload']['damage_flags']['source_attack_type']=='BUFF' and e['payload']['damage_flags']['ignore_for_sp'] is True for e in h)
    assert s.ctx.resources.current('target','hp')==5710
    b=s.ctx.get('target',('buffs','instances'),[])
    assert [i['definition'] for i in b]==[CHILD] and b[0]['expires_at'] is None


def test_repeat_timer_present_no_refresh_or_damage_reset(tmp_path):
    s=proof(package(),tmp_path,commands=(0,100,300))
    assert len([e for e in s.session.events if e['type']=='buff.applied'])==2
    assert [e['payload']['amount'] for e in hits(s)]==[50+6*n for n in range(1,31)]


def test_parent_reapply_after_expiry_reuses_existing_child_ramp(tmp_path):
    s=proof(package(),tmp_path,end=1020,commands=(0,930))
    assert len([e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==CHILD])==1
    assert [(e['time'],e['payload']['amount']) for e in hits(s)][-3:]==[(930,230),(960,230),(990,230)]


def test_target_after_hook_half_still_applies_and_source_ATK_not_burn_basis(tmp_path):
    p=package();p['entities'][0]['components']['attributes']['base']['atk']=3107
    p['rules'].append({'id':'rule/ch8/fire/authorhalf','kind':'rule','contract':'damage.pipeline',
        'implementation':{'type':'provider','provider':'author.ch8.fire.half'}})
    p['buffs'].append({'id':'buff/ch8/fire/authorhalf','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/ch8/fire/authorhalf'}]})
    p['entities'][1]['components']['buffs']={'initial':['buff/ch8/fire/authorhalf']}
    def half(inputs,params,context):
        return {'accepted':True,'amount':inputs['effect']['settlement']['amount']*.5,'allocations':[],'events':[]}
    s=proof(p,tmp_path,end=100,split=20,extra_providers={'author.ch8.fire.half':{'callable':half,'version':'1'}})
    assert [e['payload']['amount'] for e in hits(s)]==[28,31,34]


def test_source_public_retire_child_still_ticks_original_owner(tmp_path):
    p=package();p['entities'][1]['components']['abilities']=['ability/ch8/fire/retire']
    p['selectors'].append({'id':'selector/ch8/fire/source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]})
    p['abilities'].append({'id':'ability/ch8/fire/retire','kind':'ability','selector':'selector/ch8/fire/source',
        'activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdrawn'}}]},'timeline':[]})
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg)
    s.submit({'action':'skill','source':'source','ability':'ability/ch8/fire/apply'},at=0)
    s.submit({'action':'skill','source':'target','ability':'ability/ch8/fire/retire'},at=45)
    s.advance(40);cp=tmp_path/'retire.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg)
    s.advance(60);r.advance(60);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    assert not s.ctx.active('source')
    assert [e['payload']['amount'] for e in hits(s)]==[56,62,68]

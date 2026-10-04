"""True owned periodic packets, modification bypass, SP ignore and recovery."""
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_buff_no_source_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def fixture(without=True):
    request={'op':'no_source_damage','damage_type':'true','attack_type':'BUFF','fixed_amount':30,
        'damage_without_modify':without,'ignore_for_sp':True,'node_is_env_damage':False,
        'env_blackboard_injected':False,'environmental':False,'origin':{'source_file':'synthetic_source_counter'},
        'rules':{'damage.pipeline':'rule/probe/fixed'}}
    return {'schemaVersion':2,'manifest':{'id':'package/probe/buff_no_source','requires':['preset/ark_standard']},
        'rules':[{'id':'rule/probe/sp','kind':'calculation_rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current+inputs.parameters.amount'}},
            {'id':'rule/probe/fixed','kind':'calculation_rule','contract':'damage.pipeline',
            'implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}],'output':'nodes.result'}},
            {'id':'rule/probe/reject','kind':'calculation_rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[
                {'id':'result','expression':"{'accepted':False,'amount':0,'allocations':[],'events':[]}"}],'output':'nodes.result'}}],
        'buffs':[{'id':'buff/probe/periodic','kind':'buff','interval_seconds':.1,'effects':[request]},
                 {'id':'buff/probe/reject','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/probe/reject'}]}],
        'entities':[{'id':'unit/probe/owner','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':100,'atk':10}},
            'resources':{'hp':{'initial':100,'capacity':100,'role':'health'},'sp':{'initial':0,'capacity':9,'recovery_rule':'rule/probe/sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'target','amount':1}}},
            'spatial':{},'buffs':{'initial':['buff/probe/periodic','buff/probe/reject']},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],
        'scenarioDraft':{'id':'scene/probe/buff_no_source','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':1},'objectives':{},
            'initialEntities':[{'definition':'unit/probe/owner','instanceAlias':'owner','position':{'row':0,'col':0}}]}}


def main():
    out=ROOT/'validation/campaign/buff_no_source_v1/probe_valid_sp';out.mkdir(exist_ok=False);rows=[]
    for without in (False,True):
        p=fixture(without);s=Engine.create(Compiler().compile(p),seed=61792);s.advance(4)
        assert s.ctx.resources.current('owner','hp')==(70 if without else 100)
        cp=out/(str(without)+'.cp.json');pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
        for sim in (s,r):sim.advance(12)
        assert s.ctx.resources.current('owner','sp')==0
        if without:
            assert not s.ctx.active('owner') and s.ctx.resources.current('owner','hp')==0
            packets=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in packets]==[3,6,9,12]
            assert all(e['payload']['source'] is None and e['payload']['attack_type']=='BUFF' and e['payload']['origin']['buff_timer']['owner']==2 for e in packets)
            assert not [t for t in s.session.scheduler.pending if t['kind']=='domain.buff.periodic']
        else:assert not [e for e in s.session.events if e['type']=='damage.accepted']
        head=replay(s.program,s.export_replay());assert s.checkpoint()==r.checkpoint()==head.checkpoint()
        (out/(str(without)+'.events.json')).write_text(json.dumps(thaw(tuple(s.session.events)),indent=2)+'\n',encoding='utf8')
        rows.append({'without_modify':without,'passed':True,'checkpoint_sha':pin,'head_and_restore_equal':True})
    for key,value in [('damage_without_modify',1),('attack_type',[]),('ignore_for_sp',1)]:
        p=fixture();p['buffs'][0]['effects'][0][key]=value
        try:Compiler().compile(p)
        except ValueError:rows.append({'invalid':key,'rejected':True})
        else:raise AssertionError(key)
    p=out/'verification.json';p.write_text(json.dumps({'passed':True,'core':implementation_digest(),'cases':rows,
        'scope':'Author generic actual Buff3/6/9/12 actor-free packet bypasses reject hooks; False preserves hooks; true death/timer cleanup/SPignore/diskCP/head. Source2000 consumer/freshindependent/fullsuite pending'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'core':implementation_digest(),'sha':hashlib.sha256(p.read_bytes()).hexdigest()}))


if __name__=='__main__':main()

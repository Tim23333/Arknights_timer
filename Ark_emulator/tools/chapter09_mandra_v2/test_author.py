"""Fresh source-level rebirth, immunity, loss and public replay regressions."""
import sys,os,json,hashlib,copy,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_finale_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter09_mandra_v2.build import build,providers,BODY,PREFIX,IMMUNE,CALLGRAPH,DAMAGE,PROFILE
OUT=ROOT/'validation/campaign/chapter09_mandra_v2';LOG=Path(os.environ['ARKSIM_RUN_DIR']);FACTS={};ARTIFACTS=[]
CORE='cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def fixture(profile='talent_prefix'):
    p=build(profile);p['selectors'].append({'id':'selector/v2/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'},{'state':'alive'}],'limit':1})
    attacks=[]
    for name,kind,scale in [('kill','true',40),('true','true',1),('arts','arts',1),('physical','physical',1)]:
        aid='ability/v2/'+name;attacks.append(aid);p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/v2/boss','timeline':[{'at':0,'effect':{'op':'damage','damage_type':kind,'scale':scale}}]})
    p['entities'].append({'id':'unit/v2/operator','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':41000,'atk':1400,'def':137,'mres':22,'attack_speed_ratio':1}},'resources':{'hp':{'role':'health','capacity':41000,'initial':41000}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'abilities':attacks}})
    p['scenarioDraft']={'id':'scene/mandra/v2/'+profile,'ruleset':'ruleset/ark_standard','map':{'rows':6,'cols':8},'resources':{'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'},'initialEntities':[{'definition':BODY,'instanceAlias':'boss','position':{'row':2,'col':2}},{'definition':'unit/v2/operator','instanceAlias':'operator','position':{'row':2,'col':3}}],'commands':[{'at':7,'action':'skill','source':'operator','ability':'ability/v2/kill'}]};return p
def sim(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=15232)
def buffs(s):return {b['definition']:b for b in s.ctx.get('boss',('buffs','instances'))}
def rebirth_profiles():
    for profile,cfg in PROFILE.items():
        p=fixture(profile);end=157+cfg['invulnerable']*30;p['scenarioDraft']['commands'] += [
            {'at':160,'action':'skill','source':'operator','ability':'ability/v2/true'},
            {'at':end+2,'action':'skill','source':'operator','ability':'ability/v2/arts'},
            {'at':end+4,'action':'skill','source':'operator','ability':'ability/v2/physical'},
            {'at':end+6,'action':'skill','source':'operator','ability':'ability/v2/true'}]
        s=sim(p);s.advance(11);assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss')
        assert set(buffs(s))=={IMMUNE} and buffs(s)[IMMUNE].get('rebirth_self_lease');s.advance(146)
        assert not s.ctx.active('boss');s.advance(1);assert s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==50000
        held=buffs(s);assert set(held)=={IMMUNE,'buff/'+PREFIX+'shield','buff/'+PREFIX+'stone_area','buff/'+PREFIX+'invulnerable'}
        assert held['buff/'+PREFIX+'invulnerable']['expires_at']==end
        assert s.ctx.get('boss',('runtime','cooldowns'))['ability/'+PREFIX+'ray']==157+cfg['ray_cd']*30
        assert s.ctx.get('boss',('runtime','cooldowns'))['ability/'+PREFIX+'summon']==157+cfg['summon_cd']*30
        s.advance(8);assert s.ctx.resources.current('boss','hp')==50000
        path=LOG/(profile+'.checkpoint.json');path.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=providers())
        s.advance(end+8-s.session.time);r.advance(end+8-r.session.time);h=replay(s.program,s.export_replay(),providers=providers());assert cp(s)==cp(r)==cp(h)
        assert s.ctx.resources.current('boss','hp')==50000-364-352-1400
        packets=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload'].get('source')==s.session.world.resolve('boss') and e['payload'].get('ability') is None and abs(e['payload']['amount']-149.76)<1e-8];assert packets
        FACTS[profile]={'waiting_buffs':[IMMUNE],'restored_at':157,'invulnerability_until':end,'damage_losses':{'arts':364,'physical':352,'true':1400},'post_restore_buff_definitions':list(held),'CPP_full_public_head':True,'area_packets':len(packets)}
        ARTIFACTS.append({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'program_fingerprint':s.program.fingerprint})
def source_immunity():
    p=fixture();p['scenarioDraft']['commands']=[];s=sim(p);s.ctx.buffs.apply('operator','boss','buff/ch9/pillar/stun10');s.advance(1)
    assert all(s.ctx.buffs.controls('boss').values());status=s.ctx.spatial.selection_state('boss',DEFAULT_STATE)
    assert set(status['abnormal_immunes'])=={0,12,16,11,18} and status['abnormal_combo_immunes']==[0] and 0 not in status['abnormal_flags'] and 8 in status['abnormal_flags']
    FACTS['immunity']={'controls_allowed':dict(s.ctx.buffs.controls('boss')),'status':thaw(status)}
def true_and_normal_first_life():
    p=fixture();p['scenarioDraft']['commands']=[{'at':1,'action':'skill','source':'operator','ability':'ability/v2/arts'},{'at':3,'action':'skill','source':'operator','ability':'ability/v2/physical'},{'at':5,'action':'skill','source':'operator','ability':'ability/v2/true'}];s=sim(p);s.advance(6);assert s.ctx.resources.current('boss','hp')==50000-364-352-1400
    assert s.ctx.get('boss',('attributes','base'))['def']==520 and s.ctx.get('boss',('attributes','base'))['mres']==35
def native_leak_two():
    p=fixture();p['scenarioDraft']['commands']=[];p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1];p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':'WALK','startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':2},'checkpoints':[]};s=sim(p);s.advance(2)
    assert s.ctx.state()['leaks']==1 and s.ctx.state()['kills']==0 and s.ctx.resources.current('system/battle','life')==99997
    FACTS['leak']={'base_after':99997,'leaked':1,'killed':0}
def main():
    assert implementation_digest()==CORE
    files=[Path(__file__),ROOT/'tools/chapter09_mandra_v2/build.py',CALLGRAPH,DAMAGE,ROOT/'tools/chapter09_mandra_v1/build.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')];before={str(p):sha(p) for p in files};results=[]
    for fn in [rebirth_profiles,source_immunity,true_and_normal_first_life,native_leak_two]:
        try:fn();results.append({'case':fn.__name__,'passed':True})
        except Exception as error:results.append({'case':fn.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    after={str(p):sha(p) for p in files};code=0 if all(x['passed'] for x in results) and before==after else 1
    report={'core_before':CORE,'core_after':implementation_digest(),'actual_exit':code,'results':results,'facts':FACTS,'artifacts':ARTIFACTS,'source_before':before,'source_after':after,'source_equal':before==after,'content_only':True};path=OUT/'author.final.v2.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())

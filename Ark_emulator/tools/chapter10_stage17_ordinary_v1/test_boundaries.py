"""Fresh source3 gates and explicit lifesteal reference boundary matrix."""
import sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter10_stage17_ordinary_v1 import test_author as prior
FACT={};sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def reception(inputs,params,context):
    result=thaw(inputs['effect']['settlement'])
    if params['mode']=='barrier':result['allocations']=[{'resource':'barrier','amount':result['amount']},{'resource':'hp','amount':0}]
    else:
        result['amount']=0
        for a in result.get('allocations',[]):
            if 'amount' in a:a['amount']=0
            if 'delta' in a:a['delta']=0
    return result
def boundary_matrix():
    for label,expected,expected_damage in [('overkill',3055,25),('barrier',3000,0),('invincible',3000,0),('postRES',3049.5,22.5)]:
        p=prior.fixture('enemy_1228_dslime');player=next(e for e in p['entities'] if e['id']=='unit/stage17/test/player');reg={**prior.REG,'test.slime.receiver':{'callable':reception,'version':'explicit-primary-health-reference-boundary-v1'}}
        p['scenarioDraft']['commands']=[{'at':0,'action':'skill','source':'player','ability':'ability/stage17/test/hurt'}]
        if label=='overkill':player['components']['resources']['hp'].update(initial=25,capacity=25);player['components']['attributes']['base']['max_hp']=25
        if label in ['barrier','invincible']:
            rid='rule/test/slime_receiver';bid='buff/test/slime_receiver';p['rules'].append({'id':rid,'kind':'rule','contract':'damage.pipeline','parameters':{'mode':label},'implementation':{'type':'provider','provider':'test.slime.receiver'}});p['buffs'].append({'id':bid,'kind':'buff','damage_hooks':[{'phase':'after','rule':rid}],**({'selection_flags':{'abnormal_flags':[5]}} if label=='invincible' else {})});player['components']['buffs']={'initial':[bid]}
            if label=='barrier':player['components']['resources']['barrier']={'initial':100,'capacity':100}
            flags={'flags':[5] if label=='invincible' else [],'immunes':[]};next(r for r in p['rules'] if r['id']=='rule/campaign/elemental_receivers/eligible')['parameters']['buff_flags'][bid]=flags
        if label=='postRES':player['components']['attributes']['base'].update(mres=75,**{'def':100000})
        program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=1229);s.advance(3);path=prior.LOG/(label+'.checkpoint.json');path.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(program,json.loads(path.read_bytes()),providers=reg);s.advance(5);r.advance(5);h=replay(program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==h.checkpoint()
        events=[thaw(e) for e in s.session.events if e['type'] in ['damage.accepted','healing.accepted']];health=s.ctx.resources.current('source','hp');damage=next(e['payload']['amount'] for e in events if e['type']=='damage.accepted' and e['payload']['source']==s.session.world.resolve('source'))
        FACT[label]={'source_HP':health,'actual_primary_health_damage':damage,'events':events,'CPP_full_head':True,'program_fingerprint':program.fingerprint,'checkpoint_sha256':sha(path)}
        assert health==expected and damage==expected_damage
def main():
    core=implementation_digest();files=[f for f in (CAND/'ark_sim').rglob('*') if f.is_file() and f.suffix in ['.py','.json']]+[Path(__file__),ROOT/'tools/chapter10_stage17_ordinary_v1/build.py',ROOT/'tools/chapter10_stage17_ordinary_v1/test_author.py'];before={str(f):sha(f) for f in files};results=[]
    for f in [prior.darmy,prior.slime,prior.lord,boundary_matrix]:
        try:f();results.append({'case':f.__name__,'passed':True})
        except Exception as e:results.append({'case':f.__name__,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    after={str(f):sha(f) for f in files};code=0 if all(r['passed'] for r in results) and before==after else 1
    path=prior.OUT/'author.final.v4.json';assert not path.exists();path.write_text(json.dumps({'core_before':core,'core_after':implementation_digest(),'source_before':before,'source_after':after,'source_equal':before==after,'actual_exit':code,'results':results,'source_actor_facts':prior.FACT,'lifesteal_reference_boundary_facts':FACT,'native_method_body_verified':False},indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())

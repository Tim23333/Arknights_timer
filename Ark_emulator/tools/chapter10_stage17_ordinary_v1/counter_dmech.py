"""Actual compile counter for sourced20s non-damage owned SP channel."""
import sys,json,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.chapter10_stage17_ordinary_v1.build import source,SOURCE,BSON
OUT=ROOT/'validation/campaign/chapter10_stage17_ordinary_v1';OUT.mkdir(parents=True,exist_ok=True)
def main():
    v,pref=source('enemy_1223_dmech');allsource=json.loads(SOURCE.read_bytes());projectile=allsource['projectiles']['projectile_enemy_dmech_charge'];lasso=next(c for c in projectile['components'].values() if c['native_class']=='LassoProjectile');assert lasso['raw']['_linkDuration']==20
    proposal={'schemaVersion':2,'entities':[],'abilities':[],'rules':[{'id':'rule/counter/motion','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}}],'buffs':[{'id':'buff/counter/dmech_charge','kind':'buff','metadata':{'native':'dmech_charge modify_sp[start]','native_BSON':json.loads(BSON.read_bytes())['templates']['modify_sp[start]']}}],'attachments':[{'id':'attachment/counter/native_charge','kind':'attachment','duration_seconds':20,'flight_lifetime_seconds':1,'step_interval_seconds':1/30,'refresh_interval_seconds':1,'hit_interval_seconds':1,'motion':{'rule':'rule/counter/motion','parameters':{'mode':'homing','speed':1}},'target_buff':'buff/counter/dmech_charge','effect':{'op':'modify_resource','resource':'sp','delta':1},'damage_integral':False,'completion_blocking':True,'force_reach_on_timeout':True,'source_cancel_flags':[12,0],'ignored_owned_source_flags':[],'lifecycle':{'source_invalid':'cancel','target_invalid':'cancel','source_hidden':'cancel','target_hidden':'cancel'},'max_packets':None,'source_recovery_buff':None,'recovery_on':[]}],'scenarioDraft':{'id':'scene/counter/dmech_channel','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':2},'initialEntities':[]}}
    proposal['definitions']=[row for field in ['entities','abilities','rules','buffs','attachments'] for row in proposal.pop(field)]
    # Make the channel reachable from an actually possessed finite ability;
    # an unreferenced declaration is correctly pruned by Compiler.
    proposal['definitions'] += [
        {'id':'unit/counter/source','kind':'entity','components':{'attributes':{'base':{'max_hp':6000,'atk':300,'def':250,'mres':20,'move_speed':1,'attack_interval':2}},'resources':{'hp':{'role':'health','initial':6000,'capacity':6000}},'spatial':{},'abilities':['ability/counter/charge']}},
        {'id':'ability/counter/charge','kind':'ability','activation':{'mode':'manual'},'wait_for_channels':True,'timeline':[{'at':0,'effect':{'op':'begin_attachment','attachment':'attachment/counter/native_charge'}}]}]
    proposal['scenarioDraft']['initialEntities']=[{'definition':'unit/counter/source','position':{'row':0,'col':0}}]
    error=None
    try:Compiler().compile(proposal)
    except Exception as e:error={'class':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()}
    assert error and 'Owned attachment requires actor damage or an atomic health/element packet' in error['message'],error
    def leaves(value,path='$',out=None):
        if out is None:out=[]
        if isinstance(value,dict):
            for k,v in value.items():leaves(v,path+'.'+k,out)
        elif isinstance(value,list):
            for i,v in enumerate(value):leaves(v,path+'['+str(i)+']',out)
        elif isinstance(value,(float,int)) and not isinstance(value,bool) and abs(value-.9)<1e-6:out.append({'path':path,'value':value})
        return out
    report={'schema':'ark-sim/source-channel-core-gap-counter/v1','core':implementation_digest(),'actual_compile_rejected':True,'simulation_created':False,'consumer_complete':False,'native_variant':v,'native_prefab':pref,'native_projectile':projectile,'source_SHA':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'BSON_SHA':hashlib.sha256(BSON.read_bytes()).hexdigest(),'proposal':proposal,'error':error,'requested_point9_source_matches':leaves({'variant':v,'prefab':pref,'projectile':projectile}),'boundaries':['This counter proves generic owned attachment currently excludes SP resource packet. No fake0 damage substituted.','Exact .9 trigger ratio not found in available dmech prefab/DB/projectile leaves; any reference must be explicitly attributed, not silently claimed native.','Native EnemySkill maxTriggerTime1/CD5/SPcost5 and ThreePartChannel duration20/pre+post.6669999957/source selector bothside category2 gunctrl retained.','Completion/intr source-owned selector CreateBuffUseAbilitySelector and -15 SP reduction are required; not replaced by Manfred charge binding.']}
    path=OUT/'dmech.channel.counter.v1.json';assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'counter':str(path),'SHA':hashlib.sha256(path.read_bytes()).hexdigest(),'error':error['message']}))
if __name__=='__main__':main()

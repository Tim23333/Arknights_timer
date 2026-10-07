"""Keep v3 diagnostics, add native-resource ready windows and slot reservation."""
import copy,json,hashlib,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    folder=ROOT/'packages/campaign/chapter0_stage_models';receipts=[]
    for stage in ('level_main_00-10','level_main_00-11'):
        src=folder/(stage+'.source.v2.json');package=json.loads(src.read_bytes());defs={d['id']:d for d in package['definitions']};oldpath=folder/(stage+'.public.plan.v3.json');doc=copy.deepcopy(json.loads(oldpath.read_bytes()));commands=doc['commands'];deploys={c['entity']:c for c in commands if c['action']=='deploy'};ready=[]
        for uid in doc['roster']:
            actor=defs[uid];skill=actor['metadata']['selected_skill_ability'];ability=defs[skill];activation=ability['activation'];sp=actor['components']['resources']['sp'];cost=sum(c['amount'] for c in activation.get('costs',[]) if c['resource']=='sp');initial=sp['initial'];recovery=sp.get('recovery',{});rate=sp.get('recovery_rate',0);mode=recovery.get('mode');deployed=deploys[uid]['at']
            if mode=='periodic' and not recovery.get('selector') and rate>0:
                interval=recovery['interval_seconds'];ticks=math.ceil(max(0,cost-initial)/(rate*interval))*math.ceil(interval*30);at=deployed+ticks+1
                windows=[at,at+901];policy='Declared periodic recovery lower bound; ignore source talent/random additions; any preceding successful cast may freeze recovery and actual retry can reject.'
            else:
                windows=[deployed+401,deployed+901];policy='Event or selector-qualified SP: no ready guarantee; finite repeated public attempts and natural auto activation must be observed.'
            commands.extend({'at':at,'action':'skill','source':deploys[uid]['alias'],'ability':skill} for at in windows)
            ready.append({'unit':uid,'skill':skill,'source_resource':sp,'source_activation_cost':cost,'declared_mode':activation['mode'],'auto_only':activation.get('parameters',{}).get('auto_only',False),'retry_ticks':windows,'policy':policy})
        # Withdrawals must follow all selected-skill opportunities for the
        # departing original actors; later public replacements keep native DP.
        readyby={r['unit']:r for r in ready};old_deploy_order=list(deploys);departing=set(old_deploy_order[:5]);extra={deploys[u]['alias']:max(readyby[u]['retry_ticks'])+1 for u in departing}
        for c in commands:
            if c['action']=='withdraw':c['at']=max(c['at'],extra.get(c['source'],c['at']))
        first_four=max(c['at'] for c in commands if c['action']=='withdraw' and c['source'] in {deploys[u]['alias'] for u in old_deploy_order[:4]})
        # Existing v3 later deployments already follow the enlarged first-four
        # window in these fixed stages; reject a drift rather than fund or skip.
        assert min(deploys[u]['at'] for u in old_deploy_order[8:])>first_four
        mon=next(s for s in doc['summon_attempts'] if s['token_definition']=='unit/kalts_mon3tr_model');mon_at=mon['command']['at'];kalts=deploys['unit/char_003_kalts']['alias'];commands.extend({'at':mon_at+offset,'action':'skill','source':kalts,'ability':'ability/kalts_host_s3'} for offset in (451,901))
        commands.sort(key=lambda c:c['at']);candidate=copy.deepcopy(package);candidate['scenarioDraft']['commands']=commands;Compiler().compile(candidate)
        doc.update({'schema':'ark-sim/chapter0-public-finite-plan/v4','parent_plan_sha256':sha(oldpath),'source_native_SP_ready_windows':ready,'manual_selected_skill_attempts':52,'Mon3tr_qualified_host_windows':[mon_at+451,mon_at+901],'Myrtle_source_cost':24,'Myrtle_first_conservative_ready_retry_at':deploys['unit/char_151_myrtle']['at']+421,'native_resource_changed':False,'SP_injected':False,'previous_diagnostic_attempts_preserved':True})
        path=folder/(stage+'.public.plan.v4.json');assert not path.exists();path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8');receipts.append({'stage':stage,'sha256':sha(path),'selected_skill_attempts':52,'last_tick':max(c['at'] for c in commands),'compiled':True,'whole_stage':False})
    out=ROOT/'validation/campaign/chapter0_stage_assembly_v1/public.plan.v4.receipt.json';out.write_text(json.dumps({'records':receipts,'tool_sha256':sha(Path(__file__)),'whole_stage':False},indent=2)+'\n',encoding='utf8');print(json.dumps(receipts))
if __name__=='__main__':main()

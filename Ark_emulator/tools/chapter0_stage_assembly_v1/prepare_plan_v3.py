"""Twelve public actors, source skills and three source-owned summon attempts."""
import hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    folder=ROOT/'packages/campaign/chapter0_stage_models';records=[]
    for stage in ('level_main_00-10','level_main_00-11'):
        src=folder/(stage+'.source.v2.json');p=json.loads(src.read_bytes());scene=p['scenarioDraft'];defs={d['id']:d for d in p['definitions']};old=json.loads((folder/(stage+'.public.plan.v2.json')).read_bytes());commands=[];spent=0;last=30;deploys=[];used=set();roster=scene['roster']
        def fund(cost,earliest):
            nonlocal spent,last
            at=max(last,earliest,math.ceil(max(0,spent+cost-10))*30+31);assert min(99,10+(at-1)//30-spent)>=cost;spent+=cost;last=at+31;return at
        def cell(terrain):
            mask={'ground':1,'high':2,'both':3}[terrain]
            for i,t in enumerate(scene['map']['tiles']):
                pos=(i//scene['map']['cols'],i%scene['map']['cols'])
                if t['buildableType'] and (mask==3 or t['buildableType'] in (mask,3)) and pos not in used:used.add(pos);return {'row':pos[0],'col':pos[1]}
            raise ValueError('No distinct native terrain cell for '+terrain)
        for index,uid in enumerate(roster):
            if index==8:
                swap=max(last,max(d['at']+451 for d in deploys[:4]));commands.extend({'at':swap+i,'action':'withdraw','source':d['alias']} for i,d in enumerate(deploys[:4]));last=swap+4
            actor=defs[uid];cost=actor['components']['attributes']['base']['deploy_cost'];terrain=actor['components']['deployable']['terrain'];at=fund(cost,last);position=cell(terrain);alias='fixed12/'+uid.rsplit('/',1)[1]
            command={'at':at,'action':'deploy','entity':uid,'alias':alias,**position,'facing':'right'};commands.append(command);deploys.append(command)
            skill=actor['metadata']['selected_skill_ability'];assert skill in actor['components']['abilities']
            commands.extend({'at':at+offset,'action':'skill','source':alias,'ability':skill} for offset in (60,450))
        # The first four swaps create four slots; a fifth public withdrawal
        # reserves Mon3tr's real capacity1 after all twelve deployment attempts.
        reserve=max(last,deploys[4]['at']+451);commands.append({'at':reserve,'action':'withdraw','source':deploys[4]['alias']});last=reserve+1;summons=[]
        for host,ability,token,cost in [('char_003_kalts','ability/kalts_summon','unit/kalts_mon3tr_model',10),('char_400_weedy','ability/campaign_weedy_deploy_cannon','unit/campaign_weedy_cannon',5),('char_179_cgbird','ability/support_night_bird','unit/support_night_bird',5)]:
            terrain=defs[token]['components']['deployable']['terrain'];position=cell(terrain);at=fund(cost,last);command={'at':at,'action':'skill','source':'fixed12/'+host,'ability':ability,'payload':{'position':position}};commands.append(command);summons.append({'command':command,'token_definition':token,'native_capacity':defs[token]['components']['deployable'].get('capacity',1),'declared_cost':cost})
        assert [x['native_capacity'] for x in summons]==[1,0,0]
        commands.sort(key=lambda c:c['at']);candidate=json.loads(src.read_bytes());candidate['scenarioDraft']['commands']=commands;Compiler().compile(candidate)
        doc={'schema':'ark-sim/chapter0-public-finite-plan/v3','source_package_sha256':sha(src),'commands':commands,'roster':roster,'deployment_count':12,'manual_selected_skill_attempts':24,'summon_attempts':summons,
          'native_constraints':old['constraints'],'slot_strategy':'First8 then public withdraw first4 for last4; withdraw fifth original actor to reserve Mon3tr capacity1; source cannon/bird capacity0. No slot increase.',
          'funding':'Only native DP10 +1/sec; conservative before-tick lower funding at every cost. Ignore skill DP income and all withdraw refunds. Costs are first-deploy declared native roster costs, plus original summon10/5/5.',
          'ACK_driver':{'class':'tools.control_driver.public_ack_v2.PublicAckDriver','policy':'external_dialogue_observation_plus_one_tick/v2','path':str(ROOT/'tools/control_driver/public_ack_v2.py'),'sha256':sha(ROOT/'tools/control_driver/public_ack_v2.py'),'ledger_required':['event','control','step','submitted_at','at','public_command_order'],'static_control_ids_or_ACK_schedule':False},
          'coverage_policy':'Every scheduled public attempt must retain its accepted or rejected result; target/death/terrain/SP/timing rejection cannot be skipped. If native stage finishes before future attempts, retain actual terminal/replay evidence and use separately scoped mechanism probes for uncovered behavior.',
          'source_parameters_changed':False,'whole_stage_started':False,'independent_admission_pending':True}
        path=folder/(stage+'.public.plan.v3.json');assert not path.exists();path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8');records.append({'stage':stage,'sha256':sha(path),'deploy':12,'selected_skill_attempts':24,'summon_attempts':3,'last_scheduled_tick':max(c['at'] for c in commands),'whole_stage':False})
    out=ROOT/'validation/campaign/chapter0_stage_assembly_v1/public.plan.v3.receipt.json';out.write_text(json.dumps({'records':records,'tool_sha256':sha(Path(__file__)),'compiled':True,'whole_stage':False},indent=2)+'\n',encoding='utf8');print(json.dumps(records))
if __name__=='__main__':main()

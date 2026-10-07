"""Static source-plan/ownership/terrain/slot audit; no acceptance claims."""
import json,copy,hashlib,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.chapter10_stage_source_peer_v1.source_preflight import ROOT,exact
BASE=ROOT/'scenarios/campaign/chapter10/level_main_10-14/public_plan_v1_finite'
PACKAGE=ROOT/'packages/campaign/chapter10_stage_models/level_main_10-14.source_draft.v2.life99999.json'
ROSTER=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json'
OUT=ROOT/'validation/campaign/chapter10_stage_source_peer_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())
def main():
    files=[BASE/'commands.json',BASE/'plan.json',PACKAGE,ROSTER,ROOT/'tools/chapter10_stage_assembly_v1/build_commands.py',Path(__file__)]
    before={str(p):sha(p) for p in files};commands=load(BASE/'commands.json');plan=load(BASE/'plan.json');p=load(PACKAGE);scene=p['scenarioDraft'];defs={d['id']:d for d in p['definitions']};original={d['id']:d for d in load(ROSTER)['definitions']}
    assert plan['source_package_sha256']==sha(PACKAGE) and plan['commands_sha256']==sha(BASE/'commands.json') and len(commands)==41
    assert len({c['entity'] for c in commands if c['action']=='deploy'})==12 and set(c['entity'] for c in commands if c['action']=='deploy')==set(scene['roster'])
    assert scene['resources']['dp']['initial']==10 and scene['parameters']['deploy_capacity']==8
    aliases={};active={};occupied={};trace=[];cells=[];skills=[];withdrawals=[];costs=[];maximum=0;last=-1;no_bonus_dp=10.;previous_tick=0;negative=[]
    for index,c in enumerate(commands):
        assert type(c['at']) is int and c['at']>=last;last=c['at']
        # Illustrative accounting only: no skill bonuses/refunds, no death,
        # exact acceptance or phase-boundary periodic scheduling is asserted.
        no_bonus_dp=min(99,no_bonus_dp+(c['at']-previous_tick)/30);previous_tick=c['at']
        if c['action']=='deploy':
            entity=defs[c['entity']];raw=original[c['entity']];exact(entity['components']['attributes']['base'],raw['components']['attributes']['base']);exact(entity['components']['deployable'],raw['components']['deployable'])
            alias=c['alias'];assert alias not in aliases and c['entity'] in scene['roster'];aliases[alias]=c['entity'];position=(c['row'],c['col']);assert position not in occupied
            deploy=entity['components']['deployable'];mask={'ground':1,'high':2,'both':3}[deploy['terrain']];tile=scene['map']['tiles'][c['row']*scene['map']['cols']+c['col']];assert tile['buildableType']&mask
            amount=entity['components']['attributes']['base']['deploy_cost'];no_bonus_dp-=amount;costs.append({'index':index,'at':c['at'],'alias':alias,'cost':amount,'no_bonus_no_refund_DP':no_bonus_dp})
            if no_bonus_dp<0:negative.append({'at':c['at'],'alias':alias,'balance':no_bonus_dp})
            capacity=deploy.get('capacity',1);active[alias]={'definition':c['entity'],'capacity':capacity,'position':position};occupied[position]=alias
            cells.append({'command_index':index,'position':list(position),'definition':c['entity'],'terrain':deploy['terrain'],'tile':tile,'native_hp':raw['components']['attributes']['base']['max_hp']})
        elif c['action']=='skill':
            assert c['source'] in aliases;entity=defs[aliases[c['source']]];ability=defs[c['ability']];assert c['ability'] in entity['components']['abilities']
            activation=ability['activation'];assert activation['mode']=='manual'
            costspec=activation.get('costs',[])
            for cost in costspec:
                assert math.isfinite(cost['amount']) and cost['amount']>=0
                owner=cost.get('owner','source');resource=scene['resources'].get(cost['resource']) if owner=='battle' else entity['components']['resources'].get(cost['resource']);assert resource is not None
                if owner=='battle' and cost['resource']=='dp':no_bonus_dp-=cost['amount']
            details={'command_index':index,'at':c['at'],'owner_alias':c['source'],'ability':c['ability'],'costs':costspec,'recovery':entity['components'].get('resources',{}).get('sp'),'source_alive_cast_busy_status_SP_not_verified':True}
            for effect in activation.get('on_start',[]):
                if effect['op']!='spawn':continue
                child=defs[effect['definition']];params=effect['parameters'];assert effect['owner']=='source' and params['on_owner_retire']=='remove' and params['position_from_payload'] is True
                payload=c['payload'];position=(payload['position']['row'],payload['position']['col']);assert position not in occupied
                deploy=child['components']['deployable'];mask={'ground':1,'high':2,'both':3}[deploy['terrain']];tile=scene['map']['tiles'][position[0]*scene['map']['cols']+position[1]];assert tile['buildableType']&mask
                capacity=deploy.get('capacity',1);alias='planned_owned/'+c['source']+'/'+effect['definition'];assert alias not in active
                active[alias]={'definition':effect['definition'],'capacity':capacity,'position':position,'owner':c['source']};occupied[position]=alias
                details['owned_spawn']={'definition':effect['definition'],'capacity':capacity,'max_owned':params['max_owned'],'native_cooldown_seconds':deploy['cooldown_seconds'],'native_max_instances':deploy.get('parameters',{}).get('max_instances'),'on_owner_retire':'remove','position':list(position),'tile':tile,'lifetime_seconds':effect.get('lifetime_seconds')}
            skills.append(details)
        elif c['action']=='withdraw':
            assert c['source'] in aliases;was_active=c['source'] in active;removed=[]
            for alias in list(active):
                if alias==c['source'] or active[alias].get('owner')==c['source']:
                    item=active.pop(alias);occupied.pop(item['position']);removed.append(alias)
            withdrawals.append({'at':c['at'],'alias':c['source'],'planned_live_before':was_active,'owned_children_removed_in_plan':removed,'actual_rejection_must_be_logged':True})
        else:raise AssertionError('Unexpected public action '+c['action'])
        slots=sum(x['capacity'] for x in active.values());assert slots<=8,(c['at'],slots);maximum=max(maximum,slots);trace.append({'index':index,'at':c['at'],'action':c['action'],'planned_slots_if_survival_and_acceptance':slots})
    assert maximum==8 and not active
    assert [c['at'] for c in commands if c['action']=='withdraw' and c['at']>=12000]==list(range(12000,12012))
    assert [x['at'] for x in withdrawals if x['planned_live_before'] is False]==[12000,12001,12002,12004,12006]
    # Existing reference ownership is the authority, not this command plan.
    owned=[s['owned_spawn'] for s in skills if 'owned_spawn' in s];assert [s['capacity'] for s in owned]==[1,0,0]
    assert all('deployable' not in defs[x['definition']]['components'] for x in scene['initialEntities'])
    after={str(f):sha(f) for f in files};assert before==after
    report={'schema':'ark-sim/source-public-plan-static-review/v1','source_plan_only':True,'static_bounds_passed':True,'actual_acceptance_verified':False,'model_approved':False,'whole_stage_approved':False,'client_verified':False,'commands':41,'distinct_roster':12,'maximum_planned_slots':maximum,'source_before':before,'source_after':after,'source_equal':True,'cells':cells,'skills':skills,'slot_trace':trace,'withdrawals':withdrawals,'deployment_costs':costs,'owned_summons':owned,'DP_dependency':{'initial':10,'capacity':99,'recovery_per_second':1,'illustrative_no_skill_bonus_no_refund_negative_points':negative,'meaning':'This is not actual DP simulation. Myrtle skill/recovery/refunds and actor survival determine acceptance; no new funds added.'},'conditional_risks':['SP, DARK flag24, source death, target eligibility, busy casts and actual periodic recovery phases are dynamic; every rejection must be logged.','Kalts hostS3 at4500 is only10s after summon4200; original recovery selector pauses/resets SP while no owned Mon3tr. Cost15 therefore depends on real external SP/temporal effects and may reject.','Amgoat S3 at3600 is20s after deploy3000. Raw initial55/cost80 requires original owned random initial-SP talent or external SP; original talent preserved, not assumed successful.','Five final withdrawals target actors already publicly withdrawn; rejection is an intentional finite attempt and must remain in actual outcomes.','Owned child presence/lifetime and parent removal are source semantics; static plan does not prove runtime cleanup.'],'simulation_started':False,'raw_logs_generated':0}
    path=OUT/'public.plan.source_only.v1.json';assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'static_bounds_passed':True,'maximum_slots':maximum,'receipt_sha256':sha(path),'conditional_risks':report['conditional_risks']}))
if __name__=='__main__':main()

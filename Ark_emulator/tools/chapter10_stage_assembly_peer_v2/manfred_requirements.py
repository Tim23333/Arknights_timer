"""Fixed selected source dependency inventory, not a Boss implementation."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter10_stage_assembly_peer_v2'
SOURCE=ROOT/'packages/campaign/chapter10_source_prepare/enemies.native.v1.json';PLAN=ROOT/'packages/campaign/chapter10_source_prepare/source.plan.v1.json';BSON=ROOT/'packages/campaign/chapter10_source_prepare/bson.transitive.v2.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    data=json.loads(SOURCE.read_bytes());v=next(x for x in data['variants'].values() if x['prefab_key']=='enemy_1528_manfri');pref=data['prefabs'][v['prefab_key']];enemy=v['native_enemy']['resolved'];bb={x['key']:x['valueStr'] if x['valueStr'] is not None else x['value'] for x in enemy['talentBlackboard']};bson=json.loads(BSON.read_bytes())
    modes=[]
    for mode in v['modes']:
        modes.append({'index':mode['index'],'native_mode_path':mode['path_id'],'raw_source_mode':mode['raw'],'nodes':{k:{'native_class':n.get('native_class'),'source_path':n.get('path_id'),'status':n.get('status'),'raw_attack_type':n.get('raw',{}).get('_damageType'),'raw_scale':n.get('raw',{}).get('_atkScale'),'animation_binding':n.get('animation_binding')} for k,n in mode['nodes'].items()}})
    classes={'RebornTalent','EmptyAbility','EmptyActiveAbility','ActiveBuffAbility','PassiveBuffAbility','BuffToOwner','BuffToOwnerDuringAbility','BuffWhenCastOnSameTarget','EnemySkill','AnimatedActionToOwnerAbility','AnimatedActionToTargetAbility','RangedAttack','MeleeAttack','GlobalAuraAbility'}
    owned=[]
    for key,c in pref['components'].items():
        if c['native_class'] not in classes:continue
        raw=c['raw'];row={'native_path':key,'class':c['native_class'],'gameobject':c['gameobject_name'],'alias':raw.get('_metadata'),'selector':raw.get('_selector'),'trigger':raw.get('_trigger'),'buffs':[{'buffKey':b['buffKey'],'templateKey':b['templateKey'],'isSilenceable':b['isSilenceable'],'lifeTimeType':b['lifeTimeType'],'lifeTime':b['lifeTime'],'durationKey':b['durationKey'],'native_attributes':b['attributes']} for b in raw.get('_buffs',[])]}
        for name in ['_hpRechargeRatio','_useAbilityToHandle','_abilityName','_delayTime','_ignoreNormalAnim','_buffsRetainedWhenReborn','_maxTriggerTime','_familyMask','_checkParentActive','_ignoreSilence','_duration','_durationKey','_triggerInterval','_intervalKey','_interval','_damageType','_atkScale','_preDelay','_cooldown','_selectorAsTarget','_startEvent','_endEvent']:
            if name in raw:row[name]=raw[name]
        owned.append(row)
    template_rows=[]
    def node_types(value,out=None):
        if out is None:out=[]
        if isinstance(value,dict):
            if '$type' in value:out.append(value['$type'].split('+')[-1].split(',')[0])
            for v in value.values():node_types(v,out)
        elif isinstance(value,list):
            for v in value:node_types(v,out)
        return out
    for key,record in bson['templates'].items():
        if 'manfri' in key or key in ['evade','enemy_trigger_ability','switch_mode_no_restore','track_at_next_wave_when_buff_finish','triggerability_tick_trigger']:
            parsed=record['parsed'];template_rows.append({'key':key,'document_sha256':record['document_sha256'],'events':{event:node_types(actions) for event,actions in parsed['eventToActions'].items()}})
    requirements=[
        {'area':'Original3 modes/ownership','source':'mode0+2 actual19/55 melee nodes with arts/physical respectively; mode1 native EmptyActiveAbility+NeverTrigger, must represent transition ownership without fake attack. All general/talent/skill nodes retained.','existing_candidates':'behavior/rebirth/finite owned waiting actions may compose; not tested for this source yet.'},
        {'area':'Funnel attack families','source':'s1 source.5ATK arts and charge3; s2 parallel physical+arts.5 and charge6; common same-target ASPD+60 cap5 expiry6sec; target-switch resets.','requirements':'Actual cast/target history, source selectors, channels and source-owned cannon SP endpoints; cannot mount empty aliases.'},
        {'area':'Shield','source':'80% physical/arts evasion; cannon hit disables30sec and causes stun8sec.','requirements':'Actual provenance classification of gunctrl hit, modifier-aware receiving hook, real control with source immunity fields; TRUE bypass must follow literal damage-mask/action source.'},
        {'area':'First death20sec revival','source':'RebornTalent actual HP recharge1.0, handle aliasRevive, retained enemy_manfri_aura_on; BB Reborn20/invincible5/interval.8.','requirements':'Actual first-life death and owned waiting callbacks permit parallel rage attacks at HP0, timed second-life HP restore and mode2; no HP1 placeholder or ordinary dead cast grants. Finish-current-wave source hook must be sourced.'},
        {'area':'Rage','source':'Random global target every.8sec, .3ATK arts/charge6; native EnemySkill placeholderCD9999 must not be misread as ordinary cooldown for owned rebirth trigger.','requirements':'Real finite source-owned trigger, deterministic RNG/FP, each cast/packet/charge generation and transaction/CPP/head.'},
        {'area':'Stage-specific aura','source':'aura.isenabled=aura_off string in resolved BB; interval.5/scale.05/radius1.1 remain literal.','requirements':'Preserve disabled selected10-17 branch instead of activating aura by mere prefab presence.'},
        {'area':'Cannon coupling','source':'Three distinct source aliases Funnel_s1_charge, Funnel_s2_charge, Funnel_rage_charge.','requirements':'Fixed pot1 gunctrl SP endpoint and native both-side/category/tag selector. Different from dmech20sec charging skill; no shared owner shortcut.'}]
    report={'schema':'ark-sim/manfred-source-dependency-requirements/v1','source_files':{str(p):sha(p) for p in [SOURCE,PLAN,BSON,Path(__file__)]},'variant':v['variant_id'],'native_reference':v['native_reference'],'native_stage_override':v['native_enemy']['stage_override'],'resolved_source':enemy,'blackboard':bb,'native_modes':modes,'source_owned_components':owned,'BSON_actions':template_rows,'source_version_policy':data['source_version_policy'],'selected_reference':{'url':'https://prts.wiki/w/曼弗雷德','retrieved_date':'2026-10-07','scope':'CurrentPRTS level0; reference not original method body','summary':'Level0 stats agree40000/1000/600/40. Two lives; first death20s100%restore, then5s invulnerability. Focus60cap5 expires6s. Physical/arts evade80%; cannon disables30s/stun8s. First arts.5/charge3, rebirth random.3 each.8/charge6, second physical plus arts.5/charge6.','client_verified':False},'requirements':requirements,'runtime_authored':False,'generic_gap_proven_by_actual_counter':False,'simulation_created':False,'model_or_whole_approved':False}
    path=OUT/'manfred.requirements.draft.v1.json';assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'path':str(path),'sha256':sha(path),'owned_components':len(owned),'BSON_templates':len(template_rows),'runtime_authored':False}))
if __name__=='__main__':main()

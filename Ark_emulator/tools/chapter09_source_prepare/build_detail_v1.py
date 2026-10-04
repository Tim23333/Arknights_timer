"""Exact critical callgraphs, prefix-separated BB and native animation remaps."""
import json,hashlib
from pathlib import Path
from tools.extract_campaign_animation_bindings import resolve_animation
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'packages/campaign/chapter09_source_prepare'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    enemy=BASE/'enemies.native.v1.json';pre=BASE/'predefines.native.v3.json';e=json.loads(enemy.read_bytes());p=json.loads(pre.read_bytes());mapped=[]
    for vid,v in e['variants'].items():
        key=v['prefab_key'];f=e['prefabs'][key];anim=e['animations'][key];cs=f['components']
        for m in v['modes']:
            hook=cs.get(str(m['raw']['_animatorHooker']['m_PathID']));replacements={x['fromAnimKey']:x['toAnimKey'] for x in hook['raw'].get('_replaceAnimPairs',[]) } if hook else {}
            for role,node in m['nodes'].items():
                original=node.get('raw',{}).get('_animKey')
                if not original:continue
                resolved=replacements.get(original,original)
                try:binding=resolve_animation(resolved,anim['animator']['fields']['_animations'],anim['parsed'])
                except Exception as err:binding={'error':str(err),'status':'explicit_animation_binding_gap'}
                mapped.append({'variant_id':vid,'mode':m['index'],'role':role,'native_node_path':node.get('path_id'),'original_key':original,'hook_replaced_key':resolved,'binding':binding})
    cs=e['prefabs']['enemy_1173_duspfr']['components'];group=cs['3900889880497538338'];deadchildren=[]
    for ptr in group['raw']['_abilities']:
        node=cs[str(ptr['m_PathID'])];selector=node['raw'].get('_selector',{});deadchildren.append({'path_id':ptr['m_PathID'],'node':node,'selector':cs.get(str(selector.get('m_PathID')))})
    attack=cs['5757806308984735010'];flameSkill=next(v for v in e['variants']['enemy_1173_duspfr@0/fcd4019ae131bb64']['native_enemy']['resolved']['skills'] if v['prefabKey']=='Flame')
    sourceBB={vid:{'talent_entries':v['native_enemy']['resolved'].get('talentBlackboard'),'raw_rows':v['native_enemy']['raw_rows'],'selected_resolved_skill_entries':v['native_enemy']['resolved'].get('skills'),'native_reference_override':v['native_reference'].get('overwrittenData'),'policy':'EachTalent/skill/prefix remains distinct. No wholelist merge override or same-suffix aliasing. Methodbody keybinding conflicts are explicit replaceable source consumers.'} for vid,v in e['variants'].items()}
    pillar=next(v for v in p['skill_prefabs']['sktok_dupilr']['components'].values() if v['native_class']=='SpawnTokenOnTileAbility')
    result={'schema':'ark-sim/chapter09-source-detail/v1','source_locks':{str(x):sha(x) for x in (enemy,pre,Path(__file__),ROOT/'tools/extract_campaign_animation_bindings.py')},'animation_remapped_bindings':mapped,'blackboard_prefixes_and_raw_rows':sourceBB,
        'Flame_damage_and_EP':{'native_attack':attack,'source_DB_skill':flameSkill,'reference_parameter_rule':'ATK*atk_scale for healthdamage; ATK*ep_damage_ratio separate packet afterhealthnormal pipeline, thenEP-resistance. Raw_epDamageRatio1 is fallback overwritten by sourceBB. This is documented reference-first assignment; no native Attack.CreateElementDamageNode body proof.', 'selected_numeric':{'atk':500,'damage_scale':.12,'EPscale':.06,'raw_health_beforeRES':60,'raw_EP_beforeResistance':30,'interval_seconds':.5}},
        'deadboom_source_beforezero':{'BSON':e['bson_templates']['templates']['enemy_duspfr_t[deadboom]'],'parallel_group':group,'actual_child_nodes':deadchildren,'policy':'Unsilenced first HPzero is a real source deferral/deadlike3s, not standardalreadydead emit. Fiveparallel children DieAnim/Suicide1.1s/PullDupilr1s/Damage1s/KillDuspfr1s; finiteowned action/lifecycle required, no arbitrary deadactor skill permission. Damage uses ARTSType2 scale1/motionground only; noEPtype. Allyexplosionchain checks marker anddamage100*ATK; exactfalse/noSource suicide flags preserved.'},
        'pillar_spawn_transitive':{'source_spawn_node':pillar,'transitive_characterKey':'trap_044_duruin','source_spawn_preDelay':1.5,'source_spawned_buff_lifetime':.5,'policy':'Do not inventenemy1176or temporarytime life. Spawnedstone HP100/block3, actualtile blockers/nativewithdraw rules; lifetime only ifsourceexplicit specified. SourceMapDependentTrap nofixedTTL established.'},
        'semantic_gaps':['Mandraskill Reborntalent invul3 vs selectedRebornskill5 andpillarCD20 vs10 distinctprefix/sourcechannels, not overrideequalname','Mandragora DB branchID named summon_dupilr butnativeLevel branchesnull; inspect actualSpawnTokenOnTile directhelper andLevelBranchTrigger before treating absentbranch as empty','all inlineBuffmissingDB rows notgap unlessloadFromDBtrue; only actualrequiredstun row found','C9normal selectedmask1 ignoresFOUR_STAR/EASYrunes; preserveallraw'], 'runtime_authored':False,'whole_stage_verified':False}
    out=BASE/'source.detail.v1.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()

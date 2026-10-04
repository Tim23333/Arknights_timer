"""Exact boss full raw closure plus source-approved BB overlay and animator-hook resolution."""
import sys,json,hashlib,re
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.extract_campaign_animation_bindings import resolve_animation
BASE=ROOT/'packages/campaign/chapter08_source_prepare/integration'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 enemy=BASE/'enemies.native.v1.json';pre=BASE/'predefines.native.v2.json';plan=BASE/'source.plan.v1.json';e=json.loads(enemy.read_bytes());p=json.loads(plan.read_bytes());v=next(v for k,v in e['variants'].items() if 'bsnake' in k);prefab=e['prefabs']['enemy_1515_bsnake'];root=next(c for c in prefab['components'].values() if c['native_class']=='Enemy');assert len(root['raw']['_modes'])==len(v['modes'])==4;baseBB={};
 for row in v['native_enemy']['raw_rows']:
  for item in row['enemyData'].get('talentBlackboard') or []:baseBB[item['key']]=deepcopy(item)
 merged=deepcopy(baseBB)
 for item in v['native_reference']['overwrittenData']['talentBlackboard']:merged[item['key']]=deepcopy(item)
 assert len(baseBB)==10 and len(merged)==12;animator=next(c['raw'] for c in prefab['components'].values() if c['native_class']=='SingleSpineAnimator');resolved=[]
 for mode in v['modes']:
  hooker=prefab['components'][str(mode['raw']['_animatorHooker']['m_PathID'])];replacements={x['fromAnimKey']:x['toAnimKey'] for x in hooker['raw']['_replaceAnimPairs']};row={'index':mode['index'],'raw':mode,'hooker':hooker,'resolved_animations':{}}
  for role,node in mode['nodes'].items():
   if node.get('raw',{}).get('_animKey'):
    original=node['raw']['_animKey'];key=replacements.get(original,original);row['resolved_animations'][role]=resolve_animation(key,animator['_animations'],e['animations']['enemy_1515_bsnake']['parsed'])
  resolved.append(row)
 reb=next(c for c in prefab['components'].values() if c['native_class']=='RebornTalent');frames={k:e['animations']['enemy_1515_bsnake']['parsed']['animations'][k] for k in ['Attack_A','Attack_B','Reborn_1_Start','Reborn_1_Idle','Reborn_1_End','Reborn_2_Start','Reborn_2_Idle','Reborn_2_End','Skill_3']};stage=p['stages']['level_main_08-17'];rawhint=merged['hint.location']['valueStr'];hints=[[(int(a),int(b)) for a,b in re.findall(r'\((\d+),(\d+)\)',segment)] for segment in rawhint.split('_')];pred=json.loads(pre.read_bytes());aliases={tuple([r['raw_native']['position']['row'],r['raw_native']['position']['col']]):r['raw_native']['alias'] for r in pred['stages']['level_main_08-17']['instances']};assert len(hints)==7 and all(len(x)==5 for x in hints) and all(x in aliases for hs in hints for x in hs);hintaliases=[[aliases[x] for x in hs] for hs in hints]
 out=ROOT/'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json';assert not out.exists();result={'schema':'ark-sim/ch8-bsnake-source-closure/v1','variant':v,'root':root,'prefab':prefab,'animation_source':e['animations']['enemy_1515_bsnake'],'source_modes_count':4,'source_hook_resolved_modes':resolved,'frames':frames,'base_BB10':baseBB,'stage_override_only2':v['native_reference']['overwrittenData']['talentBlackboard'],'consumer_merged_BB12':merged,'BB_merge_policy':'Keywise explicit reference preserving base10 plus stage2 hints, approved byRoot. Frozen parent resolved lists remain unchanged; not a new native methodbody proof.','RebornTalent':reb,'BSON':e['bson_templates'],'projectile_bsnake':e['projectiles']['projectile_enemy_bsnake'],'ten_flame_source':pred,'native_stage_document':stage['native_document'],'hint_sets7x5_native_row_col':hints,'hint_alias_sets7x5':hintaliases,'hint_policy':'Native position pair row,col confirmed exact10predefines positions; renderer/frame/timing nativebody notrecovered. Hintdoesnotspawn fakeactors or damage.','pending_true_generic_profiles':['Reborn spec restore_ratio0 finalpreset currently forbidden: exactreference finalzero health waiting+screen afterlife mustcounter beforeanycore extension','Bsnake screen map-row launcher geometry/startRNG interpreted reference; PP sameauthsource/noactorposition edits','onBegin trigger inactive ScreenAttackAnimation mustrespectactualowned callback permissions, no fakeHP active'], 'source_locks':{str(x):sha(x) for x in [enemy,pre,plan,Path(__file__),ROOT/'tools/extract_campaign_animation_bindings.py',ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs']},'runtime_authored':False,'whole_stage_executed':False};out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':sha(out),'modes':4,'BB':len(merged),'hint_groups':len(hints),'normal_frames':[m['resolved_animations'].get('_attack',{}).get('events') for m in resolved[:2]]}))
if __name__=='__main__':main()

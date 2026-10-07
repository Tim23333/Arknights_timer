"""Exact offline native11 closure; runtime and old projected levels are excluded."""
import argparse,base64,copy,hashlib,json,sys,traceback
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter07.native_assets_v1 import NativeAssets,find_templates,bson_source,story_source
from tools.build_chapter02_enemy_sources import geometry_source,exact_shared_skeleton
from tools.build_mainline_00_11_sources import animation_sources
from tools.extract_campaign_animation_bindings import resolve_animation,library_identity,character_bindings
from tools.normalize_campaign_operators import load_sources
from tools.build_mainline_dependencies import DEFAULT_DB
PLAN=ROOT/'packages/campaign/chapter11_source_prepare/source.plan.v1.json';PIN='db510b260c64266315fd22ea2a5f2708434089d4be4272e9afb4c7dc148c6518'
OUTPUT=ROOT/'packages/campaign/chapter11_source_prepare';REPORT=ROOT/'validation/campaign/chapter11_source_prepare'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,value):
    path=OUTPUT/name
    if path.exists():raise FileExistsError('Preserve existing source output: '+str(path))
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return {'relative_path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size}
def index(paths,wanted=None):
    import UnityPy
    found={}
    for path in sorted(paths):
        if path.name.endswith('.resS'):continue
        for obj in UnityPy.load(str(path)).objects:
            if obj.type.name=='GameObject':
                key=obj.read().m_Name
                if wanted is None or key in wanted:found.setdefault(key,[]).append(path)
    return found
def scan(value,templates,projectiles,spawns,path='source'):
    if isinstance(value,dict):
        if value.get('templateKey'):templates.add(value['templateKey'])
        if value.get('key')=='projectile' and value.get('valueStr'):projectiles.add(value['valueStr'])
        for key,v in value.items():
            if key in ('_projectileKey','projectileKey','_projectilePrefabKey','_projectileToEmit','_projectileToSpawn') and isinstance(v,str) and v:projectiles.add(v)
            if key in ('_enemyKey','_characterKey','_unitKey','_tokenKey') and isinstance(v,str) and v:spawns.append({'path':path+'.'+key,'key':v})
            if key=='SerializedState' and isinstance(v,str) and v:scan(json.loads(v),templates,projectiles,spawns,path+'.decodedSerializedState')
            else:scan(v,templates,projectiles,spawns,path+'.'+key)
    elif isinstance(value,list):
        for i,v in enumerate(value):scan(v,templates,projectiles,spawns,path+'['+str(i)+']')
class Extractor:
    def __init__(self):
        self.assets=NativeAssets();self.templates=set();self.projectiles=set();self.spawns=[];self.locks={PLAN.relative_to(ROOT.parent).as_posix():PIN};self.gaps=[]
    def collect(self,value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):self.locks[value['path']]=value['sha256']
            for v in value.values():self.collect(v)
        elif isinstance(value,list):
            for v in value:self.collect(v)
    def closure(self,key,paths,kind):
        paths=list(dict.fromkeys(paths))
        if len(paths)!=1:
            gap={'kind':kind,'key':key,'status':'missing_or_ambiguous_exact_native_asset','candidate_paths':[str(p) for p in paths]};self.gaps.append(gap);return gap
        value=self.assets.closure(paths[0],key);value['geometry_sources']=geometry_source(self.assets,value)
        scan(value['components'],self.templates,self.projectiles,self.spawns,kind+'/'+key);self.collect(value);return value
    def enemy(self,plan):
        variants=copy.deepcopy(plan['variants']);keys={v['native_enemy']['resolved']['prefabKey'] for v in variants.values()};branches=[]
        for name,s in plan['stages'].items():
            refs={v['native_enemy']['native_id'] for v in variants.values() if v['variant_id'] in s['variant_ids']}
            for branch,body in (s['native_document'].get('branches') or {}).items():
                for pi,phase in enumerate(body['phases']):
                    for ai,a in enumerate(phase['actions']):
                        if a['actionType']=='SPAWN' and a['key'] not in refs:
                            keys.add(a['key']);branches.append({'stage':name,'branch':branch,'phase':pi,'action':ai,'native':copy.deepcopy(a),'selected_DB_level':None,'resolution_policy':'Exact branch literal; no enemyDbRefs entry, no fabricated DB level0'})
        found=index((ROOT.parent/'data/battle').glob('enm_pfb*.ab_unpacked/CAB-*'),keys);prefabs={};animations={};before=library_identity()
        for key in sorted(keys):
            prefab=self.closure(key,found.get(key,[]),'enemy');prefabs[key]=prefab
            if 'components' not in prefab:animations[key]={'status':'native_prefab_gap'};continue
            path=found[key][0]
            try:
                a=animation_sources({key:{'source':path.relative_to(ROOT.parent).as_posix()}})[key];a['status']='exact_source_bound_spine'
            except (ValueError,KeyError,FileNotFoundError) as error:
                if str(error)=='Skeleton identity differs from selected exact prefab':
                    a=exact_shared_skeleton(key,path,self.assets);a['strict_name_rejection_preserved']=str(error)
                else:a={'status':'exact_animation_gap','error':str(error)};self.gaps.append({'kind':'enemy_animation','key':key,**a})
            animations[key]=a;self.collect(a)
        assert library_identity()==before
        matrix=[]
        for vid,v in variants.items():
            key=v['native_enemy']['resolved']['prefabKey'];prefab=prefabs[key];a=animations[key];modes=[]
            if 'components' in prefab:
                roots=[(pid,c) for pid,c in prefab['components'].items() if '_modes' in c['raw']]
                if len(roots)!=1:raise ValueError('Ambiguous source enemy mode root: '+key)
                v['root_path_id']=roots[0][0]
                for i,pointer in enumerate(roots[0][1]['raw']['_modes']):
                    if pointer['m_FileID'] or not pointer['m_PathID']:
                        modes.append({'index':i,'pointer':pointer,'status':'external_or_native_null_mode_pointer'});continue
                    mode=prefab['components'][str(pointer['m_PathID'])];nodes={}
                    for role in ('_combat','_attack','_attackTrigger'):
                        p=mode['raw'].get(role)
                        if p is None:nodes[role]={'status':'field_absent'};continue
                        if not p['m_PathID']:nodes[role]={'status':'native_null','pointer':p};continue
                        if p['m_FileID']:nodes[role]={'status':'unresolved_external_node','pointer':p};continue
                        node=copy.deepcopy(prefab['components'][str(p['m_PathID'])]);node['path_id']=p['m_PathID'];bindings={}
                        for field in ('_animKey','_endAnimKey','_downAnimKey','_upAnimKey','_endAnim','_animWithPre','_animNoPre'):
                            if node['raw'].get(field) and a.get('status') in ('exact_source_bound_spine','exact_serialized_pointer_shared_skeleton'):
                                try:bindings[field]=resolve_animation(node['raw'][field],a['animator']['fields']['_animations'],a['parsed'])
                                except (ValueError,KeyError) as error:bindings[field]={'status':'native_binding_gap','error':str(error)}
                        node['animation_bindings']=bindings;nodes[role]=node
                    modes.append({'index':i,'path_id':pointer['m_PathID'],'raw':copy.deepcopy(mode['raw']),'nodes':nodes})
                owned=[{'path_id':pid,'native_class':c['native_class'],'raw':copy.deepcopy(c['raw'])} for pid,c in prefab['components'].items() if any(word in c['native_class'] for word in ('Ability','Skill','Talent','Checker','Selector','Animation'))]
                v['owned_components']=owned
            else:owned=[];v['source_gap']=prefab
            v.update(prefab_key=key,modes=modes,runtime_authored=False)
            matrix.append({'variant_id':vid,'prefab':key,'fixed_native_reference':v['native_reference'],'source_DB':v['native_enemy'],
              'native_owned_classes':dict(Counter(c['native_class'] for c in prefab.get('components',{}).values())),'modes':modes,'owned_components':owned,'animation_status':a.get('status'),'native_methods_recovered':False})
        db=json.loads(DEFAULT_DB.read_bytes());db_rows={b['native']['key']:copy.deepcopy(db.get(b['native']['key'])) for b in branches}
        # DB format may wrap the keyed table; preserve whichever exact record exists.
        if isinstance(db.get('enemies'),list):
            for key in db_rows:db_rows[key]=copy.deepcopy([r for r in db['enemies'] if r.get('Key')==key or r.get('key')==key])
        self.locks[DEFAULT_DB.relative_to(ROOT.parent).as_posix()]=sha(DEFAULT_DB)
        value={'schema':'ark-sim/chapter11-enemy-native-source/v1','variants':variants,'prefabs':prefabs,'animations':animations,'dependency_matrix':matrix,
          'branch_only_spawn_declarations':branches,'branch_only_unselected_DB_records':db_rows,'branch_level_resolution_gap':bool(branches),
          'source_locks':copy.deepcopy(self.locks),'spine_reader_before':before,'spine_reader_after':library_identity(),'runtime_created':False,'client_verified':False,
          'version_policy':'Fixed56 table/level identities and each local native bundle/MonoScript/Spine SHA are independent. No native method bodies or client version equivalence recovered.'}
        return value
    def environment(self,plan):
        keys={tile['tileKey'] for s in plan['stages'].values() for tile in s['native_document']['mapData']['tiles']}
        found=index((ROOT.parent/'data/battle/prefabs').glob('*tiles.ab_unpacked/CAB-*'),keys)
        prefabs={k:self.closure(k,found.get(k,[]),'tile') for k in sorted(keys)}
        return {'schema':'ark-sim/chapter11-environment-native-source/v1','prefabs':prefabs,
          'native_stage_data':{n:{k:copy.deepcopy(s['native_document'].get(k)) for k in ('mapData','routes','extraRoutes','branches','runes','optionalRunes','globalBuffs','options','hardPredefines')} for n,s in plan['stages'].items()},
          'source_locks':copy.deepcopy(self.locks),'typed_empty_null_source_preserved':True,'runtime_created':False,'whole_stage_executed':False}
    def predefines(self,plan):
        chars,skills,table_locks=load_sources();keys={r['inst']['characterKey'] for s in plan['stages'].values() for bucket,values in s['native_document']['predefines'].items() for r in values or []}
        token_paths=list((ROOT.parent/'data/battle/prefabs').glob('*tokens.ab_unpacked/CAB-*'))
        token_index=index(token_paths,keys);prefabs={};animations={};assets={};before=library_identity();stories={};rows={};skill_tables={};skill_prefabs={}
        skill_index=index((ROOT.parent/'data/battle/prefabs').glob('*skills.ab_unpacked/CAB-*'))
        for key in sorted(keys):
            paths=[p for p in (ROOT.parent/'data/charpack'/(key+'.ab_unpacked')).glob('CAB-*') if not p.name.endswith('.resS')]
            if not paths:paths=token_index.get(key,[])
            prefab=self.closure(key,paths,'predefine');prefabs[key]=prefab
            if key.startswith('char_'):
                try:animations[key]=character_bindings(key,assets)
                except (ValueError,KeyError,FileNotFoundError) as error:animations[key]={'status':'explicit_character_spine_gap','error':str(error)};self.gaps.append({'kind':'character_animation','key':key,'error':str(error)})
            self.collect(animations.get(key,{}))
        for name,stage in plan['stages'].items():
            records=[]
            for bucket,values in stage['native_document']['predefines'].items():
                for i,raw in enumerate(values or []):
                    key=raw['inst']['characterKey'];idx=raw['skillIndex'];selected=None
                    if key not in chars:selection={'status':'exact_fixed_character_missing','key':key,'native_skill_index':idx}
                    elif idx==-1:selection={'status':'native_no_selected_skill','native_index':-1}
                    elif type(idx)is int and 0<=idx<len(chars[key].get('skills',[])):
                        sid=chars[key]['skills'][idx]['skillId'];level=raw['mainSkillLvl']
                        if type(level)is not int or not 1<=level<=len(skills[sid]['levels']):raise ValueError('Native skill level outside fixed source: '+key)
                        selected=copy.deepcopy(skills[sid]['levels'][level-1]);skill_tables[sid]=copy.deepcopy(skills[sid]);prefabkey=selected['prefabId']
                        if prefabkey not in skill_prefabs:skill_prefabs[prefabkey]=self.closure(prefabkey,skill_index.get(prefabkey,[]),'skill')
                        selection={'status':'exact_native_selected_fixed_skill','skill_id':sid,'native_skill_index':idx,'native_level':level,'raw_level':selected}
                    else:selection={'status':'invalid_native_skill_index','native_skill_index':idx,'fixed_skill_count':len(chars[key].get('skills',[]))}
                    records.append({'bucket':bucket,'index':i,'raw_native':copy.deepcopy(raw),'fixed_character':copy.deepcopy(chars.get(key)),
                      'skill_selection':selection,'alias_native_type':type(raw['alias']).__name__,'hidden_policy':'Native null alias remains null; requires explicit story ownership binding' if raw['alias'] is None else 'Exact native alias retained'})
            controls=[copy.deepcopy(a) for a in stage['actions'] if a['native']['actionType']!='SPAWN']
            for a in controls:
                if a['native']['actionType']=='STORY':
                    key=a['native']['key'];stories[key]=story_source(key);self.collect(stories[key])
            rows[name]={'native_predefines':copy.deepcopy(stage['native_document']['predefines']),'native_hard_predefines':copy.deepcopy(stage['native_document'].get('hardPredefines')),
              'native_options':copy.deepcopy(stage['options']),'instances':records,'controls':controls,'branches':copy.deepcopy(stage['native_document'].get('branches'))}
        assert library_identity()==before;self.collect(assets)
        return {'schema':'ark-sim/chapter11-predefined-native-source/v1','stages':rows,'prefabs':prefabs,'animations':animations,'animation_assets':assets,
          'fixed_table_sources':table_locks,'skill_tables':skill_tables,'skill_prefabs':skill_prefabs,'stories':stories,'source_locks':copy.deepcopy(self.locks),
          'spine_reader_before':before,'spine_reader_after':library_identity(),'runtime_created':False,'whole_stage_executed':False,'client_verified':False}
    def transitive(self,documents):
        for name,document in documents.items():scan(document,self.templates,self.projectiles,self.spawns,name)
        projectile_index=index((ROOT.parent/'data/battle/prefabs').glob('*projectiles.ab_unpacked/CAB-*'));projectile_sources={};rounds=[]
        for i in range(48):
            templates_before=set(self.templates);proj_before=set(projectile_sources)
            bson=bson_source(self.templates);scan(bson['templates'],self.templates,self.projectiles,self.spawns,'transitiveBSON')
            for key in sorted(self.projectiles-set(projectile_sources)):
                projectile_sources[key]=self.closure(key,projectile_index.get(key,[]),'projectile')
            rounds.append({'round':i,'templates_requested':len(self.templates),'new_templates':sorted(self.templates-templates_before),'new_projectiles':sorted(set(projectile_sources)-proj_before)})
            if self.templates==templates_before and set(projectile_sources)==proj_before:break
        else:raise ValueError('Native string/BSON/projectile closure did not stabilize')
        self.collect(bson);self.collect(self.assets.scripts)
        return {'schema':'ark-sim/chapter11-transitive-native-source/v1','BSON':bson,'projectiles':projectile_sources,'native_monoscripts':self.assets.scripts,
          'closure_rounds':rounds,'spawn_string_dependencies':list({json.dumps(v,sort_keys=True):v for v in self.spawns}.values()),
          'source_locks':copy.deepcopy(self.locks),'gaps':self.gaps,'native_method_bodies_recovered':False,'runtime_created':False}
def main():
    assert sha(PLAN)==PIN;plan=json.loads(PLAN.read_bytes());assert all(sha(p)==h for p,h in plan['source_locks'].items())
    REPORT.mkdir(parents=True,exist_ok=True);extractor=Extractor();outputs=[];docs={}
    for name,fn in [('enemies.native.v1.json',extractor.enemy),('environment.native.v1.json',extractor.environment),('predefines.native.v1.json',extractor.predefines)]:
        print('Extracting '+name,flush=True);docs[name]=fn(plan);outputs.append(write(name,docs[name]));print(json.dumps(outputs[-1]),flush=True)
    closed=extractor.transitive(docs);outputs.append(write('closure.native.v1.json',closed))
    for path,h in extractor.locks.items():assert sha(ROOT.parent/path)==h,path
    assert sha(PLAN)==PIN and all(sha(p)==h for p,h in plan['source_locks'].items())
    receipt={'schema':'ark-sim/chapter11-native-extraction-receipt/v1','source_only':True,'outputs':outputs,'source_locks':extractor.locks,
      'plan_sha256':PIN,'helper_sha256':sha(__file__),'variants':len(docs['enemies.native.v1.json']['variants']),'branch_only_selected_level_gap':docs['enemies.native.v1.json']['branch_level_resolution_gap'],
      'BSON_missing':closed['BSON']['missing_templates'],'gaps':extractor.gaps,'source_guard_current':True,'runtime_created':False,'whole_stage_executed':False,'client_verified':False}
    (REPORT/'extraction.receipt.v1.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'source_only':True,'outputs':len(outputs),'gaps':len(extractor.gaps),'receipt_sha256':sha(REPORT/'extraction.receipt.v1.json')}),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as error:
        REPORT.mkdir(parents=True,exist_ok=True);(REPORT/'extraction.failure.v1.json').write_text(json.dumps({'passed':False,'runtime_created':False,'error':str(error),'traceback':traceback.format_exc()},ensure_ascii=False,indent=2)+'\n',encoding='utf8');raise

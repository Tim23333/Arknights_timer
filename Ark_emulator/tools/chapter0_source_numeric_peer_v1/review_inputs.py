"""Independent typed chapter0 source inputs and consumer projections; no runtime."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter11_source_prepare.review_plan import equal
from tools.build_mainline_dependencies import resolve_enemy,DEFAULT_DB,PIN
def sha(p):
    p=Path(p)
    if not p.is_absolute():p=ROOT.parent/p
    return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    plan=ROOT/'packages/campaign/chapter0_source_prepare/source.plan.v3.json';source=ROOT/'packages/campaign/chapter0_source_prepare/enemies.native.v1.json';module=ROOT/'packages/campaign/chapter0_consumers/enemies.module.v1.json'
    p=json.loads(plan.read_bytes());s=json.loads(source.read_bytes());m=json.loads(module.read_bytes());assert p['chapter']==0 and p['fixed_commit']==PIN
    assert sha(plan)=='b0fde50c99f7f6ddcbc55079b46d822178a5da71f52ab5bc9cc488b54e66c95a' and sha(source)=='ad8a610ad5b3fbebe16a000f5098084accab4a346492dd686e937f22925fe360'
    guards={**p['source_locks'],**s['source_locks']};assert all(sha(k)==h for k,h in guards.items())
    table=json.loads(Path(p['stage_table_identity']['path']).read_bytes())['stages'];selected={k:v for k,v in table.items() if re.fullmatch(r'main_00-\d+',k) and v.get('levelId') and v['difficulty']=='NORMAL'}
    last=sorted(selected,key=lambda k:int(k.rsplit('-',1)[1]))[-2:];assert last==[r['native_id'] for r in p['targets']]==['main_00-10','main_00-11'];db=json.loads(DEFAULT_DB.read_bytes());stages=[]
    for target in p['targets']:
        equal(target['fixed_stage_row'],selected[target['native_id']]);level=target['level_asset'];stored=p['stages'][level];raw=json.loads((ROOT/'packages/campaign/native_reference'/(level+'.json')).read_bytes());equal(stored['native_document'],raw);equal(stored['options'],raw['options'])
        assert len(stored['variant_ids'])==len(raw['enemyDbRefs'])
        for ref,vid in zip(raw['enemyDbRefs'],stored['variant_ids']):equal(p['variants'][vid]['native_reference'],ref);equal(p['variants'][vid]['native_enemy'],resolve_enemy(db,ref))
        actions=[{'wave':wi,'fragment':fi,'action':ai,'native':a} for wi,w in enumerate(raw['waves']) for fi,f in enumerate(w['fragments']) for ai,a in enumerate(f['actions'])];assert len(actions)==len(stored['actions'])
        for a,b in zip(actions,stored['actions']):equal(a,{k:b[k] for k in a})
        pre=[{'bucket':k,'index':i,'native_record':v} for k,values in raw['predefines'].items() for i,v in enumerate(values or [])];equal(pre,stored['predefine_records'])
        stages.append({'level':level,'actions':len(actions),'born':sum(a['native']['count'] for a in actions if a['native']['actionType']=='SPAWN'),'predefine_types':{k:type(v).__name__ for k,v in raw['predefines'].items()},'full_native_document_typed_equal':True})
    projections=[]
    assert len(m['entities'])==len(s['variants'])==8
    for vid,v in s['variants'].items():
        equal(v['native_reference'],p['variants'][vid]['native_reference']);equal(v['native_enemy'],p['variants'][vid]['native_enemy']);key=v['prefab_key'];e=next(e for e in m['entities'] if e['id']=='unit/ch0/'+key);equal(e['metadata']['native_variant'],v)
        root=s['prefabs'][key]['components'][str(v['root_path_id'])]['raw'];equal(e['metadata']['root_component'],root);assert len(v['modes'])==1 and root['_commonAbilities']==[] and v['modes'][0]['raw']['_generalAbilities']==[]
        attrs=v['native_enemy']['resolved']['attributes'];base=e['components']['attributes']['base'];expected={'max_hp':attrs['maxHp'],'atk':attrs['atk'],'def':attrs['def'],'mres':attrs['magicResistance'],'move_speed':attrs['moveSpeed'],'attack_speed_ratio':attrs['attackSpeed']/100,'attack_interval':attrs['baseAttackTime'],'mass_level':attrs['massLevel'],'block_cost':root['_blockVolume']};equal(base,expected)
        node=v['modes'][0]['nodes']['_combat'];owned=e['components']['abilities'];assert e['components']['lifecycle']['leak_loss']==v['native_enemy']['resolved']['lifePointReduce']
        if node['native_class']=='MeleeAttack':
            a=next(a for a in m['abilities'] if a['id']==owned[0]);equal(a['metadata']['native_owned_node'],node);binding=node['animation_binding'];hit=next(x for x in binding['events'] if x['name']=='OnAttack');assert a['timeline'][0]['at_seconds']==hit['seconds'] and a['duration_seconds']==binding['duration']['seconds'] and a['timeline'][0]['effect']['scale']==node['raw']['_atkScale'];assert a['activation']['interval_seconds']==attrs['baseAttackTime']
        else:assert node['native_class']=='EmptyAnimatedAbility' and not owned and attrs['atk']==0 and v['modes'][0]['nodes']['_attack']['status']==v['modes'][0]['nodes']['_attackTrigger']['status']=='native_null'
        projections.append({'variant':vid,'native_combat':node['native_class'],'exact_owned_node_retained':True,'owned_abilities':owned,'all_base_fields_equal':True})
    assert all(sha(k)==h for k,h in guards.items());out=ROOT/'validation/campaign/chapter0_source_numeric_peer_v1/source.inputs.review.v1.json';out.parent.mkdir(parents=True,exist_ok=True)
    result={'schema':'ark-sim/chapter0-independent-input-review/v1','passed':True,'plan_sha256':sha(plan),'source_sha256':sha(source),'module_sha256':sha(module),'stages':stages,'variants':projections,'source_guards':guards,'current_guards_equal':True,
      'source_and_reference_policy':{'source':'Exact native attributes, modes, node, hit/full frames, base interval and flyer null attack nodes retained','reference':'blocked_only/alive/player selection, category=1/unit_type=2 and stun immune index0 are explicit model projections; native selection tie timing and broad immunity/client behavior unverified'},'runtime_ready_claim':False,'whole_stage':False,'client_verified':False,'reviewer_sha256':sha(__file__)}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'report_sha256':sha(out)}))
if __name__=='__main__':main()

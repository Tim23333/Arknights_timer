import json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter02_03_refjoin_v1'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=read(OUT/'preparation.json');results=[]
for item in report['results']:
 stage=item['stage'];p=read(Path(item['native_package']));scene=p['scenarioDraft'];defs={d['id']:d for d in p['definitions']}
 if stage=='02-10':
  sourcefile=ROOT/'packages/campaign/chapter02_sources/native.reference.json';source=read(sourcefile)
  nativefile=ROOT/'packages/campaign/native_reference/level_main_02-10.json';native=read(nativefile)
  bindingfile=ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.combat_guard.reference_module.json';bindings=read(bindingfile)['manifest']['metadata']['variant_bindings']
 else:
  sourcefile=ROOT/'packages/campaign/chapter03_plans/source.plan.json';source=read(sourcefile);nativefile=sourcefile;native=source['stages']['level_main_03-08']['native_document'];bindingfile=Path(item['native_package']);bindings=p['manifest']['metadata']['variant_bindings']
 HP=[]
 for b in bindings:
  variant=source['variants'][b['variant_id']];assert b['native_reference']==variant['native_reference'];assert b['native_reference'] in native['enemyDbRefs']
  attrs=variant['native_enemy']['resolved']['attributes'];definition=defs[b['unit_definition']];actual=definition['components']['resources']['hp']['initial'];assert actual==attrs['maxHp'],(stage,b['variant_id'],actual,attrs['maxHp'])
  assert definition['components']['attributes']['base']['max_hp']==attrs['maxHp']
  HP.append({'variant_id':b['variant_id'],'native_reference':b['native_reference'],'source_hp':attrs['maxHp'],'definition':b['unit_definition'],'actual_hp':actual})
 route_count=0;source_actions=0
 for wi,wave in enumerate(scene['timeline']['waves']):
  for fi,fragment in enumerate(wave['fragments']):
   for action in fragment['actions']:
    m=action['metadata'];ai=m['native_action_index'];raw=native['waves'][wi]['fragments'][fi]['actions'][ai];assert m['native_action']==raw;source_actions+=1
    if action['kind']!='spawn':continue
    route=deepcopy(native['routes'][raw['routeIndex']]);rows=scene['map']['rows']
    for k in ['startPosition','endPosition']:route[k]={'row':rows-1-route[k]['row'],'col':route[k]['col']}
    route['checkpoints']=route.get('checkpoints') or []
    for c in route['checkpoints']:
     if c.get('position') is not None:c['position']={'row':rows-1-c['position']['row'],'col':c['position']['col']}
    actual=action['spawn']['route']
    for k in route:
     if k!='motionMode':assert actual[k]==route[k],(stage,k,actual[k],route[k])
    assert actual['motionMode'] in ['WALK','FLY'];route_count+=1
 assert all(not x['active'] for x in scene['metadata']['rune_policy'])
 assert not any((native['predefines'] or {}).values()) and not any((native['hardPredefines'] or {}).values()) and scene['initialEntities']==[]
 results.append({'stage':stage,'passed':True,'source_file':str(sourcefile),'source_sha':sha(sourcefile),'native_file':str(nativefile),'native_sha':sha(nativefile),'binding_file':str(bindingfile),'binding_sha':sha(bindingfile),'hp':HP,'source_action_rows':source_actions,'route_rows':route_count,'normal_difficulty_runes_inactive':True,'native_predefines_empty':True,'movement_multiplier':native['options']['moveMultiplier'],'policy':'Coordinate reversal only; motionMode explicitly resolved from exact variant. Raw wave action, checkpoints,offsets and source HP verified; native method bodies remain source/reference policies, no V1 runtime delegation.'})
with (OUT/'native_audit.json').open('x',encoding='utf8') as f:json.dump({'results':results,'helper_sha':sha(Path(__file__))},f,ensure_ascii=False,indent=2)
print(json.dumps({'results':[{k:v for k,v in x.items() if k!='hp'} for x in results],'sha':sha(OUT/'native_audit.json')}))

"""New content-only revision: INPUT_TARGET2 is eligibility, never finite score priority."""
import argparse,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.reference_module.json';PIN='bf13eb78c7b81dd0727c60f3d88d4f7d09a5244c6cfb9dad1e959ad0c5dd3859';OUT=ROOT/'packages/campaign/chapter02_units/main_02-10.enemies.combat_guard.reference_module.json';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 raw=PARENT.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Frozen bf13 parent drift')
 p=json.loads(raw);definitions={d['id']:d for d in p['definitions']};bound=[]
 for row in p['manifest']['metadata']['variant_bindings']:
  modes=row['source_modes']
  if len(modes)!=1:continue
  combat=modes[0]['nodes'].get('_combat') or {};raw=combat.get('raw') or {}
  if combat.get('native_class') not in ['RangedAttack','MeleeAttack'] or raw.get('_selectTargetSource')!=2:continue
  for ident in row['owned_abilities']:
   ability=definitions[ident]
   if ability.get('rules',{}).get('targeting.score')!='rule/ch2_10/combat_priority':continue
   selector=definitions[ability['selector']]
   if selector.get('eligibility',{}).get('rule')!='rule/chapter02/qualification':raise ValueError('Expected source eligibility closure')
   selector['eligibility']['rule']='rule/ch2_10/combat_target_guard';selector.setdefault('metadata',{})['combat_target_guard']={'source_combat':combat,'semantics':'Existing blocked_by restricts qualified candidates to that actor; no geometry/filter/free bypass and no fallback to another target'};bound.append({'variant_id':row['variant_id'],'ability':ident,'selector':selector['id'],'source_combat':combat})
 if len(bound)!=3:raise ValueError('Exactly three explicitly source-bound combat consumers required')
 parameters=[{'name':name,'input':'inputs.'+name} for name in ['source','candidate','selector','selection_states','parameters']]
 p['definitions'].append({'id':'rule/ch2_10/combat_target_guard','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'graph','nodes':[{'id':'source_options','rule':'rule/chapter02/qualification','inputs':{x['name']:x['input'] for x in parameters}},{'id':'result','expression':"{'accepted':nodes.source_options.accepted and ('blocked_by' not in inputs.source.components.runtime or inputs.source.components.runtime.blocked_by == None or inputs.source.components.runtime.blocked_by == inputs.candidate.id),'reason':nodes.source_options.reason if nodes.source_options.accepted == False else 'combat_input_target2'}"}],'output':'nodes.result'},'metadata':{'profile':'Source-bound INPUT_TARGET2 qualifies the actual existing blocker independently of taunt magnitude; original filters/geometry/source-options still apply'}})
 score=definitions['rule/ch2_10/combat_priority'];score['implementation']['expression']="0 if 'blocked_by' in inputs.source.components.runtime and inputs.source.components.runtime.blocked_by != None else -100000 * (inputs.candidate.components.attributes.base.taunt_level if 'taunt_level' in inputs.candidate.components.attributes.base else 0) + inputs.distance";score['metadata']['profile']='Blocked mode uses candidate identity eligibility; unblocked base-taunt/distance/ID is declared comparator, no finite blocked priority weight'
 meta=p['manifest']['metadata'];meta.update(parent_combat_module_sha256=PIN,combat_guard_builder_sha256=sha(__file__),combat_guard_bindings=bound,combat_guard_policy='Only the three raw source INPUT_TARGET2 consumers; boss/player/other abilities unchanged');meta['source_locks'][str(PARENT.relative_to(ROOT))]=PIN;p['manifest']['id']+='/combat_guard'
 from tools.campaign_content_composition import reachable_content
 scene={'id':'scene/closure/combat_guard','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':30,'cols':20},'initialEntities':[{'definition':r['unit_definition'],'position':{'row':i*2,'col':1}} for i,r in enumerate(meta['variant_bindings'])]}
 rebuilt,report=reachable_content(scene,[('source_bound_combat_guard',p)],manifest_id=p['manifest']['id']);rebuilt.pop('scenarioDraft')
 meta['parent_composition']=meta.pop('composition');meta['composition']=report;rebuilt['manifest']['metadata']=meta
 p=rebuilt
 return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode()
 if a.check:
  if OUT.read_bytes()!=raw:raise ValueError('Combat guard module drift')
 else:OUT.write_bytes(raw)
 print(json.dumps({'passed':True,'sha256':sha(OUT),'bindings':len(p['manifest']['metadata']['combat_guard_bindings'])}))

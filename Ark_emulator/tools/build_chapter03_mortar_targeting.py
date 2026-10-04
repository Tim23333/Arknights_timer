"""New reference-targeting revision; original source/7b7e model stay frozen."""
from pathlib import Path
from copy import deepcopy
import argparse,json,hashlib
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT/'packages/campaign/chapter03_models/mortar.reference.json';PIN='7b7e9e45afb5441f151bf99c7b5c6613d90e6a6e87beffa2ce38da37059a8ae5';OUT=ROOT/'packages/campaign/chapter03_models/mortar.targeting.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def graph_rule(ident,expression):
 return {'id':ident,'kind':'rule','contract':'targeting.eligibility','implementation':{'type':'graph','nodes':[{'id':'source_options','rule':'rule/ch3/mortar/eligibility','inputs':{k:'inputs.'+k for k in ('source','candidate','selector','selection_states','parameters')}},{'id':'result','expression':expression}],'output':'nodes.result'}}
def build():
 if sha(PARENT)!=PIN:raise ValueError('frozen Mortar source profile drift')
 p=json.loads(PARENT.read_bytes());normal=p['selectors'][0];normal['eligibility']['rule']='rule/ch3/mortar/reference_blocker'
 p['rules'].append(graph_rule('rule/ch3/mortar/reference_blocker',"{'accepted':nodes.source_options.accepted and ('blocked_by' not in inputs.source.components.runtime or inputs.source.components.runtime.blocked_by == None or inputs.source.components.runtime.blocked_by == inputs.candidate.id),'reason':nodes.source_options.reason if nodes.source_options.accepted == False else 'reference_first_blocker'}"))
 # Blocked priority uses actual eligibility, independent of magnitude of taunt.
 p['rules'].append({'id':'rule/ch3/mortar/reference_score','kind':'rule','contract':'targeting.score','implementation':{'type':'expression','expression':"inputs.distance - 100000 * (inputs.candidate.components.attributes.base.taunt_level if 'taunt_level' in inputs.candidate.components.attributes.base else 0)"},'metadata':{'policy':'Declared base integer taunt ordering within radius7, distance/ID tie-break; arbitrary fractional or live modified taunt needs replacement scoring rule'}})
 p['abilities'][0]['rules']={'targeting.score':'rule/ch3/mortar/reference_score'}
 obstacle=deepcopy(normal);obstacle['id']='selector/ch3/mortar/obstacle';obstacle['region']={'type':'all','blocked_only':True};obstacle['filters']=[{'state':'alive'}];obstacle['eligibility']['rule']='rule/ch3/mortar/eligibility';obstacle['eligibility']['parameters']['source_configuration']['_targetCategory']=4;p['selectors'].append(obstacle)
 special=deepcopy(next(r for r in p['rules'] if r['id']=='rule/ch3/mortar/area'));special['id']='rule/ch3/mortar/obstacle_area';special['dependencies']=['rule/ch3/mortar/obstacle_members'];special['parameters']['eligibility']['rule']='rule/ch3/mortar/obstacle_members';special['parameters']['eligibility']['parameters']['source_configuration']['_targetCategory']=5;p['rules'].append(special)
 p['rules'].append(graph_rule('rule/ch3/mortar/obstacle_members',"{'accepted':nodes.source_options.accepted and (inputs.selection_states.candidate.category == 1 or (inputs.selection_states.candidate.category == 4 and inputs.candidate.id == ctx.target.id)),'reason':nodes.source_options.reason if nodes.source_options.accepted == False else 'captured_obstacle_primary_or_default_splash'}"))
 ability=deepcopy(p['abilities'][0]);ability['id']='ability/ch3/mortar/obstacle';ability['selector']=obstacle['id'];ability['timeline'][0]['effect']['membership_rule']=special['id'];p['abilities'].append(ability);p['entities'][0]['components']['abilities'].append(ability['id'])
 meta=p['manifest']['metadata'];meta.update(parent_module_sha256=PIN,targeting_builder_sha256=sha(Path(__file__)),reference_targeting={'checked_date':'2026-10-03','references':['https://prts.wiki/w/%E7%82%AE%E6%89%8B','https://prts.wiki/w/%E6%98%8E%E6%97%A5%E6%96%B9%E8%88%9F%E9%BB%91%E8%AF%9D%C2%B7%E6%A2%97%C2%B7%E6%88%90%E5%8F%A5/%E6%9C%BA%E5%88%B6%E7%9B%B8%E5%85%B3/%E8%B0%83%E7%AE%B1%E5%B8%88'],'support':'Default enemy first-blocker then taunt; blocked/path-enclosed enemies attack obstacle. These are reference statements, not recovered source method bodies.'})
 meta['source_locks'][str(PARENT.relative_to(ROOT))]=PIN;meta['profiles']['dispatch']+='; reference blocker eligibility guard; distinct category4-only existing blocked relation consumer'
 meta['profiles']['obstacle']='Same raw RangedAttack/FROM_OWNER1/f16, one captured projectile blast. Primary exception admits only captured category4; surrounding category4 excluded; splash still category1/ground+fly and source Hit status requirements.'
 meta['feedback_pending'] += ['Reference obstacle primary exception versus raw Hit targetCategory1; IBuil­dable handling flag1 is source evidence of special handling but body not recovered','Fractional/live-modified taunt scoring can be replaced; base integer taunt comparator current declaration','M56 known stale route-obstacle callback defect not exercised by native crate with no extra callback; no formal core obstacle promotion']
 p['manifest']['id']+='/reference_targeting';return p
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
 if args.check:
  if OUT.read_bytes()!=raw:raise ValueError('stale Mortar targeting revision')
 else:OUT.write_bytes(raw)
 print(json.dumps({'sha256':sha(OUT)}))

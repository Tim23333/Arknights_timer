"""Opt-in behavior decisions, including optional pure declared tile candidates."""
from collections.abc import Mapping
from ark_sim.contracts import thaw
def validate_config(config):
 if not isinstance(config,Mapping) or set(config)-{'rule','mode_resource','default_mode','profiles'}:raise ValueError('behavior decision unknown fields')
 if not isinstance(config.get('rule'),str) or not config['rule']:raise ValueError('behavior decision rule ID required')
 if 'mode_resource' in config:
  if not isinstance(config['mode_resource'],str) or not config['mode_resource'] or 'default_mode' in config:raise ValueError('mode_resource requires nonempty name and cannot fallback to default_mode')
 elif type(config.get('default_mode')) is not int:raise ValueError('decision without mode resource requires explicit integer default_mode')
 profiles=config.get('profiles')
 if not isinstance(profiles,(list,tuple)) or not profiles:raise ValueError('decision requires nonempty profiles')
 modes=set()
 for p in profiles:
  if not isinstance(p,Mapping) or set(p)-{'mode','selectors','cast_groups','parameters'} or type(p.get('mode')) is not int or p['mode'] in modes:raise ValueError('decision profile requires unique integer mode')
  modes.add(p['mode'])
  keys=set()
  for s in p.get('selectors',[]):
   if not isinstance(s,Mapping) or set(s)!={'key','selector'} or not isinstance(s['key'],str) or not s['key'] or s['key'] in keys or not isinstance(s['selector'],str) or not s['selector']:raise ValueError('decision selector key/reference invalid or duplicated')
   keys.add(s['key'])
  groups=set()
  for g in p.get('cast_groups',[]):
   if not isinstance(g,Mapping) or set(g)!={'key','abilities'} or not isinstance(g['key'],str) or not g['key'] or g['key'] in groups or not isinstance(g['abilities'],(list,tuple)) or not all(isinstance(x,str) and x for x in g['abilities']):raise ValueError('decision cast group invalid')
   groups.add(g['key'])
  params=p.get('parameters',{})
  if not isinstance(params,Mapping):raise ValueError('decision profile parameters require record')
 if 'default_mode' in config and config['default_mode'] not in modes:raise ValueError('default mode must name a declared profile')

def facts(ctx,ref,config,state):
 if 'mode_resource' in config:
  resources=ctx.get(ref,('resources',),{})
  if config['mode_resource'] not in resources:raise ValueError('behavior mode resource is absent')
  mode=resources[config['mode_resource']]['current']
  if type(mode) not in (int,float) or int(mode)!=mode:raise ValueError('behavior mode resource must be integral numeric (not bool)')
  mode=int(mode)
 else:mode=config['default_mode']
 profiles=[p for p in config['profiles'] if p['mode']==mode]
 if len(profiles)!=1:raise ValueError('behavior mode has no declared profile')
 profile=profiles[0];runtime=ctx.get(ref,('runtime',),{});casts=runtime.get('casts',{})
 selectors={s['key']:ctx.spatial.eligible(ref,s['selector']) for s in profile.get('selectors',[])}
 groups={g['key']:[c['id'] for c in casts.values() if c['ability'] in g['abilities']] for g in profile.get('cast_groups',[])}
 tile_candidates={}
 for aid in ctx.get(ref,('abilities',),[]):
  ability=ctx.program.definitions[aid]
  if ability.get('tile_selector'):
   from .tile_targets import query
   tile_candidates[aid]=query(ctx,ref,ability['tile_selector'])[:ability['tile_selector']['limit']]
 return {'tile_candidates':tile_candidates,'source':ctx.entity(ref),'state':state,'mode':mode,'casts':casts,'cast_groups':groups,
   'next_attack':runtime.get('next_attack',0),'blocked_by':ctx.spatial.blocked_by(ref),
   'visibility':{'alive':ctx.alive(ref),'active':ctx.active(ref),'hidden':ctx.route_hidden(ref)},
   'controls':ctx.buffs.controls(ref),'clock':{'time':ctx.session.time,'quantum':ctx.session.quantum},
   'eligible_ids':selectors,'parameters':thaw(profile.get('parameters',{}))}

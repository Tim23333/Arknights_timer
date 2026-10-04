"""Explicit pure placement connectivity over protected original route cells."""
from collections import deque
from collections.abc import Mapping
from ark_sim.contracts import thaw
from .spatial import project_cell


def validate_profile(profile):
    if not isinstance(profile,Mapping) or set(profile)!={'rule','parameters'}:
        raise ValueError('deployment connectivity requires exact rule and parameters')
    if not isinstance(profile['rule'],str) or not profile['rule'] or not isinstance(profile['parameters'],Mapping):
        raise ValueError('deployment connectivity requires rule ID and parameter mapping')


def cell(value,rows,cols):
    if not isinstance(value,Mapping) or set(value)!={'row','col'} or any(type(value[k]) is not int for k in value):
        raise ValueError('connectivity cell requires integer row and col')
    result=(value['row'],value['col'])
    if not 0<=result[0]<rows or not 0<=result[1]<cols:raise ValueError('connectivity cell outside grid')
    return result


def validate_routes(routes,rows,cols):
    if not isinstance(routes,(list,tuple)) or not routes:raise ValueError('connectivity requires explicit original ground deployment_routes')
    seen=set()
    for route in routes:
        if not isinstance(route,Mapping) or set(route)!={'id','start','end'} or not isinstance(route['id'],str) or not route['id'] or route['id'] in seen:
            raise ValueError('connectivity routes require unique ID and exact start/end cells')
        seen.add(route['id']);cell(route['start'],rows,cols);cell(route['end'],rows,cols)


def validate_options(options):
    if not isinstance(options,Mapping) or set(options)!={'diagonal','allow_corner_cut'} or any(type(v) is not bool for v in options.values()):
        raise ValueError('connectivity provider requires explicit boolean diagonal/corner policies')


def ground_routes(inputs,params,context):
    """No World access, costs, random draws or unmentioned path exemptions."""
    options={**thaw(params),**thaw(inputs['parameters'])};validate_options(options)
    grid=inputs['grid']
    if not isinstance(grid,Mapping) or set(grid)!={'rows','cols','walkable','tiles'}:
        raise ValueError('connectivity grid snapshot fields invalid')
    rows,cols=grid['rows'],grid['cols']
    if type(rows) is not int or type(cols) is not int or rows<=0 or cols<=0:raise ValueError('connectivity grid dimensions invalid')
    walking=grid['walkable']
    if not isinstance(walking,(list,tuple)) or len(walking)!=rows*cols or any(type(v) is not bool for v in walking):
        raise ValueError('connectivity walkable cells must be explicit booleans')
    if not isinstance(grid['tiles'],(list,tuple)) or len(grid['tiles'])!=rows*cols:raise ValueError('connectivity tile snapshot count invalid')
    validate_routes(inputs['routes'],rows,cols)
    if not isinstance(inputs['occupied'],(list,tuple)):raise ValueError('connectivity occupied cells must be an array')
    closed={cell(c,rows,cols) for c in inputs['occupied']};closed.add(cell(inputs['proposed'],rows,cols))
    def allowed(p):return 0<=p[0]<rows and 0<=p[1]<cols and walking[p[0]*cols+p[1]] and p not in closed
    directions=[(-1,0),(0,-1),(0,1),(1,0)]
    if options['diagonal']:directions += [(-1,-1),(-1,1),(1,-1),(1,1)]
    for route in inputs['routes']:
        start=cell(route['start'],rows,cols);end=cell(route['end'],rows,cols)
        queue=deque([start]) if allowed(start) else deque();visited={start} if queue else set()
        while queue and end not in visited:
            r,c=queue.popleft()
            for dr,dc in directions:
                p=(r+dr,c+dc)
                if p in visited or not allowed(p):continue
                if dr and dc and not options['allow_corner_cut'] and (not allowed((r+dr,c)) or not allowed((r,c+dc))):continue
                visited.add(p);queue.append(p)
        if end not in visited:return {'accepted':False,'reason':'sealed_route:'+route['id']}
    return {'accepted':True,'reason':'original_ground_routes_connected'}


def validate_scenario(definitions,scene):
    profiles=[]
    for definition in definitions.values():
        profile=definition.get('components',{}).get('deployable',{}).get('connectivity')
        if profile is not None:profiles.append(profile)
    def visit(value):
        if isinstance(value,Mapping):
            profile=value.get('components',{}).get('deployable',{}).get('connectivity')
            if profile is not None:profiles.append(profile)
            for key,child in value.items():
                if key not in ('metadata','parameters','payload','inputs','map'):visit(child)
        elif isinstance(value,(list,tuple)):
            for child in value:visit(child)
    visit(scene)
    if not profiles:return
    grid=scene.get('map',{});rows,cols=grid.get('rows'),grid.get('cols')
    if type(rows) is not int or type(cols) is not int or rows<=0 or cols<=0:raise ValueError('connectivity needs explicit scene grid')
    validate_routes(scene.get('parameters',{}).get('deployment_routes'),rows,cols)
    for profile in profiles:
        validate_profile(profile);rule=definitions.get(profile['rule'],{})
        if rule.get('contract')!='deploy.connectivity':raise ValueError('connectivity rule contract mismatch')
        if rule.get('implementation',{}).get('provider')=='model.deploy.ground_connectivity':
            validate_options({**thaw(rule.get('parameters',{})),**thaw(profile['parameters'])})


def inspect(context,definition,position,deployable):
    profile=deployable.get('connectivity')
    if profile is None:return
    validate_profile(profile);grid=context.spatial.grid
    routes=context.program.scenario.get('parameters',{}).get('deployment_routes')
    validate_routes(routes,grid.rows,grid.cols)
    tiles=[thaw(grid.tile(r,c)) for r in range(grid.rows) for c in range(grid.cols)]
    occupied=[]
    for index,tile in enumerate(tiles):
        if tile.get('obstacleLikeMoveCost'):occupied.append({'row':index//grid.cols,'col':index%grid.cols})
    for entity in context.session.world.entities():
        if not context.active(entity['id']) or context.route_hidden(entity['id']):continue
        if not entity['components'].get('route_obstacle'):continue
        other=entity['components'].get('spatial',{}).get('position')
        if other is not None:
            r,c=project_cell(other);occupied.append({'row':r,'col':c})
    prototype={'definition_id':definition['id'],'components':thaw(definition.get('components',{})),'tags':list(definition.get('tags',()))}
    decision=context.calc('deploy.connectivity',{'grid':{'rows':grid.rows,'cols':grid.cols,'tiles':tiles,
        'walkable':[bool(grid.passable(r,c)) for r in range(grid.rows) for c in range(grid.cols)]},
        'routes':thaw(routes),'occupied':occupied,'proposed':dict(position),'parameters':thaw(profile['parameters'])},
        rule_id=profile['rule'],component=deployable.get('rules',{}),scope_extra={'source':definition.get('rules',{})},extra={'source':prototype})
    if not isinstance(decision,Mapping) or set(decision)!={'accepted','reason'} or type(decision['accepted']) is not bool or not isinstance(decision['reason'],str):
        raise ValueError('deploy.connectivity must return strict accepted/reason decision')
    if not decision['accepted']:raise ValueError(decision['reason'])

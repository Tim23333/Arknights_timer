"""Owned tile layers: World stores ownership, pure rules compute effective data."""
from collections.abc import Mapping
from ark_sim.contracts import thaw
from ark_sim.rules.numeric import validate_data
import math

PATCH_FIELDS={'buildableType','passableMask','heightType','physicalHeight','advancedBuildMask','obstacleLikeMoveCost'}


def validate_values(values):
    if not isinstance(values,Mapping) or set(values)-PATCH_FIELDS:raise ValueError('terrain overlay values contain unsupported tile fields')
    for key,value in values.items():
        if key in ('buildableType','passableMask') and (type(value) is not int or not 0<=value<=3):raise ValueError('terrain overlay '+key+' requires mask0..3')
        if key=='advancedBuildMask' and (type(value) is not int or value<0):raise ValueError('terrain advancedBuildMask requires nonnegative integer')
        if key=='heightType' and value not in (0,1,'LOWLAND','HIGHLAND'):raise ValueError('terrain heightType requires0/1/LOWLAND/HIGHLAND')
        if key=='heightType' and isinstance(value,bool):raise ValueError('terrain heightType cannot be boolean')
        if key=='physicalHeight' and (type(value) not in (int,float) or not math.isfinite(value)):raise ValueError('terrain physicalHeight requires finite numeric data')
        if key=='obstacleLikeMoveCost' and type(value) is not bool:raise ValueError('terrain obstacleLikeMoveCost requires boolean')


def validate_spec(spec,position=False):
    allowed={'key','priority','values','preserve','rule'}|({'position'} if position else set())
    if not isinstance(spec,Mapping) or set(spec)-allowed:raise ValueError('terrain overlay unknown specification fields')
    if not isinstance(spec.get('key'),str) or not spec['key']:raise ValueError('terrain overlay requires nonempty owner key')
    if type(spec.get('priority')) is not int:raise ValueError('terrain overlay priority must be explicit integer')
    validate_values(spec.get('values'))
    preserve=spec.get('preserve',[])
    if not isinstance(preserve,(list,tuple)) or any(not isinstance(x,str) or x not in PATCH_FIELDS for x in preserve) or len(set(preserve))!=len(preserve):raise ValueError('terrain preserve requires unique known tile fields')
    if set(preserve)&set(spec['values']):raise ValueError('terrain preserve conflicts with a rewritten field')
    if 'rule' in spec and (not isinstance(spec['rule'],str) or not spec['rule']):raise ValueError('terrain overlay rule must be a definition ID')
    if 'position' in spec:
        p=spec['position']
        if not isinstance(p,Mapping) or set(p)!={'row','col'} or any(type(v) is not int for v in p.values()):raise ValueError('terrain overlay position requires integer cell')


class TerrainSystem:
    def __init__(self,context):self.ctx=context

    def _state(self):return self.ctx.get('system/battle',('state','terrain'),{'next_id':1,'revision':0,'layers':{},'effective_tiles':{}})
    def _save(self,state):self.ctx.set('system/battle',('state','terrain'),state)
    def _base(self,row,col):return thaw(self.ctx.spatial.grid._tiles[row*self.ctx.spatial.grid.cols+col])
    def _cell_layers(self,row,col,state):return [x for x in state['layers'].values() if x['cell']=={'row':row,'col':col}]

    def _evaluate(self,row,col,state):
        layers=self._cell_layers(row,col,state);base=self._base(row,col)
        if not layers:return base,None
        explicit={x['rule'] for x in layers if x.get('rule')}
        if len(explicit)>1:raise ValueError('overlapping terrain layers require one coherent tile-options rule')
        scope={'scenario':thaw(self.ctx.program.scenario.get('rules',{}))}
        result=self.ctx.rules.evaluate('terrain.tile_options',{'base':base,'layers':layers,'position':{'row':row,'col':col}},
            scope=scope,rule_id=next(iter(explicit)) if explicit else None,
            context={'time':self.ctx.session.time,'seconds':self.ctx.session.time*self.ctx.session.quantum,'quantum':self.ctx.session.quantum})
        options=thaw(result.value)
        if not isinstance(options,Mapping):raise ValueError('terrain tile-options rule must return tile data')
        # Custom rules can alter every normalized option, but cannot return
        # unrecognized behavior fields under the guise of a tile patch.
        normalized=PATCH_FIELDS|{'groundPassable','movementCost'}
        for key,value in options.items():
            if key not in normalized and (key not in base or value!=base[key]):
                raise ValueError('terrain rule cannot change base tile identity or behavior metadata')
        # A partial numeric result inherits immutable source identity/metadata;
        # adding active mechanics requires a separately implemented dispatcher.
        options={**base,**options}
        validate_values({k:v for k,v in options.items() if k in PATCH_FIELDS})
        if type(options.get('groundPassable')) is not bool:raise ValueError('terrain rule requires explicit groundPassable')
        cost=options.get('movementCost')
        if type(cost) not in (int,float) or not math.isfinite(cost) or cost<=0:raise ValueError('terrain rule requires positive finite movementCost')
        validate_data(options,'terrain effective tile')
        return dict(options),result

    def tile(self,row,col):return self._evaluate(row,col,self._state())[0]
    def map(self):
        state=self._state();base=thaw(self.ctx.spatial._base_map_definition)
        if not state['layers']:return base
        base['tiles']=[self._evaluate(r,c,state)[0] for r in range(base['rows']) for c in range(base['cols'])]
        return base

    def _changed(self,state,cells,reason):
        traces=[]
        for row,col in sorted(cells):
            tile,result=self._evaluate(row,col,state);key=f'{row}:{col}'
            if self._cell_layers(row,col,state):state['effective_tiles'][key]=tile
            else:state['effective_tiles'].pop(key,None)
            traces.append({'position':{'row':row,'col':col},'effective_tile':tile,'rule_id':result.rule_id if result else None,'trace':thaw(result.trace) if result else None})
        state['revision']+=1;self._save(state)
        # Derived paths/steering are never retained across a layer revision.
        for entity in self.ctx.session.world.entities():
            spatial=entity['components'].get('spatial',{})
            if spatial.get('route'):
                spatial=thaw(spatial);spatial.pop('movement_path',None);spatial.pop('velocity',None);spatial.pop('terrain_wait_revision',None)
                spatial.get('movement',{}).update(path_index=0)
                self.ctx.set(entity['id'],('spatial',),spatial)
        self.ctx.emit('terrain.changed',{'revision':state['revision'],'reason':reason,'changes':traces})
        self.ctx.spatial.blocking()

    def apply(self,owner,spec):
        with self.ctx.session.atomic():
            validate_spec(spec,position=True);owner=self.ctx.session.world.resolve(owner)
            if owner==self.ctx.session.world.resolve('system/battle') or not getattr(self.ctx, 'active', self.ctx.alive)(owner):raise ValueError('terrain overlay requires an active living actor owner')
            cell=spec.get('position',self.ctx.get(owner,('spatial','position')))
            if not isinstance(cell,Mapping) or set(cell)!={'row','col'} or any(type(v) is not int for v in cell.values()) or not self.ctx.spatial.grid.inside(cell['row'],cell['col']):raise ValueError('terrain overlay owner/cell must be an integer position inside map')
            state=self._state();cells={(cell['row'],cell['col'])}
            for key,layer in list(state['layers'].items()):
                if layer['owner']==owner and layer['key']==spec['key']:
                    cells.add((layer['cell']['row'],layer['cell']['col']));state['layers'].pop(key)
            uid=state['next_id'];state['next_id']+=1
            layer={'id':uid,'sequence':uid,'owner':owner,'cell':dict(cell),'key':spec['key'],'priority':spec['priority'],
                'values':thaw(spec['values']),'preserve':list(spec.get('preserve',[])),'rule':spec.get('rule')}
            state['layers'][str(uid)]=layer;self._changed(state,cells,{'kind':'apply_or_replace','owner':owner,'layer':uid,'key':spec['key']})
            return uid

    def remove(self,owner,key=None):
        with self.ctx.session.atomic():
            if key is not None and (not isinstance(key,str) or not key):raise ValueError('terrain remove requires a nonempty owner key')
            owner=self.ctx.session.world.resolve(owner)
            if owner==self.ctx.session.world.resolve('system/battle'):raise ValueError('terrain layers have actor owners')
            state=self._state();cells=set();removed=[]
            for uid,layer in list(state['layers'].items()):
                if layer['owner']==owner and (key is None or layer['key']==key):
                    cells.add((layer['cell']['row'],layer['cell']['col']));removed.append(int(uid));state['layers'].pop(uid)
            if removed:self._changed(state,cells,{'kind':'remove','owner':owner,'key':key,'layers':removed})
            return removed

    def tick(self,session):
        state=self._state()
        if not state['layers']:return
        cells={(l['cell']['row'],l['cell']['col']) for l in state['layers'].values()};changed=set()
        for row,col in cells:
            value,_=self._evaluate(row,col,state)
            if value!=state['effective_tiles'].get(f'{row}:{col}'):changed.add((row,col))
        if changed:
            with session.atomic():self._changed(state,changed,{'kind':'pure_rule_time_or_dependency_change'})

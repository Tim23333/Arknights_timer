"""Source-free periodic field state and pure sampled scheduling/membership."""
import math
from collections.abc import Mapping
from ark_sim.contracts import thaw
from .tile_fields import board,same_data
from .selection import validate_state,DEFAULT_STATE
from .spatial import project_cell
RESERVED_ORIGIN={'field_uid','cell','trigger_sequence'}


def finite(value,name,positive=False):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0 or (positive and value==0):raise ValueError(name+' must be finite nonnegative/positive numeric')


def validate_profile(p):
    if not isinstance(p,Mapping) or set(p)!={'type','trigger','membership','effects','expected_blackboard','origin'} or p['type']!='periodic_effect_field':raise ValueError('periodic field profile requires exact trigger/membership/effects/blackboard/origin')
    for name in ('origin','expected_blackboard'):
        if not isinstance(p[name],Mapping):raise ValueError('field '+name+' must be mapping')
    if RESERVED_ORIGIN & set(p['origin']):raise ValueError('field origin cannot forge runtime identity')
    trigger=p['trigger']
    if not isinstance(trigger,Mapping) or set(trigger)!={'rule','stream','sample_count','parameters','initial'}:raise ValueError('field trigger configuration fields invalid')
    if not isinstance(trigger['rule'],str) or not trigger['rule'] or not isinstance(trigger['stream'],str) or not trigger['stream'] or type(trigger['sample_count']) is not int or trigger['sample_count']<0 or not isinstance(trigger['parameters'],Mapping):raise ValueError('field trigger rule/stream/count/parameters invalid')
    initial=trigger['initial']
    if not isinstance(initial,Mapping) or initial.get('mode') not in ('sampled','fixed'):raise ValueError('field initial policy must be explicit sampled or fixed')
    if initial['mode']=='sampled' and set(initial)!={'mode'}:raise ValueError('sampled field initial policy fields invalid')
    if initial['mode']=='fixed':
        if set(initial)!={'mode','seconds'}:raise ValueError('fixed field initial policy requires seconds')
        finite(initial['seconds'],'field initial seconds')
    membership=p['membership']
    if not isinstance(membership,Mapping) or set(membership)!={'rule','parameters'} or not isinstance(membership['rule'],str) or not membership['rule'] or not isinstance(membership['parameters'],Mapping):raise ValueError('field membership requires rule/parameters')
    if not isinstance(p['effects'],(list,tuple)):raise ValueError('field effects must be explicit array')
    for effect in p['effects']:
        if not isinstance(effect,Mapping) or effect.get('op')!='no_source_damage' or RESERVED_ORIGIN & set(effect.get('origin',{})):raise ValueError('field effects require explicit no_source_damage and unforgeable origin')


def uniform_trigger(inputs,params,context):
    options={**thaw(params),**thaw(inputs['parameters'])}
    if set(options)!={'minimum_key','maximum_key'} or any(not isinstance(v,str) or not v for v in options.values()):raise ValueError('uniform trigger requires exact blackboard key bindings')
    low=inputs['blackboard'][options['minimum_key']];high=inputs['blackboard'][options['maximum_key']]
    finite(low,'field interval minimum',True);finite(high,'field interval maximum',True)
    if high<low:raise ValueError('field interval maximum below minimum')
    if len(inputs['samples'])!=1:raise ValueError('uniform field trigger requires one explicit sample')
    sample=inputs['samples'][0]
    if not isinstance(sample,Mapping) or set(sample)!={'value'}:raise ValueError('field sample requires explicit value record')
    u=sample['value']
    if type(u) not in (int,float) or not math.isfinite(u) or not 0<=u<1:raise ValueError('field random sample outside [0,1)')
    return {'enabled':True,'next_delay_seconds':low+(high-low)*u}


def cell_combat_members(inputs,params,context):
    options={**thaw(params),**thaw(inputs['parameters'])}
    if set(options)!={'side_mask','motion_mask','category_mask','extra_offsets','combat_policy','exclude_flags','respect_target_free'}:raise ValueError('field membership configuration incomplete')
    for key,limit in [('side_mask',7),('motion_mask',3),('category_mask',7)]:
        if type(options[key]) is not int or options[key]<=0 or options[key]&~limit:raise ValueError('field target mask invalid')
    if options['combat_policy'] not in ('blocked','attacking','blocked_or_attacking') or type(options['respect_target_free']) is not bool:raise ValueError('field combat/free policy invalid')
    offsets=options['extra_offsets'];flags=options['exclude_flags']
    if not isinstance(offsets,(list,tuple)) or any(not isinstance(v,(list,tuple)) or len(v)!=2 or any(type(x) is not int for x in v) for v in offsets):raise ValueError('field offsets require integer pairs')
    if not isinstance(flags,(list,tuple)) or any(type(v) is not int or not 0<=v<46 for v in flags):raise ValueError('field excluded flags invalid')
    row,col=project_cell(inputs['field']['cell']);extra={(row+dr,col+dc) for dr,dc in offsets};members=[]
    for actor in inputs['candidates']:
        key=str(actor['id']);state=inputs['selection_states'][key];validate_state(state,complete=True)
        if not options['side_mask']&(1<<state['side']) or not options['motion_mask']&state['motion'] or not options['category_mask']&state['category']:continue
        if options['respect_target_free'] and state['target_free']:continue
        if set(options['exclude_flags']) & set(state['abnormal_flags']):continue
        place=project_cell(actor['components']['spatial']['position'])
        if place!=(row,col):
            if place not in extra or state['side']!=1:continue
            combat=inputs['combat_states'][key];held=combat['blocked_by'] is not None;attacking=combat['attacking']
            allowed=held if options['combat_policy']=='blocked' else attacking if options['combat_policy']=='attacking' else held or attacking
            if not allowed:continue
        members.append(actor['id'])
    return members


def validate_content(definitions,scene):
    profiles=scene.get('map',{}).get('tile_mechanics',{})
    for key,p in profiles.items():
        if p.get('type')!='periodic_effect_field':continue
        validate_profile(p)
        for field,contract in [('trigger','field.trigger'),('membership','field.members')]:
            rule=definitions.get(p[field]['rule'],{})
            if rule.get('contract')!=contract:raise ValueError('field rule contract mismatch:'+field)
        for tile in scene['map']['tiles']:
            if tile.get('tileKey')==key and not same_data(board(tile),p['expected_blackboard']):raise ValueError('periodic field blackboard not exactly bound')


class PeriodicFieldSystem:
    def __init__(self,ctx):self.ctx=ctx
    def state(self):return self.ctx.state().get('periodic_fields',{'next_id':1,'fields':{}})
    def save(self,data):self.ctx.state_update(periodic_fields=data)
    def current(self,uid):return self.state()['fields'].get(uid)
    def initialize(self):
        profiles=self.ctx.program.scenario['map'].get('tile_mechanics',{})
        if not any(p.get('type')=='periodic_effect_field' for p in profiles.values()):return
        with self.ctx.session.atomic():
            for index,tile in enumerate(self.ctx.program.scenario['map']['tiles']):
                p=profiles.get(tile.get('tileKey'),{})
                if p.get('type')!='periodic_effect_field':continue
                data=self.state();uid='field/'+str(data['next_id']);data['next_id']+=1
                row,col=divmod(index,self.ctx.spatial.grid.cols)
                data['fields'][uid]={'uid':uid,'cell':{'row':row,'col':col},'tile_key':tile['tileKey'],'profile':thaw(p),'blackboard':board(tile),
                    'sequence':0,'generation':1,'active':True,'due':None,'task':None};self.save(data)
                initial=p['trigger']['initial']
                if initial['mode']=='fixed':self.schedule(uid,initial['seconds'])
                else:self.plan(uid,'initial')
    def schedule(self,uid,seconds):
        finite(seconds,'field schedule seconds');field=self.current(uid)
        if field is None or not field['active'] or self.ctx.state().get('finished'):return
        ticks=self.ctx.quantize(seconds)
        if seconds>0 and ticks<=0:raise ValueError('field positive delay quantizes to zero')
        due=self.ctx.session.time+ticks;task=self.ctx.session.schedule('domain.field.pulse',{'uid':uid,'generation':field['generation']},due,phase=0)
        data=self.state();data['fields'][uid].update(due=due,task=task);self.save(data)
    def plan(self,uid,phase):
        field=self.current(uid)
        if field is None or not field['active'] or self.ctx.state().get('finished'):return
        trigger=field['profile']['trigger'];samples=[{'value':self.ctx.session.random.sample(trigger['stream'])} for _ in range(trigger['sample_count'])]
        result=self.ctx.calc('field.trigger',{'field':field,'blackboard':field['blackboard'],'samples':samples,'phase':phase,
            'parameters':trigger['parameters']},rule_id=trigger['rule'],extra={'field_origin':field['profile']['origin']})
        if not isinstance(result,Mapping) or set(result)!={'enabled','next_delay_seconds'} or type(result['enabled']) is not bool:raise ValueError('field.trigger requires strict enabled/next_delay_seconds')
        if result['enabled']:finite(result['next_delay_seconds'],'field next delay',True);self.schedule(uid,result['next_delay_seconds'])
        elif result['next_delay_seconds'] is not None:raise ValueError('disabled field trigger requires null delay')
        else:self.remove(uid)
    def remove(self,uid):
        field=self.current(uid)
        if field is None:return
        with self.ctx.session.atomic():
            pending={t['id'] for t in self.ctx.session.scheduler.pending}
            if field['task'] in pending:self.ctx.session.cancel(field['task'])
            data=self.state();data['fields'][uid].update(active=False,generation=field['generation']+1,task=None,due=None);self.save(data)
    def tick(self,session):
        if not self.ctx.state().get('finished'):return
        for uid,field in self.state()['fields'].items():
            if field['active']:self.remove(uid)
    def members(self,field):
        actors=[];states={};combat={}
        for actor in self.ctx.session.world.entities():
            ref=actor['id']
            if 'system' in actor['tags'] or not self.ctx.selectable(ref) or actor['components'].get('spatial',{}).get('position') is None:continue
            # M72 adds the source=None availability consumer. Missing support
            # in the independent parent is explicit, never a fake source actor.
            if not self.ctx.spatial.available(None,ref,observable=True):continue
            actors.append(actor);states[str(ref)]=self.ctx.spatial.selection_state(ref,DEFAULT_STATE)
            decision=actor['components'].get('runtime',{}).get('behavior_decision',{}) or {}
            combat[str(ref)]={'blocked_by':self.ctx.spatial.blocked_by(ref),'attacking':bool(decision.get('attack')) or bool(actor['components'].get('runtime',{}).get('casts'))}
        rule=field['profile']['membership'];result=self.ctx.calc('field.members',{'field':field,'candidates':actors,'selection_states':states,'combat_states':combat,'parameters':rule['parameters']},rule_id=rule['rule'])
        allowed={actor['id'] for actor in actors}
        if not isinstance(result,(list,tuple)) or any(type(ref) is not int or ref not in allowed for ref in result) or len(set(result))!=len(result):raise ValueError('field.members requires unique allowed integer IDs')
        return list(result)
    def pulse(self,session,payload):
        with session.atomic():
            field=self.current(payload['uid'])
            if field is None or not field['active'] or field['generation']!=payload['generation']:return
            if self.ctx.state().get('finished'):self.remove(field['uid']);return
            data=self.state();data['fields'][field['uid']].update(task=None,due=None);self.save(data)
            members=self.members(field)
            event=self.ctx.emit('field.triggered',{'source':None,'field_uid':field['uid'],'cell':field['cell'],'sequence':field['sequence'],'members':members})
            for effect in field['profile']['effects']:
                for ref in members:
                    live=self.current(field['uid'])
                    if not live['active'] or live['generation']!=field['generation'] or self.ctx.state().get('finished'):return
                    # Re-evaluate live state/geometry/control between packets.
                    if ref not in self.members(live):continue
                    request=thaw(effect);request['origin']={**field['profile']['origin'],**request.get('origin',{}),
                        'field_uid':field['uid'],'cell':field['cell'],'trigger_sequence':field['sequence']}
                    self.ctx.effects.execute(None,[ref],request,cause=event)
            live=self.current(field['uid'])
            if not live['active'] or live['generation']!=field['generation'] or self.ctx.state().get('finished'):return
            data=self.state();data['fields'][field['uid']]['sequence']+=1;self.save(data);self.plan(field['uid'],'next')

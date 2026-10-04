"""Opt-in phase programs advanced by effects, with World-owned pending tasks.

This implementation executes explicit actions; no inferred native branch body
or invisible Timeline fallback. A phase is requested only after its previous
phase completes, and terminal cancellation retains unfinished state.
"""
from collections.abc import Mapping
from ark_sim.contracts import thaw


def validate(config,validate_effect=None):
    if not isinstance(config,Mapping) or not config:raise ValueError('branches require nonempty named programs')
    for key,program in config.items():
        if not isinstance(key,str) or not key or not isinstance(program,Mapping) or set(program)!={'phases','loop'} or type(program['loop']) is not bool:
            raise ValueError('branch program requires named phases and explicit loop boolean')
        phases=program['phases']
        if not isinstance(phases,(list,tuple)) or not phases:raise ValueError('branch phases must be nonempty')
        for phase in phases:
            if not isinstance(phase,Mapping) or set(phase)!={'pre_delay_seconds','actions'}:
                raise ValueError('branch phase requires exact pre_delay_seconds/actions')
            from ark_sim.content.schemas import number
            number(phase['pre_delay_seconds'],'branch.phase.delay',0)
            if not isinstance(phase['actions'],(list,tuple)):raise ValueError('branch actions must be list')
            for action in phase['actions']:
                if not isinstance(action,Mapping) or set(action)!={'delay_seconds','effects'}:
                    raise ValueError('branch action requires exact delay_seconds/effects')
                number(action['delay_seconds'],'branch.action.delay',0)
                if not isinstance(action['effects'],(list,tuple)) or not action['effects']:
                    raise ValueError('branch action effects must be nonempty')
                if validate_effect:
                    for effect in action['effects']:validate_effect(effect)


class BranchSystem:
    def __init__(self,context):
        self.ctx=context;self.handlers={'domain.branch.action':self.action}
    def state(self):return self.ctx.state().get('branches',{})
    def save(self,state):self.ctx.state_update(branches=state)
    def start(self):
        config=self.ctx.program.scenario['branches'];validate(config)
        self.save({key:{'cursor':0,'generation':0,'phase':'idle','remaining':0,'tasks':[],'action_tasks':{},'source':None}
                   for key in config})
    def available(self,key):
        if key not in self.ctx.program.scenario['branches']:raise ValueError('unknown branch program')
        row=self.state()[key];spec=self.ctx.program.scenario['branches'][key]
        return not self.ctx.state().get('finished') and row['phase']=='idle' and (row['cursor']<len(spec['phases']) or spec['loop'])
    def advance(self,key,source,cause=None):
        with self.ctx.session.atomic():
            if not self.available(key):raise ValueError('branch phase busy or complete')
            state=self.state();row=state[key];spec=self.ctx.program.scenario['branches'][key]
            cursor=row['cursor']%len(spec['phases']);phase=spec['phases'][cursor]
            source=self.ctx.session.world.resolve(source)
            if not self.ctx.active(source):raise ValueError('branch request source must be active')
            row.update(generation=row['generation']+1,phase='running',source=source,remaining=len(phase['actions']),tasks=[],action_tasks={})
            origin=self.ctx.session.time+self.ctx.quantize(phase['pre_delay_seconds'])
            for index,action in enumerate(phase['actions']):
                at=origin+self.ctx.quantize(action['delay_seconds'])
                task=self.ctx.session.schedule('domain.branch.action',{'branch':key,'generation':row['generation'],
                    'phase_index':cursor,'action_index':index},at,phase=self.ctx.effect_phase)
                row['tasks'].append(task)
                queued=next(t for t in self.ctx.session.scheduler.pending if t['id']==task)
                row['action_tasks'][str(index)]={'task':task,'due':at,'consumed':False,
                    'sequence':queued['seq'],'phase':queued['phase'],'priority':queued['priority']}
            if not row['remaining']:row.update(cursor=row['cursor']+1,phase='idle')
            self.save(state);self.ctx.emit('branch.phase_started',{'branch':key,'phase_index':cursor,
                'generation':row['generation'],'source':source,'actions':len(phase['actions'])},cause)
    def action(self,session,payload):
        with session.atomic():
            if not isinstance(payload,Mapping) or set(payload)!={'branch','generation','phase_index','action_index'} or not isinstance(payload['branch'],str) or any(type(payload[k]) is not int or payload[k]<0 for k in ('generation','phase_index','action_index')):
                raise ValueError('branch handler requires strict named program and integer task identity')
            key=payload['branch'];state=self.state();row=state[key]
            if row['phase']!='running' or type(payload['generation']) is not int or payload['generation']!=row['generation']:return
            if payload['phase_index']!=row['cursor']%len(self.ctx.program.scenario['branches'][key]['phases']):raise ValueError('branch phase identity differs')
            owned=row['action_tasks'].get(str(payload['action_index']))
            if owned is None or owned['consumed']:raise ValueError('branch action missing or already consumed')
            if session.time<owned['due'] or owned['task'] in {t['id'] for t in session.scheduler.pending}:
                raise ValueError('branch action cannot execute before actual owned dispatch')
            expected_key=(owned['due'],session.scheduler.rank(owned['phase']),owned['priority'],owned['sequence'])
            if session._active_key!=expected_key:raise ValueError('branch action must use its actual owned task identity')
            owned['consumed']=True;self.save(state)
            if self.ctx.state().get('finished'):self.cancel_terminal();return
            spec=self.ctx.program.scenario['branches'][key]['phases'][payload['phase_index']]['actions'][payload['action_index']]
            event=self.ctx.emit('branch.action_started',{'branch':key,'phase_index':payload['phase_index'],
                'action_index':payload['action_index'],'source':row['source']})
            for effect in spec['effects']:
                if self.ctx.state().get('finished'):self.cancel_terminal();return
                self.ctx.effects.execute(self.ctx.session.world.resolve('system/battle'),[],thaw(effect),cause=event)
            state=self.state();row=state[key]
            if row['phase']!='running' or row['generation']!=payload['generation']:return
            row['remaining']-=1
            if row['remaining']==0:
                row.update(cursor=row['cursor']+1,phase='idle',tasks=[],action_tasks={})
                self.ctx.emit('branch.phase_finished',{'branch':key,'phase_index':payload['phase_index'],'source':row['source']})
            self.save(state)
    def cancel_terminal(self):
        with self.ctx.session.atomic():
            state=self.state();pending={t['id'] for t in self.ctx.session.scheduler.pending}
            for key,row in state.items():
                if row['phase']=='running':
                    for task in row['tasks']:
                        if task in pending:self.ctx.session.cancel(task)
                    row.update(phase='stopped',tasks=[],generation=row['generation']+1)
            self.save(state)

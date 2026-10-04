"""Bounded reproducible M24 edits on the new ignored candidate only."""
from pathlib import Path
import json
ROOT=Path('D:/Arknights/Arknights_timer/unpack_work/campaign_m24_enemy_fsm_candidate')
def patch(name,old,new):
 p=ROOT/name;s=p.read_text(encoding='utf8');assert s.count(old)==1,(name,old);p.write_text(s.replace(old,new,1),encoding='utf8',newline='')
# One actual filter implementation serves existing selection and pure queries.
p=ROOT/'ark_sim/domains/movement.py';s=p.read_text();start=s.index('        definition = self.ctx.program.definitions[selector_id]',s.index('    def select('));end=s.index('        provider = definition.get("provider"',start)
block=s[start:end]
helper='    def _candidate_input(self, source, selector_id, primary=None):\n'+block+'        return definition, entity, candidates\n\n'
s=s[:start]+'        definition, entity, candidates = self._candidate_input(source, selector_id, primary)\n'+s[end:]
at=s.index('    def select(');s=s[:at]+helper+s[at:]
at=s.index('    def select(')
pure='''    def eligible(self, source, selector_id, ability=None, effect=None, primary=None):
        if (ability or {}).get('parameters', {}).get('healing') or (effect or {}).get('op') in {'heal', 'regenerate'}:
            raise ValueError('healing eligibility requires its explicit pure availability contract')
        definition, entity, candidates = self._candidate_input(source, selector_id, primary)
        result = self.ctx.rules.evaluate('selector.eligibility', {
            'source': entity, 'candidates': candidates, 'region': thaw(definition.get('region', {})),
            'selector_parameters': thaw(definition.get('parameters', {})),
            'selector_provider': definition.get('provider', 'ark.selector.grid')},
            scope={'scenario':thaw(self.ctx.program.scenario.get('rules',{})), 'source':thaw(self.ctx.definition(source).get('rules',{}))},
            rule_id=definition.get('eligible_rule'), context={'time':self.ctx.session.time, 'quantum':self.ctx.session.quantum})
        ids=thaw(result.value);allowed={x['id'] for x in candidates}
        if not isinstance(ids,list) or any(type(ref) is not int or ref not in allowed for ref in ids):
            raise ValueError('pure selector returned undeclared candidate identity')
        return ids

'''
s=s[:at]+pure+s[at:];p.write_text(s,encoding='utf8',newline='')
patch('ark_sim/domains/behavior.py','        provider = definition.get("provider") or definition.get("implementation", {}).get("provider")', '''        if definition.get('decision'):
            from .behavior_decision import facts
            inputs=facts(self.ctx,ref,definition['decision'],component.get('state',definition.get('initial',definition.get('initial_state'))))
            decision=self.ctx.calc('behavior.decision',inputs,source=ref,owner=ref,rule_id=definition['decision']['rule'])
            if not isinstance(decision,dict) or set(decision)!={'move','attack'} or any(type(x) is not bool for x in decision.values()):
                raise ValueError('behavior decision requires exactly move/attack booleans')
            return decision
        provider = definition.get("provider") or definition.get("implementation", {}).get("provider")''')
patch('ark_sim/domains/providers.py','BUILTIN_PROVIDERS = {','BUILTIN_PROVIDERS = {\n    "ark.selector.pure_eligibility": ark.pure_eligibility,\n    "ark.behavior.decision": ark.behavior_decision,')
patch('ark_sim/presets/providers.py','def selector_grid(inputs, params, context):','''def pure_eligibility(inputs,params,context):
    return context.invoke_provider(inputs['selector_provider'],{'source':inputs['source'],'candidates':inputs['candidates'],'region':inputs['region']},inputs['selector_parameters'])


def behavior_decision(inputs,params,context):
    p={**dict(params),**dict(inputs['parameters'])};v=inputs['visibility'];c=inputs['controls']
    if not v['alive'] or not v['active'] or v['hidden']:return {'move':False,'attack':False}
    if not c['abilities']:return {'move':False,'attack':False}
    busy=any(inputs['cast_groups'].get(key) for key in p.get('stop_cast_groups',[]))
    target=bool(inputs['eligible_ids'].get(p.get('target_key','normal'),[]))
    blocked=inputs['blocked_by'] is not None
    if p.get('blocked_target',False):target=blocked
    return {'move':bool(c['move'] and not blocked and not busy and not (p.get('stop_on_target',True) and target)),
            'attack':bool(c['attack'] and not busy and target)}


def selector_grid(inputs, params, context):''')
patch('ark_sim/content/schemas.py','"behavior": {"provider", "implementation", "states",','"behavior": {"decision", "provider", "implementation", "states",')
patch('ark_sim/content/schemas.py','"ordering", "limit", "limit_attribute", "provider", "parameters"}', '"ordering", "limit", "limit_attribute", "provider", "parameters", "eligible_rule"}')
patch('ark_sim/content/schemas.py','    elif kind == "behavior":\n','''    elif kind == "behavior":
        if definition.get('decision'):
            from ark_sim.domains.behavior_decision import validate_config
            try:validate_config(definition['decision'])
            except ValueError as error:raise ContentError(identifier+': '+str(error)) from error
''')
patch('ark_sim/content/capabilities.py','        if components.get("spatial", {}).get("steering"):', '''        machine=definitions.get(components.get('behavior',{}).get('machine'),{})
        if machine.get('decision'):
            config=machine['decision'];require('behavior.decision',identifier+'.behavior',scopes,config['rule'])
            if config.get('mode_resource') and config['mode_resource'] not in components.get('resources',{}):
                raise ContentError(identifier+': absent behavior mode resource')
            owned=set(components.get('abilities',[]))
            for profile in config['profiles']:
                for group in profile.get('cast_groups',[]):
                    if any(a not in owned for a in group['abilities']):raise ContentError(identifier+': behavior cast group includes unowned ability')
                for entry in profile.get('selectors',[]):
                    selected=definitions[entry['selector']]
                    if selected.get('kind')!='selector':raise ContentError(identifier+': behavior selector reference is not selector')
                    require('selector.eligibility',identifier+'.behavior',scopes,selected.get('eligible_rule'))
        if components.get("spatial", {}).get("steering"):''')
patch('ark_sim/content/capabilities.py','        elif kind == "selector" and identifier not in selectors_seen:\n            selector(identifier, identifier, [])','''        elif kind == "selector" and identifier not in selectors_seen:
            selector(identifier, identifier, [])
            if definition.get('eligible_rule'):require('selector.eligibility',identifier,scopes,definition['eligible_rule'])''')
p=ROOT/'ark_sim/rules/contracts.json';j=json.loads(p.read_bytes())
def contract(identifier,inputs,output,implementations,owner='source'):
 return {'id':identifier,'kind':'calculation','owner':owner,'inputs':[{'name':n,'type':t,'required':True} for n,t in inputs],
    'outputType':output,'implementations':implementations,'description':'Explicit pure declared model, not native-body recovery'}
j['contracts'].append(contract('behavior.decision',[(n,t) for n,t in [('source','entity_snapshot'),('state','string'),('mode','integer'),('casts','record'),('cast_groups','record'),('next_attack','logic_time'),('blocked_by','entity_ref'),('visibility','record'),('controls','record'),('clock','record'),('eligible_ids','record'),('parameters','record')]],'record',['expression','graph','provider']))
j['contracts'][-1]['inputs'][6]['required']=False;j['contracts'][-1]['inputs'][6]['nullable']=True
# Named item schema handles nullable blocker and strict decision values; domain also rejects extra keys.
j['contracts'][-1]['inputs'][6]['type']={'type':'entity_ref','nullable':True}
j['contracts'][-1]['outputSchema']={'type':'record','fields':{'move':{'type':'boolean'},'attack':{'type':'boolean'}}}
j['contracts'].append(contract('selector.eligibility',[('source','entity_snapshot'),('candidates','entity_list'),('region','record'),('selector_parameters','record'),('selector_provider','string')],'entity_list',['provider'],'source'))
j['contracts'][-1]['outputSchema']={'type':'entity_list','items':{'type':'integer'}};p.write_text(json.dumps(j,indent=2)+'\n',encoding='utf8',newline='')
p=ROOT/'ark_sim/content/presets/ark_standard.json';j=json.loads(p.read_bytes());j['rules'] += [
 {'id':'rule/ark_selector_pure_eligibility','kind':'calculation_rule','contract':'selector.eligibility','implementation':{'type':'provider','provider':'ark.selector.pure_eligibility'},'parameters':{'provider':'ark.selector.grid'}},
 {'id':'rule/ark_behavior_decision','kind':'calculation_rule','contract':'behavior.decision','implementation':{'type':'provider','provider':'ark.behavior.decision'}}]
j['rulesets'][0]['bindings']['selector.eligibility']='rule/ark_selector_pure_eligibility';p.write_text(json.dumps(j,indent=2)+'\n',encoding='utf8',newline='')

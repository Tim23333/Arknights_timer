"""Create a guarded isolated elemental candidate; primary source never edited."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT.parent/'unpack_work/campaign_elemental_v1_candidate'
PARENT='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
HERE=Path(__file__).parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'],cwd=root,text=True).strip()
def replace(path,old,new):
    text=path.read_text(encoding='utf-8');assert text.count(old)==1,(path,old)
    path.write_text(text.replace(old,new),encoding='utf-8',newline='')

def main():
    assert core(ROOT)==PARENT and not OUT.exists()
    shutil.copytree(ROOT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(HERE/'elemental.py',OUT/'ark_sim/domains/elemental.py')
    api=OUT/'ark_sim/adapters/api.py'
    replace(api,'        self.ctx.resources = ResourceSystem(self.ctx)',
        '        self.ctx.resources = ResourceSystem(self.ctx)\n        from ark_sim.domains.elemental import ElementalSystem\n        self.ctx.elemental = ElementalSystem(self.ctx)')
    replace(api,'        for name, handler in handlers.items():',
        '        if any("elemental" in d.get("components", {}) for d in self.program.definitions.values()):\n            handlers["domain.elemental.expire"] = self.ctx.elemental.expire\n            self.session.add_system(self.ctx.elemental.tick, phase=0)\n        for name, handler in handlers.items():')
    lifecycle=OUT/'ark_sim/domains/lifecycle.py'
    replace(lifecycle,'        self.ctx.resources.initialize_capacities(ref)',
        '        self.ctx.resources.initialize_capacities(ref)\n        self.ctx.elemental.initialize(ref)')
    replace(lifecycle,'        has_initial_clocks=has_initial_clocks or needs_arbitration_atomic(definition,kwargs.get("component_overrides") or {})',
        '        has_initial_clocks=has_initial_clocks or needs_arbitration_atomic(definition,kwargs.get("component_overrides") or {})\n        has_initial_clocks=has_initial_clocks or "elemental" in definition.get("components", {}) or "elemental" in (kwargs.get("component_overrides") or {})')
    replace(lifecycle,'        if reason == \'dead\':\n            generation=',
        '        self.ctx.elemental.cancel(ref, reason)\n        if reason == \'dead\':\n            generation=')
    effects=OUT/'ark_sim/domains/effects.py'
    replace(effects,'        if effect.get(\'op\') == \'restart_behavior\':',
        '''        if effect.get('op') in {'elemental_damage', 'elemental_attack'}:
            from .elemental import validate_effect
            validate_effect(effect)
        if effect.get('op') == 'restart_behavior':''')
    replace(effects,'            if operation == "instant_kill":',
        '''            if operation == 'elemental_damage':
                if source is not None and not self.ctx.active(source):continue
                self.ctx.elemental.apply(source,target,effect,cause)
            elif operation == 'elemental_attack':
                if source is not None and not self.ctx.active(source):continue
                # Complete request validated before the health packet. Nested
                # failure rolls health/events/RNG/scheduler back atomically.
                self.execute(source,[target],thaw(effect['health_effect']),ability,cast,cause)
                if self.ctx.active(target) and self.ctx.active(source):
                    self.ctx.elemental.apply(source,target,thaw(effect['element_effect']),cause)
            elif operation == "instant_kill":''')
    schema=OUT/'ark_sim/content/schemas.py'
    replace(schema,'COMPONENT_FIELDS = {','COMPONENT_FIELDS = {"elemental": None,')
    replace(schema,"EFFECT_FIELDS = {","EFFECT_FIELDS = {'element','health_effect','element_effect',")
    replace(schema,"'effects': {'restart_behavior'","'effects': {'elemental_damage','elemental_attack','restart_behavior'")
    replace(schema,'    fields(effect, EFFECT_FIELDS, path)',
        '''    fields(effect, EFFECT_FIELDS, path)
    if effect.get('op') in {'elemental_damage','elemental_attack'}:
        from ..domains.elemental import validate_effect as elemental_effect
        try:elemental_effect(effect)
        except ValueError as error:raise ContentError(path+': '+str(error)) from error
        if effect['op']=='elemental_attack':
            validate_effect(effect['health_effect'],path+'.health_effect',capabilities)
            validate_effect(effect['element_effect'],path+'.element_effect',capabilities)''')
    replace(schema,'        lifecycle=components.get(\'lifecycle\',{})',
        '''        if 'elemental' in components:
            from ..domains.elemental import validate as elemental_component
            try:elemental_component(components['elemental'])
            except ValueError as error:raise ContentError(identifier+': '+str(error)) from error
            for key,profile in components['elemental']['elements'].items():
                for phase in ('on_break','on_end'):
                    for index,child in enumerate(profile.get(phase,())):
                        validate_effect(child,identifier+'.elemental.'+key+'.'+phase+'['+str(index)+']',capabilities)
        lifecycle=components.get('lifecycle',{})''')
    cap=OUT/'ark_sim/content/capabilities.py'
    replace(cap,'        local = [*scopes, item.get("rules", {})]',
        '''        local = [*scopes, item.get("rules", {})]
        if item.get('op')=='elemental_damage' and item.get('amount_rule'):
            require('elemental.packet',path+'.amount_rule',local,item['amount_rule'])
        if item.get('op')=='elemental_attack':
            effect(item['health_effect'],path+'.health_effect',scopes)
            effect(item['element_effect'],path+'.element_effect',scopes)''')
    replace(cap,'        entity_scopes[identifier] = scopes',
        '''        if 'elemental' in components:
            spec=components['elemental']
            require('elemental.eligibility',identifier+'.elemental',scopes,spec['eligibility_rule'])
            require('time.quantize',identifier+'.elemental.clock',scopes)
            for key,profile in spec['elements'].items():
                for contract,binding in profile['rules'].items():
                    require(contract,identifier+'.elemental.'+key,scopes,binding)
                for phase in ('on_break','on_end'):
                    for index,child in enumerate(profile.get(phase,())):
                        effect(child,identifier+'.elemental.'+key+'.'+phase+'['+str(index)+']',scopes)
        entity_scopes[identifier] = scopes''')
    replace(cap,'        if item.get("amount_rule"):\n            require("resource.recovery", path, local, item["amount_rule"])',
        '        if item.get("amount_rule") and item.get("op")!="elemental_damage":\n            require("resource.recovery", path, local, item["amount_rule"])')
    compiler=OUT/'ark_sim/content/compiler.py'
    replace(compiler,'                    if key in expected_contracts and isinstance(child, str) and child in definitions:',
        '''                    if value.get('op')=='elemental_damage':expected_contracts['amount_rule']='elemental.packet'
                    if key in expected_contracts and isinstance(child, str) and child in definitions:''')
    catalog=OUT/'ark_sim/rules/contracts.json';old=json.loads(catalog.read_bytes());assert len(old['contracts'])==99
    fields={'source':'entity_snapshot','target':'entity_snapshot','element':'string','current':'resource_amount',
            'capacity':'resource_amount','delta_seconds':'duration','request':'record','attributes':'record','parameters':'record'}
    for key,output in [('capacity','resource_amount'),('loss','resource_amount'),('recovery','resource_amount'),('break_duration','duration'),('eligibility','boolean')]:
        old['contracts'].append({'id':'elemental.'+key,'kind':'calculation','owner':'target',
            'inputs':[{'name':name,'type':typ,'required':True} for name,typ in fields.items()],
            'outputType':output,'outputSchema':{'type':output},'implementations':['expression','graph','provider'],
            'pureEvaluation':True,'writesStateDirectly':False,'contractVersion':1})
    old['contracts'].append({'id':'elemental.packet','kind':'calculation','owner':'effect',
        'inputs':[{'name':name,'type':typ,'required':True} for name,typ in {'source':'entity_snapshot','target':'entity_snapshot','source_attributes':'record','target_attributes':'record','request':'record'}.items()],
        'outputType':'resource_amount','outputSchema':{'type':'resource_amount'},'implementations':['expression','graph','provider'],
        'pureEvaluation':True,'writesStateDirectly':False,'contractVersion':1})
    catalog.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='')
    before={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')}
    after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')}
    receipt={'candidate':str(OUT),'parent_core':PARENT,'candidate_core':core(OUT),
        'changed':[key for key in before if before[key]!=after[key]],'added':sorted(set(after)-set(before)),
        'parent_guards':before,'candidate_guards':after,'contracts_parent_count':99,'contracts_new_count':105,
        'primary_modified':False,'frozen':False,'author_gate':False}
    directory=ROOT/'validation/campaign/chapter09_elemental_v1';directory.mkdir(parents=True,exist_ok=True)
    path=directory/'composition.json';assert not path.exists();path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'core':receipt['candidate_core'],'composition_sha':sha(path),'changed':receipt['changed'],'added':receipt['added']}))

if __name__=='__main__':main()

"""Prezero marker ordering, postclear, exact damage and atomic receiver effects."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--core',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from ark_sim.contracts import digest
    from tools.chapter09_receiver_hooks_v1.build import build,providers,MARK
    from tools.chapter09_pillar_v1.build_payload import build as pillar,TRAIT
    assert implementation_digest()==args.core
    trait=next(x for x in pillar()['buffs'] if x['id']==TRAIT);results=[];artifacts=[];log=Path(os.environ['ARKSIM_RUN_DIR'])
    files=[Path(__file__),ROOT/'tools/chapter09_receiver_hooks_v1/build.py',ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json']
    files += [x for x in (runtime/'ark_sim').rglob('*') if x.is_file() and x.suffix in ('.py','.json')]
    guard=lambda:{str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in files};before=guard()

    def fixture(pillar_source=True,damage=500,profile='native_literal'):
        p=build(pillar_trait=TRAIT,dependency_definitions=[trait],profile=profile);p['buffs'].append(trait)
        for name,atk,tag in [('pillar_source',damage,pillar_source),('ordinary',12000,False)]:
            p['entities'].append({'id':'unit/receiver/test/'+name,'kind':'entity','components':{
                'attributes':{'base':{'max_hp':30001,'atk':atk,'def':971,'mres':37}},'resources':{'hp':{'initial':30001,'capacity':30001,'role':'health'}},
                'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},
                'buffs':{'initial':[TRAIT] if tag else []},'abilities':['ability/receiver/test/hit']}})
        p['selectors'].append({'id':'selector/receiver/test/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]})
        p['abilities'].append({'id':'ability/receiver/test/hit','kind':'ability','activation':{'mode':'manual'},
            'selector':'selector/receiver/test/enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
        p['scenarioDraft']={'id':'scene/receiver/mark','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':6},
            'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'enemy','position':{'row':0,'col':0}},
                {'definition':'unit/receiver/test/pillar_source','instanceAlias':'pillar_source','position':{'row':0,'col':4}},
                {'definition':'unit/receiver/test/ordinary','instanceAlias':'ordinary','position':{'row':1,'col':4}}],
            'commands':[{'at':7,'action':'skill','source':'pillar_source','ability':'ability/receiver/test/hit'}]}
        return p

    def create(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=9211)

    def proof(p,label,split=8,end=20):
        s=create(p);s.advance(split);q=log/(label+'.checkpoint.json');q.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(s.program,json.loads(q.read_bytes()),providers=providers());s.advance(end-split);r.advance(end-split);h=replay(s.program,s.export_replay(),providers=providers());assert s.checkpoint()==r.checkpoint()==h.checkpoint();artifacts.append({'path':str(q),'sha':hashlib.sha256(q.read_bytes()).hexdigest(),'CPP_head_full_equal':True,'digest':digest(s.checkpoint())});return s

    def nonlethal_clear():
        p=fixture();p['scenarioDraft']['commands'].append({'at':9,'action':'skill','source':'ordinary','ability':'ability/receiver/test/hit'});s=create(p);s.advance(8)
        assert s.ctx.resources.current('enemy','hp')==9500
        assert not any(x['definition']==MARK for x in s.ctx.get('enemy',('buffs','instances')))
        s=proof(p,'native_clear_then_ordinary');assert s.ctx.alive('enemy') and abs(s.ctx.resources.current('enemy','hp')-2000.0000298023224)<1e-8
        assert not [e for e in s.session.events if e['type']=='entity.rebirth.skipped']

    def lethal_skip():
        s=proof(fixture(damage=12000),'source_mark_lethal');assert not s.ctx.alive('enemy') and s.ctx.resources.current('enemy','mode')==3
        assert len([e for e in s.session.events if e['type']=='entity.rebirth.skipped'])==1
        mark=next(e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==MARK)
        zero=next(e for e in s.session.events if e['type']=='resource.changed' and e['payload']['target']==s.session.world.resolve('enemy') and e['payload']['resource']=='hp' and e['payload']['value']==0)
        assert mark['id']<zero['id']

    def ordinary_no_mark():
        s=proof(fixture(False,12000),'ordinary_no_marker');assert s.ctx.alive('enemy') and s.ctx.resources.current('enemy','mode')==1
        assert not [e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==MARK]

    def late_hook_fault():
        p=fixture();hook=next(x for x in p['buffs'] if x['id'].endswith('/pillar_check'))['damage_hooks'][0]
        hook['after_effects'].append({'op':'apply_buff','buff':'buff/receiver/test/fault'})
        p['buffs'].append({'id':'buff/receiver/test/fault','kind':'buff','effects':[{'op':'random','stream':'receiver_fault','probability':1,'on_success':[{'op':'modify_resource','resource':'absent','amount':1}]}]})
        s=create(p);checkpoint=s.checkpoint()
        try:s.ctx.effects.execute('pillar_source',['enemy'],{'op':'damage','damage_type':'true','scale':1})
        except ValueError as error:
            assert 'absent' in str(error), 'Fault must reach declared late missing-resource callback'
        else:raise AssertionError('Late receiver cleanup fault missing')
        assert s.checkpoint()==checkpoint

    for name,fn in [('nonlethal_marker_cleared_before_other_source_zero',nonlethal_clear),('same_source_lethal_mark_precedes_zero_and_skips',lethal_skip),('ordinary_damage_no_mark_regular_rebirth',ordinary_no_mark),('post_modifier_latefault_full_world_rng_cache_rollback',late_hook_fault)]:
        try:fn();results.append({'case':name,'passed':True})
        except Exception as error:results.append({'case':name,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    after=guard();report={'core':args.core,'actual_exit':0 if all(x['passed'] for x in results) and before==after else 1,'results':results,'source_before':before,'source_after':after,'source_equal':before==after,'artifacts':artifacts,'comparison_exclusions':[],'whole_stage':False,'scope':'Actor receiving-before native same-modifier marker, not PRTS persistent1sec alternative or noSource bypass'};args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');return report['actual_exit']


if __name__=='__main__':raise SystemExit(main())

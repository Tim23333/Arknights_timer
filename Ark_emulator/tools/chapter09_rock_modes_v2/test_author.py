"""Source-mode content gates with public commands and complete disk/head proofs."""
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
    parser = argparse.ArgumentParser(); parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--core', required=True); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from ark_sim.contracts import digest
    from tools.chapter09_rock_modes_v2.build import build,providers,SOURCE
    from tools.chapter09_pillar_v1.build_payload import build as pillar,TRAIT
    assert implementation_digest()==args.core
    trait=next(x for x in pillar()['buffs'] if x['id']==TRAIT);results=[];artifacts=[];log=Path(os.environ['ARKSIM_RUN_DIR'])
    files=[Path(__file__),ROOT/'tools/chapter09_rock_modes_v2/build.py',SOURCE,
           ROOT/'tools/chapter09_rock_gargoyle/build_v1.py',ROOT/'tools/chapter09_pillar_v1/build_payload.py']
    files += [p for p in (runtime/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
    guard=lambda:{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};before=guard()

    def fixture(key='enemy_1171_durokt',profile='prts_reference',block=False):
        p=build(key,pillar_trait_buff=TRAIT,dependency_definitions=[trait],profile=profile);p['buffs'] += [trait,
            {'id':'buff/rock/test/stun','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_flags':[0]},
             'control':{'move':False,'attack':False,'abilities':False,'interrupt':True}}]
        actor={'id':'unit/rock/test/source','kind':'entity','tags':['player'],'components':{
            'attributes':{'base':{'max_hp':30017,'atk':12000,'def':137,'mres':23,'block_count':1}},
            'resources':{'hp':{'initial':30017,'capacity':30017,'role':'health'}},'spatial':{},
            'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'},
            'abilities':['ability/rock/test/stun','ability/rock/test/hit','ability/rock/test/leave'],
            **({'deployable':{'base_cost':1,'terrain':'ground','capacity':1}} if block else {})}}
        p['entities'].append(actor);p['selectors'].append({'id':'selector/rock/test/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]})
        for name,effect in [('stun',{'op':'apply_buff','buff':'buff/rock/test/stun'}),('hit',{'op':'damage','damage_type':'true','scale':1})]:
            p['abilities'].append({'id':'ability/rock/test/'+name,'kind':'ability','activation':{'mode':'manual'},
                'selector':'selector/rock/test/enemy','timeline':[{'at':0,'effect':effect}]})
        p['abilities'].append({'id':'ability/rock/test/leave','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':{'row':2,'col':5}}}]})
        p['scenarioDraft']={'id':'scene/rock/source_modes_v2','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':7},
            'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'enemy','position':{'row':1,'col':0},
                'route':{'startPosition':{'row':1,'col':0},'endPosition':{'row':1,'col':6},'motionMode':0,'checkpoints':[]}},
                {'definition':actor['id'],'instanceAlias':'source','position':{'row':1,'col':0 if block else 4},'deployed':block}],
            'commands':[]}
        return p

    def create(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=9291)

    def proof(p,label,split,end):
        s=create(p);s.advance(split);q=log/(label+'.checkpoint.json');q.write_text(json.dumps(s.checkpoint()),encoding='utf8')
        r=Engine.restore(s.program,json.loads(q.read_bytes()),providers=providers());s.advance(end-split);r.advance(end-split)
        h=replay(s.program,s.export_replay(),providers=providers());assert s.checkpoint()==r.checkpoint()==h.checkpoint()
        artifacts.append({'path':str(q),'sha':hashlib.sha256(q.read_bytes()).hexdigest(),'CPP_head_full_equal':True,'digest':digest(s.checkpoint())});return s

    def recover():
        p=fixture();p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/rock/test/stun'}]
        s=proof(p,'recover28',30,90);starts=[e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']=='ability/ch9/durokt/recover'];ends=[e['time'] for e in s.session.events if e['type']=='ability.finished' and e['payload']['ability']=='ability/ch9/durokt/recover']
        assert starts==[18] and ends==[46] and s.ctx.resources.current('enemy','recover_used')==1
        assert s.ctx.get('enemy',('spatial','route','motionMode'))==0 and s.ctx.get('enemy',('selection_state','motion'))==1

    def blocked_recover_gate():
        p=fixture(block=True);p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/rock/test/stun'},
            {'at':70,'action':'skill','source':'source','ability':'ability/rock/test/leave'}]
        s=create(p);s.advance(69);assert not any(e['type']=='ability.started' and e['payload']['ability'].endswith('/recover') for e in s.session.events)
        s=proof(p,'blocked_then_leave',65,150);assert len([e for e in s.session.events if e['type']=='ability.started' and e['payload']['ability'].endswith('/recover')])==1

    def start20():
        p=fixture('enemy_1172_dugago');p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/rock/test/hit'}]
        s=create(p);s.advance(3);assert s.ctx.resources.current('enemy','hp')==10000
        assert s.ctx.attributes.value('enemy','def')==1350 and s.ctx.attributes.value('enemy','mres')==100
        s=proof(p,'stone_start20',310,350);starts=[e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability'].endswith('/start_flight')];assert starts==[302]
        marker=[e['time'] for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff'].endswith('/reborn_complete')];assert marker==[322]
        assert s.ctx.resources.current('enemy','mode')==2 and s.ctx.get('enemy',('spatial','route','motionMode'))==0
        assert s.ctx.get('enemy',('selection_state','motion'))==2
        assert s.ctx.attributes.value('enemy','def')==550 and s.ctx.attributes.value('enemy','mres')==70

    def native_profile():
        p=fixture('enemy_1172_dugago','native_literal');p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/rock/test/hit'}]
        s=proof(p,'native_literal',310,350);assert abs(s.ctx.resources.current('enemy','hp')-2000.0000298023224)<1e-8
        assert s.ctx.get('enemy',('selection_state','motion'))==1 and s.ctx.get('enemy',('spatial','route','motionMode'))==0

    def early_stone_and_second_zero():
        p=fixture('enemy_1172_dugago');p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'source','ability':'ability/rock/test/hit'},
            {'at':340,'action':'skill','source':'source','ability':'ability/rock/test/hit'}]
        s=proof(p,'second_zero',320,345);assert not s.ctx.alive('enemy') and not s.ctx.get('enemy',('runtime','casts'))

    for name,fn in [('durokt_real_landing_recover_once28',recover),('recover_only_when_ground_unblocked',blocked_recover_gate),
                    ('gargoyle_stone_then20frame_OnStart_marker',start20),('explicit_native_literal_restoration_motion_profile',native_profile),
                    ('second_lethal_after_flight_no_extra_rebirth',early_stone_and_second_zero)]:
        try:fn();results.append({'case':name,'passed':True})
        except Exception as error:results.append({'case':name,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    after=guard();report={'core':args.core,'actual_exit':0 if all(x['passed'] for x in results) and before==after else 1,
        'results':results,'source_before':before,'source_after':after,'source_equal':before==after,'artifacts':artifacts,
        'comparison_exclusions':[],'whole_enemy':False,'whole_stage':False,'reference_limits':['Block/skill startup under stun follows declared V2 control and priority policy','Pillar mark lingering profile still to close','Native motion/reset correspondence preserved by explicit native/reference profiles']}
    args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');return report['actual_exit']


if __name__=='__main__':raise SystemExit(main())

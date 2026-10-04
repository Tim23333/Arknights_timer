"""First fatal target stops the next target's real before-damage RNG hook."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.experiments.m13_peer import verify as h


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--digest',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim';before=implementation_digest();assert before==args.digest
    files=[Path(__file__),Path(h.__file__)];source={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    p=h.scene(steps=[{'kind':'effects','effects':[{'op':'damage','damage_type':'true','selector':'selector/all_enemies',
        'rules':{'damage.pipeline':'rule/fatal_packet'}},h.pulse('after_targets')]}],ack='immediate')
    p['controls'][0]['on_start'].append({'op':'apply_buff','target':'battle','buff':'buff/packet_draw'})
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/peer_enemy','instanceAlias':a,'position':{'row':0,'col':i}} for i,a in enumerate(('one','two'))]
    p['selectors']=[{'id':'selector/all_enemies','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':None}]
    p['buffs']=[{'id':'buff/packet_draw','kind':'buff','damage_hooks':[{'phase':'before','rule':'rule/packet_draw','samples':{'stream':'imp','count':1}}]}]
    p['rules']=[{'id':'rule/fatal_packet','kind':'calculation_rule','contract':'damage.pipeline','implementation':{'type':'graph',
        'nodes':[{'id':'settled','expression':"{'accepted':True,'amount':10,'allocations':[{'target':inputs.target.id,'resource':'hp','delta':-10},{'target':inputs.source.id,'resource':'life','delta':-5}],'events':[]}"}],'output':'nodes.settled'}},
        {'id':'rule/packet_draw','kind':'calculation_rule','contract':'damage.request','implementation':{'type':'graph',
            'nodes':[{'id':'request','expression':"{'accepted':True,'effect':inputs.effect,'effects':[]}"}],'output':'nodes.request'}}]
    s=h.make(p);s.advance(1)
    assert len(s.session.random.samples)==1
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['payload']['target']==s.session.world.resolve('one')
    assert s.ctx.alive('two') and s.ctx.resources.current('two','hp')==10
    assert not [e for e in s.session.events if e['type'] in ('peer.after_targets','control.completed')]
    assert s.ctx.controls.instance('notice')['status']=='cancelled'
    assert not [t for t in s.session.scheduler.pending if t['kind'].startswith(('domain.control','domain.timeline'))]
    actual=h.observed(s,{'real_damage_hook_draw_per_packet':True,'first_fatal_target_only_one_draw':True,'second_HP10_alive':True,'followup_effect_not_run':True})
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};assert before==implementation_digest() and source==after
    result={'schema':'ark-sim/bounded-control-peer-review/v1','passed':True,'implementation_sha256':before,'runtime_module':ark_sim.__file__,
        'cases':[{'case':'fatal_first_target_stops_later_packet_RNG','result':'passed','actual':actual}],
        'source_at_start':source,'source_at_completion':after,'identity_stable':True,
        'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed'}],
        'scope':'one generic first-target damage allocation/terminal/RNG boundary; no native UI or stage approval','formal_approval':False,'promotion_receipt':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'draws':1,'accepted_packets':1}));return 0


if __name__=='__main__':raise SystemExit(main())

"""A zero-lifetime control must not interrupt an existing public cast."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v7_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from test_campaign_acceptance import scene


def main():
    p=scene();p['abilities'][0]['timeline'][0]['at']=10
    source=p['entities'][0]
    source['components']['abilities'].append('ability/zero_control')
    p['buffs']=[{'id':'buff/zero_control','kind':'buff','control':{'abilities':False,'interrupt':True}}]
    p['rules']=[{'id':'rule/zero_control','kind':'calculation_rule','contract':'buff.application','implementation':{'type':'expression',
        'expression':"{'accepted':True,'operations':[{'kind':'apply','buff':'buff/zero_control','duration_seconds':0}]}"}}]
    p['abilities'].append({'id':'ability/zero_control','kind':'ability','activation':{'mode':'manual','parameters':{'blocks_attacks':False}},
        'selector':'selector/probe','timeline':[{'at':0,'effect':{'op':'buff_application','application_rule':'rule/zero_control','allowed':['buff/zero_control']}}]})
    # Target begins a delayed cast, then receives the explicit zero control via a public scheduled effect.
    p['entities'][1]['components']['abilities']=['ability/probe']
    p['entities'][1]['components']['attributes']['base']['atk']=10
    p['scenarioDraft']['scheduledEffects']=[{'at':2,
        'effect':{'op':'buff_application','target':3,'application_rule':'rule/zero_control','allowed':['buff/zero_control']}}]
    sim=Engine.create(Compiler().compile(p),seed=617)
    assert sim.session.world.resolve('target1')==3
    sim.submit({'action':'skill','source':'target1','ability':'ability/probe'},at=0)
    sim.session.advance(3)
    interrupted=[e for e in sim.session.events if e['type']=='ability.interrupted' and e['payload'].get('source')==sim.session.world.resolve('target1')]
    target=ROOT/'validation/campaign/chapter06_buff_join_v7/zero_control_probe.json'
    report={'core':implementation_digest(),'passed':not interrupted,'actual_interrupts':[dict(e) for e in interrupted],
            'scope':'Fresh zero-control side-effect boundary; same public delayed cast should survive duration0'}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'passed':report['passed'],'interrupts':len(interrupted)}));raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()

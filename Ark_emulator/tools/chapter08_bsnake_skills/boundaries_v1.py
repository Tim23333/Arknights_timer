"""Fresh public recapture, qualification, lethal owner and modifier counters."""
import json
from tools.chapter08_bsnake_skills import author_v2 as base
from tools.chapter08_bsnake_skills.author_v3 import package as prepared
from tools.chapter08_bsnake_skills.build_v1 import BASE,sha,TIMER,CHILD,application,CORE
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_bsnake_skills.policies_v1 import providers
OUT=BASE/'skills_boundaries_v1'
def fixture_prepare(p,at):
    p['entities'][1]['tags'].append('primary')
    p['selectors'].append({'id':'selector/fixture/prepare','kind':'selector','region':{'type':'all'},'filters':[{'tag':'primary'}]})
    p['abilities'].append({'id':'ability/fixture/prepare','kind':'ability','activation':{'mode':'manual'},'selector':'selector/fixture/prepare','timeline':[{'at':0,'effect':application()}]})
    p['entities'][0]['components']['abilities'].append('ability/fixture/prepare')
    p['scenarioDraft']['commands']=[{'at':at,'action':'skill','source':'boss','ability':'ability/fixture/prepare'}]
def scene(case):
    kind='explode' if case.startswith('explode') else 'ignite';p=prepared(0,kind)
    if case=='ignite_marker_camo':
        p['entities'][1]['components']['buffs']={'initial':[TIMER,CHILD]}
        p['entities'][2]['components']['selection_state']['camouflage']=True
        p['entities'][3]['components']['selection_state']['motion']=2
    if case=='ignite_recapture':fixture_prepare(p,590)
    if case=='ignite_ASPD2':p['entities'][0]['components']['attributes']['base']['attack_speed_ratio']=2
    if case=='ignite_retire':
        p['entities'][0]['tags'].append('fixture_boss');p['selectors'].append({'id':'selector/fixture/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'fixture_boss'}]})
        p['abilities'].append({'id':'ability/fixture/retire','kind':'ability','activation':{'mode':'manual'},'selector':'selector/fixture/boss','timeline':[{'at':0,'effect':{'op':'retire','parameters':{'reason':'withdrawn'}}}]})
        p['entities'][1]['components']['abilities']=['ability/fixture/retire'];p['scenarioDraft']['commands']=[{'at':560,'action':'skill','source':'primary','ability':'ability/fixture/retire'}]
    if case=='explode_camo_air':
        p['entities'][2]['components']['selection_state']['camouflage']=True
        p['entities'][3]['components']['selection_state']['motion']=2
    if case=='explode_lethal_owner':
        p['entities'][1]['components']['attributes']['base']['max_hp']=900
        p['entities'][1]['components']['resources']['hp'].update(initial=900,capacity=900)
    if case=='explode_modifier':
        rule='rule/fixture/half';buff='buff/fixture/half'
        p['rules'].append({'id':rule,'kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':inputs.effect.settlement.accepted,'amount':inputs.effect.settlement.amount*.5,'allocations':[],'events':[]}"}],'output':'nodes.result'}})
        p['buffs'].append({'id':buff,'kind':'buff','damage_hooks':[{'phase':'after','rule':rule,'condition':"inputs.effect.damage_flags.source_attack_type=='NORMAL'"}]});p['entities'][2]['components']['buffs']={'initial':[buff]}
    return p,kind
def run(case):
    p,kind=scene(case);reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=818);folder=OUT/case;folder.mkdir(parents=True,exist_ok=True)
    boundary=600 if kind=='ignite' else 1082;end=670 if kind=='ignite' else 1130
    s.session.advance(boundary);cp=folder/'checkpoint.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.session.advance(end-boundary);r.session.advance(end-boundary);head=replay(program,s.export_replay(),providers=reg)
    assert base.domain(s)==base.domain(r)==base.domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
    obs=[thaw(e) for e in s.session.events if e['type'] in ('ability.started','damage.accepted','entity.died','area.resolved','buff.applied','buff.removed')]
    hits=[(e['time'],e['payload']['target'],e['payload']['amount']) for e in obs if e['type']=='damage.accepted']
    applied=[(e['time'],e['payload']['target']) for e in obs if e['type']=='buff.applied' and e['payload']['buff']==TIMER]
    if case=='ignite_marker_camo':assert [(t,x) for t,x in applied if t==605]==[(605,5),(605,6)]
    if case=='ignite_recapture':assert applied==[(590,3),(605,4),(605,5)],applied
    if case=='ignite_ASPD2':assert applied==[(588,3),(588,4)] and [h for h in hits if h[0]==618]==[(618,3,56),(618,4,56)]
    if case=='ignite_retire':assert applied==[] and hits==[] and not s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==50000
    normal=[(e['time'],e['payload']['target'],e['payload']['amount']) for e in obs if e['type']=='damage.accepted' and e['payload']['damage_flags']['source_attack_type']=='NORMAL']
    if case=='explode_camo_air':assert normal==[(1082,3,616),(1082,5,308)] and applied==[(900,3),(1083,5)]
    if case=='explode_lethal_owner':
        assert normal==[(1082,3,616),(1082,4,462),(1082,5,308)]
        assert len([e for e in obs if e['type']=='entity.died' and e['payload']['target']==3])==1
        assert len([e for e in obs if e['type']=='area.resolved'])==1 and s.ctx.resources.current('primary','hp')==0
    if case=='explode_modifier':assert normal==[(1082,3,616),(1082,4,231),(1082,5,308)] and [h for h in hits if h[0]==1113]==[(1113,4,56),(1113,5,56)]
    (folder/'input.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(folder/'replay.json').write_text(json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with (folder/'events.jsonl').open('wb') as f:
        for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False)+'\n').encode())
    return {'case':case,'CP':True,'head':True,'full_event_equality':True,'observations':obs,'files':{str(x):sha(x) for x in folder.iterdir()}}
def main():
    assert implementation_digest()==CORE;OUT.mkdir(exist_ok=True);rows=[]
    for case in ['ignite_marker_camo','ignite_recapture','ignite_ASPD2','ignite_retire','explode_camo_air','explode_lethal_owner','explode_modifier']:
        rows.append(run(case));print(case+' passed',flush=True)
    out=OUT/'report.json';assert not out.exists();out.write_text(json.dumps({'status':'seven_boundary_cases_passed','core':CORE,'module_sha256':sha(BASE/'skills.module.v3.json'),'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(sha(out))
if __name__=='__main__':main()

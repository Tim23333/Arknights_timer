"""Independent fixtures/source expectations; never import author tests/builders."""
import argparse,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_chapter08_joint_v4_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.chapter08_bsnake_combat.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
CORE='20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30'
BASE=ROOT/'packages/campaign/chapter08_consumers/bsnake';SOURCE=BASE/'source.closure.v1.json'
D12=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v12.joint.json'
PROTECT='buff/ch8/source/bsnake_t[protect]';REBORN=PROTECT+'/reborn';TIMER='buff/ch8/source/dragon_fire';CHILD='buff/ch8/source/dragon_fire[damage]'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def domain(s):return {'world':s.session.world.snapshot(),'tasks':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def base(module,case):
    p=json.loads(module.read_bytes());owner=p['entities'][0]['id'];profile=1 if case=='phase1_live' else 0
    p['entities'][0]['components']['resources']['mode']['initial']=profile
    p['entities'].append({'id':'unit/independent/attacker','kind':'entity','tags':['player','peer_target'],'components':{
        'attributes':{'base':{'max_hp':25000,'atk':642,'def':2397,'mres':93,'one_minus_status_resistance':1,'taunt_level':7}},
        'resources':{'hp':{'initial':25000,'capacity':25000,'role':'health'}},'spatial':{},
        'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}})
    p['selectors'] += [{'id':'selector/independent/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'peer_boss'}]},
                       {'id':'selector/independent/player','kind':'selector','region':{'type':'all'},'filters':[{'tag':'peer_target'}]}]
    p['entities'][0]['tags'].append('peer_boss')
    p['scenarioDraft']={'id':'scene/independent/bsnake/'+case,'ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':8},
        'initialEntities':[{'definition':owner,'instanceAlias':'boss','position':{'row':2,'col':2}},
            {'definition':'unit/independent/attacker','instanceAlias':'player','position':{'row':2,'col':3.25}}]}
    p['manifest']['metadata']['independent_scope']='New source-derived fixture values, no author fixture/expected imports. Roster/stage/rebirth life is outside this normal/protect review.'
    return p
def manual(p,name,effect,selector='selector/independent/boss',actor=1):
    aid='ability/independent/'+name
    p['abilities'].append({'id':aid,'kind':'ability','selector':selector,'activation':{'mode':'manual'},'timeline':[{'at':0,'effect':effect}]})
    p['entities'][actor]['components'].setdefault('abilities',[]).append(aid);return aid
def prepare(module,case):
    p=base(module,case);commands=[]
    if case=='phase1_live':
        p['buffs'].append({'id':'buff/independent/source_reborn_attributes','kind':'buff','modifiers':[{'attribute':'atk','layer':'direct_ratio','value':.5},{'attribute':'max_hp','layer':'direct_ratio','value':.5}]})
        aid=manual(p,'source_reborn_attributes',{'op':'apply_buff','buff':'buff/independent/source_reborn_attributes'});commands.append({'at':10,'action':'skill','source':'player','ability':aid})
    if case=='ASPD2':p['entities'][0]['components']['attributes']['base']['attack_speed_ratio']=2
    if case=='withdraw_target':
        aid=manual(p,'withdraw',{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}});commands.append({'at':19,'action':'skill','source':'player','ability':aid})
    if case=='unqualified_air':p['entities'][1]['components']['selection_state']['motion']=2
    if case in ('protect_expiry','protect_child_only','silence_normal_container','silence_reborn_container','silence_native','samekey_group'):
        p['scenarioDraft']['initialEntities'][1]['position']['col']=7
        if case.startswith('silence_') and case!='silence_native':
            p['entities'][0]['id']='unit/independent/nonBoss_container';p['scenarioDraft']['initialEntities'][0]['definition']=p['entities'][0]['id']
            p['entities'][0]['components']['selection_state']['abnormal_immunes']=[]
            p['entities'][0]['metadata']={'fixture':'NonBoss container solely tests reusable silence profile; native Boss immunity unchanged elsewhere.'}
        if case in ('silence_reborn_container','silence_native'):p['entities'][0]['components']['buffs']['initial']=[REBORN]
        if case=='samekey_group':p['entities'][0]['components']['buffs']['initial']=[PROTECT,REBORN]
        burn={'op':'buff_application','application_rule':'rule/ch8/dragon_fire/application','allowed':[TIMER,CHILD]}
        fire=manual(p,'burnself',burn,actor=1,selector='selector/independent/player')
        if case=='protect_child_only':
            p['abilities'][-1]['timeline'][0]['effect']={'op':'apply_buff','buff':CHILD}
        commands.append({'at':0,'action':'skill','source':'player','ability':fire})
        attack=manual(p,'attack',{'op':'damage','damage_type':'true','scale':1,'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False}})
        times=[5,916] if case=='protect_expiry' else [5,16,66] if case.startswith('silence_') else [5]
        commands += [{'at':t,'action':'skill','source':'player','ability':attack} for t in times]
        if case.startswith('silence_'):
            p['buffs'].append({'id':'buff/independent/silence','kind':'buff','duration_seconds':1.5,'selection_flags':{'abnormal_flags':[12]}})
            aid=manual(p,'silence',{'op':'apply_buff','buff':'buff/independent/silence'});commands.append({'at':15,'action':'skill','source':'player','ability':aid})
    p['scenarioDraft']['commands']=sorted(commands,key=lambda v:v['at'])
    return p
def run(module,out,case):
    p=prepare(module,case);reg=providers();program=Compiler(providers=reg).compile(p,packages=[str(D12)]);s=Engine.create(program,providers=reg,seed=1004)
    end=940 if case=='protect_expiry' else 220 if case in ('phase0_def','phase1_live','ASPD2') else 95
    boundary=900 if case=='protect_expiry' else 25
    folder=out/case;folder.mkdir(parents=True,exist_ok=True);s.session.advance(boundary);cp=folder/'checkpoint.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.session.advance(end-boundary);r.session.advance(end-boundary);head=replay(program,s.export_replay(),providers=reg)
    assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
    observations=[thaw(e) for e in s.session.events if e['type'] in ('damage.accepted','buff.applied','buff.removed','ability.started','ability.finished')]
    normal=[(e['time'],e['payload']['amount']) for e in observations if e['type']=='damage.accepted' and str(e['payload'].get('ability','')).startswith('ability/ch8/bsnake/normal/')]
    incoming=[(e['time'],e['payload']['amount']) for e in observations if e['type']=='damage.accepted' and e['payload'].get('ability')=='ability/independent/attack']
    if case in ('phase0_def','phase1_live','ASPD2'):
        first=46 if case=='ASPD2' else 61
        burn=[e for e in observations if e['type']=='damage.accepted' and e['time'] in (first,first+30) and e['payload'].get('ability') is None]
        assert [(e['time'],e['payload']['amount']) for e in burn]==[(first,56),(first+30,62)]
        assert all(e['payload']['source']==s.session.world.resolve('boss') and e['payload']['target']==s.session.world.resolve('player') and e['payload']['damage_flags']=={'source_attack_type':'BUFF','ignore_for_sp':True} for e in burn)
        nh=[e for e in observations if e['type']=='damage.accepted' and str(e['payload'].get('ability','')).startswith('ability/ch8/bsnake/normal/')]
        assert all(e['payload']['damage_flags']=={'source_attack_type':'NORMAL','ignore_for_sp':False} for e in nh)
    if case=='phase0_def':assert normal==[(31,770),(166,770)],normal
    if case=='phase1_live':assert normal==[(31,1155),(166,1155)],normal
    if case=='ASPD2':assert normal==[(16,770),(84,770),(152,770)],normal
    if case in ('withdraw_target','unqualified_air'):assert normal==[]
    if case=='protect_expiry':assert incoming==[(5,321),(916,642)],incoming
    if case=='protect_child_only':assert incoming==[(5,642)],incoming
    if case in ('silence_normal_container','silence_native'):assert incoming==[(5,321),(16,321),(66,321)],incoming
    if case=='silence_reborn_container':assert incoming==[(5,321),(16,642),(66,321)],incoming
    if case=='samekey_group':assert incoming==[(5,321)],incoming
    if case=='silence_native':assert 12 in s.ctx.entity('boss')['components']['selection_state']['abnormal_immunes']
    (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
    with (folder/'events.jsonl').open('wb') as f:
        for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False)+'\n').encode())
    return {'case':case,'normal_packets':normal,'incoming_packets':incoming,'CP':True,'head':True,'all_events':True,'files':{str(x):sha(x) for x in folder.iterdir()}}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--module',required=True);parser.add_argument('--sha',required=True);parser.add_argument('--out',required=True);args=parser.parse_args();module=Path(args.module);out=Path(args.out)
    assert implementation_digest()==CORE and sha(module)==args.sha
    native=json.loads(SOURCE.read_bytes());assert native['variant']['native_enemy']['resolved']['attributes']['atk']==770
    assert native['frames']['Attack_A']['events'][0]['frame']==31 and native['frames']['Attack_B']['duration']['frame']==70
    assert native['consumer_merged_BB12']['reborn.atk']['value']==.5
    cases=['phase0_def','phase1_live','ASPD2','withdraw_target','unqualified_air','protect_expiry','protect_child_only','silence_normal_container','silence_reborn_container','silence_native','samekey_group'];rows=[];out.mkdir(parents=True,exist_ok=True)
    for case in cases:rows.append(run(module,out,case));print(case+' passed',flush=True)
    assert sha(module)==args.sha and implementation_digest()==CORE
    file=out/'report.json';assert not file.exists();file.write_bytes((json.dumps({'status':'11_fresh_independent_cases_passed','core':CORE,'module':str(module),'module_sha256':args.sha,'D12_sha256':sha(D12),'source_sha256':sha(SOURCE),'peer_helper_sha256':sha(Path(__file__)),'rows':rows,'scope':'Normal/protect modules only; controlled reborn attributes are not full rebirth or stage proof. Fullbusy skill arbitration reviewed separately.'},ensure_ascii=False,indent=2)+'\n').encode());print(sha(file))
if __name__=='__main__':main()

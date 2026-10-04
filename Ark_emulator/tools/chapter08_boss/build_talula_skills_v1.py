"""Four source-keyed skills plus two attacks in each mode; isolated clock core."""
import json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=ROOT.parent/'unpack_work/campaign_selection_context_clock_v1_candidate'
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter08_boss.build_talula_threshold_v3 import sha
from tools.chapter08_boss.build_dragon_fire_v1 import TIMER,CHILD,application
from tools.chapter08_boss.talula_skill_policies_v1 import providers
CORE='26c47ef786b1a6fb24c01ad65a5fbb181e27b1b0b0dd138ccd26b728163f6407'
OUT=ROOT/'packages/campaign/chapter08_consumers/boss/talula.skills.v1.reference.json'

def build():
    assert implementation_digest()==CORE
    parent=ROOT/'packages/campaign/chapter08_consumers/boss/talula.attacks.v1.reference.json'
    fire=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v1.json'
    profile=ROOT/'packages/campaign/chapter08_consumers/boss/talula.skills.source.v1.json'
    assert sha(parent)=='31ed589aa6650fd62ead713ace25480744ceeabbc7cd6ec393e26ca876800b40' and sha(fire)=='eaf1a220f4a77fb598228cbb31342c96e587e1a6190662bd1f27ea7ad9c86b02'
    p,b,s=[json.loads(x.read_bytes()) for x in (parent,fire,profile)]
    p['rules']+=b['rules'];p['buffs']+=b['buffs']
    meta=p['manifest']['metadata'];meta['source_locks'].update(b['manifest']['metadata']['source_locks'])
    meta['source_locks'].update({x.relative_to(ROOT).as_posix():sha(x) for x in (parent,fire,profile,Path(__file__),Path(__file__).with_name('talula_skill_policies_v1.py'))})
    meta['required_runtime']=CORE;meta['partial_consumer_scope']='All source normal/half attacks and four source-keyed skills with burn; nativeFSM restart/status-resistance pending.'
    meta['pending_required_consumers']=['Native FSM restart cancels oldcasts and resets source clocks at rage transition','Status resistance parent lifetime computation','Original fullstage map/routes/controls integration and independent wholeadmission']
    meta['skill_profile_source']=s;meta['burn_reference_policy']=b['manifest']['metadata']['reference_policy']
    meta['skill_clock_reference']='Activation-relative source initialcooldowns; cooldown starts cast begin (_resetMainAbilityCdWhenCastEnd0). TimeMode1 animation has mapping speed and ASPD, matching explicit dynamic clock rule; Skill_2 mapping1.2 nativeFloat32, quantized ceil(77/1.2)=65, fullceil110/1.2=92. Mode inactive clocks retain countdown; nativeFSM restart not yet consumed.'
    p['manifest']['id']='package/ch8/talula/skills_v1'
    stem='rule/ch8/talula/'
    p['rules'] += [{'id':stem+'burn_eligibility','kind':'rule','contract':'targeting.eligibility','dependencies':[stem+'eligibility'],
        'parameters':{'base_rule':stem+'eligibility','timer':TIMER},'implementation':{'type':'provider','provider':'reference.c8.talula.burn_eligibility'}},
        {'id':stem+'skill_windup','kind':'rule','contract':'ability.windup','implementation':{'type':'expression','expression':'inputs.timing_parameters.seconds / (params.mapping_speed * max(inputs.attributes.attack_speed_ratio,.01))'},'parameters':{'mapping_speed':1}},
        {'id':stem+'skill_duration','kind':'rule','contract':'ability.duration','implementation':{'type':'expression','expression':'inputs.duration_parameters.seconds / (params.mapping_speed * max(inputs.attributes.attack_speed_ratio,.01))'},'parameters':{'mapping_speed':1}}]
    p['rules']=[{**r,'implementation':{'type':'provider','provider':'reference.c8.talula.skills_behavior'}} if r['id']==stem+'behavior' else r for r in p['rules']]
    unit=p['entities'][0]['components'];entries=[]
    for row in s['selected_effective_skills'].values():
        key=row['selected_skill']['prefabKey'];mode=row['mode'];dragon=key.startswith('DragonFire');aid='ability/ch8/talula/'+str(mode)+'/'+('dragon_fire' if dragon else 'dance_fire');sid='selector/ch8/talula/'+str(mode)+'/'+('dragon_fire' if dragon else 'dance_fire');config=row['selector']['raw'];skill=row['selected_skill'];an=row['animation_binding'];event=next(e for e in an['events'] if e['name']=='OnAttack')
        selector={'id':sid,'kind':'selector','region':{'type':'all'} if dragon else {'type':'radius','radius':2.5},'filters':[{'state':'alive'}],
            'eligibility':{'rule':stem+('burn_eligibility' if dragon else 'eligibility'),'parameters':{'source_configuration':config,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}},'metadata':{'native_selector':row['selector'],'source_profile':key}}
        if dragon:selector['limit']=1
        p['selectors'].append(selector)
        wind=stem+str(mode)+('/dragon_windup' if dragon else '/dance_windup');duration=wind+'/duration';speed=an['mapping']['speed']
        for ident,contract,expr in [(wind,'ability.windup','inputs.timing_parameters.seconds'),(duration,'ability.duration','inputs.duration_parameters.seconds')]:
            p['rules'].append({'id':ident,'kind':'rule','contract':contract,'parameters':{'mapping_speed':speed},'implementation':{'type':'expression','expression':expr+' / (params.mapping_speed * max(inputs.attributes.attack_speed_ratio,.01))'}})
        effect=application() if dragon else {'op':'damage','damage_type':'arts','scale':1,'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'},'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False}}
        p['abilities'].append({'id':aid,'kind':'ability','selector':sid,'initial_cooldown_seconds':skill['initCooldown'],'cooldown_seconds':skill['cooldown'],
            'duration_seconds':an['duration']['seconds'],'activation':{'mode':'manual','condition':'inputs.resources.mode.current == '+str(mode),'parameters':{'auto_only':True,'auto_when_ready':True,'requires_targets':True,'blocks_attacks':True}},
            'target_capture':'at_cast','timeline':[{'at_seconds':event['seconds'],'effect':effect}], 'rules':{'ability.windup':wind,'ability.duration':duration,'targeting.score':stem+'score'},'metadata':{'source_skill':row}})
        unit['abilities'].append(aid)
        entries.append({'ability':aid,'priority':10+skill['priority'],'attack_clock':False,'require_attack_control':False,'condition':'inputs.source.components.resources.mode.current == '+str(mode),'parameters':{}})
    entries += [{'ability':a,'priority':0,'attack_clock':True,'require_attack_control':True,'condition':'True','parameters':{}} for a in unit['abilities'] if a.endswith(('/combat','/attack'))]
    unit['ability_arbitration']={'priority_order':'higher_first','busy':'all_casts','entries':entries}
    for row in p['behaviors'][0]['decision']['profiles']:
        row['cast_groups'].append({'key':'skill','abilities':[a for a in unit['abilities'] if '/'+str(row['mode'])+'/' in a and not a.endswith(('/combat','/attack'))]})
    f=deepcopy(p);f['scenarioDraft']={'id':'scene/talula/skills_compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':0,'col':0}}]};Compiler(providers=providers()).compile(f)
    return p

if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(OUT),'actual_compile':True,'abilities':len(p['abilities']),'complete_boss':False}))

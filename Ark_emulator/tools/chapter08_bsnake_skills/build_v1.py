"""Source-specific Ignite and explosion Buff chain; no owner overwrite."""
import json, hashlib, sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2]
CAND=ROOT.parent/'unpack_work/campaign_chapter08_joint_v4_candidate'
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter08_bsnake_skills.policies_v1 import providers
CORE='20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30'
BASE=ROOT/'packages/campaign/chapter08_consumers/bsnake'
FIRE=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v12.joint.json'
TIMER='buff/ch8/source/dragon_fire';CHILD='buff/ch8/source/dragon_fire[damage]'
MARKER='buff/ch8/source/bsnake_s_2';REIGNITE=MARKER+'[reignite]'
OWNER='unit/ch8/bsnake/cadb87696bef4de2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def application():return {'op':'buff_application','application_rule':'rule/ch8/dragon_fire/application','allowed':[TIMER,CHILD]}
def build():
    assert implementation_digest()==CORE
    source=BASE/'skills.source.v1.json';closure=BASE/'source.closure.v1.json';req=BASE/'requirements.v2.json';ranges=ROOT/'ark_emulator/data_range_table.json'
    assert sha(source)=='8e2f04a17a08add94fdb683e51c1b23669dbcb0cd2d4ab0b1391df22dc875d2a'
    assert sha(FIRE)=='a56cf27ee1c4e1a1a5a63343e90498e0a88120bea5800ed80c834d26cd25d7af'
    s=json.loads(source.read_bytes());c=json.loads(closure.read_bytes());requirements=json.loads(req.read_bytes())
    range_row=json.loads(ranges.read_bytes())['x-5'];offsets=[[v['row'],v['col']] for v in range_row['grids'] if (v['row'],v['col'])!=(0,0)]
    assert sorted(offsets)==[[-1,0],[0,-1],[0,1],[1,0]]
    stem='rule/ch8/bsnake/skills/'
    p={'schemaVersion':2,'manifest':{'id':'package/ch8/bsnake/skills_v1','requires':['preset/ark_standard'],'metadata':{
        'required_runtime':CORE,'source_locks':{str(x):sha(x) for x in (source,closure,req,FIRE,ranges,Path(__file__),Path(__file__).with_name('policies_v1.py'))},
        'owner':OWNER,'owned_ability_bindings':[],'source_body_verified':False,'client_verified':False,
        'reference_policies':['TimeMode1 affectedBySlowDown1: animation windup/fullbusy divided by ASPD with replaceable minimum .01; source interval remains unscaled and starts cast begin.',
        'postFilter0 stable actorID tie; postFilter4 lexicographic effective HATE DESC then actorID; no finite score constant.',
        'BSON AOEDamage rangeId null/useRadius false reads inline BB range_id x-5; offline extracted range table version provenance retained, not native method body proof.',
        'ON_OWNER_FINISH maps target lifecycle cleanup to on_remove; alive owner executes AdvancedApplyDamage then clear parent; dead owner only qualified AoE. Callback runs once per actual marker removal.',
        'Qualified cell grid uses project_cell geometry; excludeTarget true removes center cell, body spatial footprint deferred to client.'] }},'abilities':[],'selectors':[],'rules':[],'buffs':[]}
    p['rules'].append({'id':stem+'typed','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}})
    explode=c['BSON']['templates']['enemy_bsnake_s_2']['parsed'];finish=explode['eventToActions']['ON_BUFF_FINISH'];area_node=finish[-1]
    assert finish[1]['_damageType']=='MAGICAL' and finish[1]['_skipModifierEvent'] is False and finish[1]['_ignoreForSp'] is False
    assert area_node['_excludeTarget'] is True and area_node['_useRadius'] is False
    aoecfg={'_'+k:v for k,v in s['skills'][1]['selector']['raw'].items() if not k.startswith('_')}
    aoecfg=deepcopy(s['skills'][1]['selector']['raw']);aoecfg['_targetMotion']=3;aoecfg['_forceIgnoreCamouflage']=0
    eligibility={'rule':stem+'typed','parameters':{'source_configuration':aoecfg,'defaults':deepcopy(DEFAULT_STATE),'side_policy':'relative_ally_enemy','neutral_policy':'reject'}}
    p['rules'].append({'id':stem+'area','kind':'rule','contract':'area.members','dependencies':[stem+'typed'],'parameters':{'offsets':offsets,'eligibility':eligibility},'implementation':{'type':'provider','provider':'ark.area.qualified_cell_offsets'}})
    dmg={'op':'damage','damage_type':'arts','scale':1,'read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'},'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False}}
    alive="targets[0].components.runtime.alive"
    p['buffs']=[{'id':MARKER,'kind':'buff','duration_seconds':.029999999329447746,'stacking':{'mode':'max','max_stacks':1},'on_remove':[
        {**deepcopy(dmg),'condition':alive}, {'op':'remove_buff','buff':TIMER,'condition':alive},
        {'op':'area','center':'target','membership_rule':stem+'area','effects':[deepcopy(dmg),{'op':'apply_buff','buff':REIGNITE}]}]},
        {'id':REIGNITE,'kind':'buff','duration_seconds':.029999999329447746,'stacking':{'mode':'max','max_stacks':1},'on_remove':[{**application(),'condition':alive}]}]
    entries=[]
    for row in s['skills']:
        mode=row['mode'];native=row['component']['raw'];ignite=native['_animKey']=='Skill_1';name='ignite' if ignite else 'explode';prefix=stem+name+'/'+str(mode)
        skill=next(x for x in requirements['source_stats']['skills'] if x['prefabKey']==('Ignite' if ignite else 'DragonFireExplode'))
        assert skill['cooldown']==skill['initCooldown']==(19 if ignite else 35)
        config=row['selector']['raw'];assert config['_buffKey']=='dragon_fire' and config['_buffKeyExcluded']==(1 if ignite else 0) and config['_maxNum']==2
        p['rules'] += [{'id':prefix+'/eligibility','kind':'rule','contract':'targeting.eligibility','dependencies':[stem+'typed'],'parameters':{'base':stem+'typed','timer':TIMER,'exclude':ignite},'implementation':{'type':'provider','provider':'reference.c8.bsnake.skills.eligibility'}},
            {'id':prefix+'/selection','kind':'rule','contract':'targeting.selection','parameters':{'hate':ignite},'dependencies':['rule/ark_attribute_layers'],'implementation':{'type':'provider','provider':'reference.c8.bsnake.skills.selection'}}]
        sid='selector/ch8/bsnake/'+name+'/phase'+str(mode);aid='ability/ch8/bsnake/'+name+'/phase'+str(mode)
        p['selectors'].append({'id':sid,'kind':'selector','region':{'type':'all'},'filters':[{'state':'alive'}],'limit':2,'eligibility':{'rule':prefix+'/eligibility','parameters':{'source_configuration':config,'defaults':deepcopy(DEFAULT_STATE),'side_policy':'relative_ally_enemy','neutral_policy':'reject'}},'rules':{'targeting.selection':prefix+'/selection'}})
        for suffix,contract,expr in [('windup','ability.windup','inputs.timing_parameters.seconds'),('duration','ability.duration','inputs.duration_parameters.seconds')]:
            p['rules'].append({'id':prefix+'/'+suffix,'kind':'rule','contract':contract,'implementation':{'type':'expression','expression':expr+'/max(inputs.attributes.attack_speed_ratio,.01)'}})
        p['rules'].append({'id':prefix+'/recovery','kind':'rule','contract':'ability.recovery','parameters':{'full_seconds':row['animation']['duration']['seconds']},'implementation':{'type':'provider','provider':'reference.c8.bsnake.skills.recovery'}})
        event=next(e for e in row['animation']['events'] if e['name']=='OnAttack')
        p['abilities'].append({'id':aid,'kind':'ability','selector':sid,'initial_cooldown_seconds':skill['initCooldown'],'cooldown_seconds':skill['cooldown'],'duration_seconds':row['animation']['duration']['seconds'],
            'activation':{'mode':'manual','condition':'inputs.resources.mode.current == '+str(mode),'parameters':{'auto_only':True,'auto_when_ready':True,'requires_targets':True,'blocks_attacks':True}},
            'target_capture':'each_hit' if ignite else 'at_cast','timeline':[{'at_seconds':event['seconds'],'effect':application() if ignite else {'op':'apply_buff','buff':MARKER}}],
            'rules':{'ability.windup':prefix+'/windup','ability.duration':prefix+'/duration','ability.recovery':prefix+'/recovery'},'metadata':{'native_skill':skill,'native_component':row}})
        entries.append({'ability':aid,'priority':10+skill['priority'],'attack_clock':False,'require_attack_control':False,'condition':'inputs.source.components.resources.mode.current == '+str(mode),'parameters':{}})
        p['manifest']['metadata']['owned_ability_bindings'].append(aid)
    p['manifest']['metadata']['arbitration_entries']=entries
    return p
if __name__=='__main__':
    p=build();out=BASE/'skills.module.v1.json';assert not out.exists();out.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'module':str(out),'sha256':sha(out),'actual_compile':False}))

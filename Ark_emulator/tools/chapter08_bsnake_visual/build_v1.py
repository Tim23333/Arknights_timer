"""Exact two aura profiles and AV owned Buffs; no source actor overwrite."""
import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_wave_track_v4_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim.domains.selection import DEFAULT_STATE
BASE=ROOT/'packages/campaign/chapter08_consumers/bsnake';SOURCE=BASE/'source.closure.v1.json';CHILD='buff/ch8/source/bsnake_s[screen_attack][effect]';STEM='buff/ch8/bsnake/visual/'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert sha(SOURCE)=='742d78443641451c8b54bdf75281c33cd04c198eaee373ca95991e380f05469d'
    s=json.loads(SOURCE.read_bytes());cs=s['prefab']['components'];h={v['path_id']:v for v in s['prefab']['hierarchy']};dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';text=dump.read_text(encoding='utf8');start=text.index('public enum AuraAbility.SelfOption');end=text.index('\n// Namespace:',start);enum=text[start:end];assert 'DEFAULT = 0;' in enum and 'EXCLUDE = 2;' in enum
    start=text.index('public enum AbilityStandard.Event');end=text.index('\n// Namespace:',start);events=text[start:end];assert 'ON_ATTACHED = 0;' in events and 'ON_DETACHED = 1;' in events
    p={'schemaVersion':2,'manifest':{'id':'package/ch8/bsnake/visual_v1','requires':['preset/ark_standard'],'metadata':{'source_locks':{str(v):sha(v) for v in (SOURCE,dump,Path(__file__))},'owner':'unit/ch8/bsnake/cadb87696bef4de2','mode_aura_profiles':[],'initial_owned_buffs':[],'rebirth_retained_buffs':[],'terminal_retained_buffs':[],
        'scope':'Actual headless visual Buff members and attachment/detachment state, no new damage/stat/control. Renderer not rendered. Source interval0 means per existing Aura reconcile cadence reference.',
        'self_enum':enum,'event_enum':events,'reference_policy':'DEFAULT0 uses original typed TargetValidator; EXCLUDE2 additionally rejects source identity. Mode2/3 originalhierarchy binds owned toggle to parent Aura. Mode0/1 detach/retirement cleanup. Source samekey max1/nonindependent uses generic shared child leases; does not refresh unrelated same-IDexternal marker.'}},'buffs':[],'rules':[],'selectors':[]}
    p['rules'].append({'id':'rule/ch8/bsnake/visual/typed','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}})
    p['buffs'].append({'id':CHILD,'kind':'buff','stacking':{'mode':'refresh','max_stacks':1},'effects':[{'op':'emit','target':'selected','event':'source.bsnake.visual.member.attached','payload':{'native_buff_key':'bsnake_s[screen_attack][effect]','effect_key':'enemy_bsnake_reborn_01_buff'}}],
        'on_remove':[{'op':'emit','target':'selected','event':'source.bsnake.visual.member.detached','payload':{'native_buff_key':'bsnake_s[screen_attack][effect]','effect_key':'enemy_bsnake_reborn_01_buff'}}], 'metadata':{'pure_AV':True,'source_raw':cs['5873077423754671492']['raw']['_buffs'][0]}})
    for mode,pid,eid in ((2,'5873077423754671492','-3263198506118384252'),(3,'-5705813583043398268','-3987919389912304252')):
        aura=cs[pid];raw=aura['raw'];validator=cs[str(raw['_targetValidator']['m_PathID'])];b=raw['_buffs'][0]
        assert len(raw['_buffs'])==1 and b['templateKey']=='empty' and b['loadFromDB']==0 and b['buffKey']=='bsnake_s[screen_attack][effect]'
        assert all(not v for v in b['attributes'].values()) and not b['blackboard'] and raw['_effects']==[] and raw['_passiveBuffs']==[]
        assert raw['_removeBuffWhenAbilityDetached']==1 and raw['_selfOption']==(2 if mode==2 else 0)
        config={'_'+k:v for k,v in validator['raw']['_targetOptions'].items()};config['_forceIgnoreCamouflage']=0;config['_needProfessionMask']=0
        assert config['_targetSide']==2 and config['_targetMotion']==3 and config['_targetCategory']==1 and config['_ignoreTargetFree']==1
        sid='selector/ch8/bsnake/visual/mode'+str(mode);parent=STEM+'aura/mode'+str(mode);master=STEM+'mode_controller/'+str(mode);rule='rule/ch8/bsnake/visual/mode'+str(mode)
        filters=[{'state':'alive'}]
        if raw['_selfOption']==2:filters.append({'exclude_source':True})
        p['selectors'].append({'id':sid,'kind':'selector','region':{'type':'all'},'filters':filters,'eligibility':{'rule':'rule/ch8/bsnake/visual/typed','parameters':{'source_configuration':config,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}}})
        p['rules'].append({'id':rule,'kind':'rule','contract':'passive.toggle','implementation':{'type':'expression','expression':'inputs.owner.components.resources.mode.current != '+str(mode)}})
        em=cs[eid]['raw'];assert em['_startEv']==0 and em['_endEv']==1 and em['_effect']=='screen_bsnake' and em['_isCameraEffect']==0
        payload={'mode':mode,'source_path_id':int(pid),'effect_key':em['_effect'],'is_camera_effect':False,'native_event':'ON_ATTACHED'}
        p['buffs'] += [{'id':parent,'kind':'buff','aura':{'selector':sid,'buff':CHILD,'lease_policy':{'mode':'shared','identity':['definition','target'],'source_binding':'oldest_live_lease','external_child_collision':'reject'}},
            'effects':[{'op':'emit','target':'source','event':'source.bsnake.visual.screen.attached','payload':payload}],
            'on_remove':[{'op':'emit','target':'source','event':'source.bsnake.visual.screen.detached','payload':{**payload,'native_event':'ON_DETACHED'}}]},
            {'id':master,'kind':'buff','removal':{'on_target_death':'retain','on_source_death':'retain'},'toggle':{'rule':rule,'buff':parent,'initial_enabled':False,'restore_delay_seconds':0}}]
        p['manifest']['metadata']['initial_owned_buffs'].append(master)
        p['manifest']['metadata']['rebirth_retained_buffs'] += [master,parent]
        p['manifest']['metadata']['terminal_retained_buffs'] += [master,parent]
        p['manifest']['metadata']['mode_aura_profiles'].append({'mode':mode,'native_aura':aura,'validator':validator,'screen_effect_emitter':cs[eid]})
    out=BASE/'visual.module.v1.json';assert not out.exists();out.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()

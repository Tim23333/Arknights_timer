"""Source-level inventory: consumed mechanics versus AV and nativebody policy."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'packages/campaign/chapter08_consumers/bsnake'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    source=BASE/'source.closure.v1.json';p=json.loads(source.read_bytes());cs=p['prefab']['components'];h={v['path_id']:v for v in p['prefab']['hierarchy']};boss=BASE/'four_modes.wave_source.v5.json';defs={d['id']:d for d in json.loads(boss.read_bytes())['definitions']}
    def path(pid):
        parts=[]
        while pid in h:parts.append(h[pid]['name']);pid=h[pid]['parent_path_id']
        return '/'.join(reversed(parts))
    drivers=[]
    for pid,c in cs.items():
        if c['native_class']!='ThreePartChannelingAnimation':continue
        r=c['raw'];keys=r['_default'];anim={key:p['frames'].get(value) if value else None for key,value in keys.items()}
        fields=[]
        for key,value in r.items():
            if key in ('m_GameObject','m_Enabled','m_Script','m_Name'):status='exact structural binding retained'
            elif key=='_default':status='actual native loop/end keys plus source durations retained; renderer not played'
            elif key=='_fireAttackFinishEvent':status='native value1 retained; logical screen/ability callbacks consumed separately, native animation-end→AttackFinish timing not executed or proven'
            else:status='exact source flag retained as AV/native animation behavior; no separate effect invented'
            fields.append({'field':key,'raw':value,'status':status})
        drivers.append({'component_path_id':int(pid),'source_hierarchy':path(c['gameobject_path_id']),'native_class':c['native_class'],'raw':r,'field_checklist':fields,'source_animation_duration_and_events':anim,'pending':'End83/37 frame offsets are not added to logical28s life or reset clocks without source-specific policy/counter. _fireAttackFinishEvent1 not silently treated as inert; native driver-toFSM end ordering remains explicit reference boundary.'})
    assert len(drivers)==2 and not [c for c in cs.values() if c['native_class']=='ThreePartChannelingAudio']
    hint=cs['8469810055483258244'];cancel=defs['buff/ch8/source/bsnake_t[hint_cancel]'];native_cancel=p['BSON']['templates']['enemy_bsnake_s[final_screen_attack]']['parsed']['eventToActions']['ON_BUFF_START'][0]['_buff']
    hintcheck={'native_hint':hint,'native_cancel_inline':native_cancel,'implemented_cancel':cancel,'actual_hint_owner_ability':defs['ability/ch8/bsnake/hint'],
        'field_checklist':[{'field':k,'raw':v,'consumer':'Original35 registered positions/7phase keys and actual hint.clear/show observed AV policy' if k in ('_effectKey','_cancelBuffKey') else 'Exact structural/default source flags retained'} for k,v in hint['raw'].items()],
        'semantic_policy':'Native hint_cancel permanent marker is actually installed at terminal start; hint.clear actual callback exists. Currentshow conditionmode<3 maps native marker intention for original4mode actor, not generalized nativeBuff-sourcebody implementation. Renderer highlight not rendered; arbitrarycancelmarker outsidemode3 may differ and is an explicit pending generalized policy.'}
    aure=[]
    for pid in ('5873077423754671492','-5705813583043398268'):
        c=cs[pid];r=c['raw'];assert all(not v for v in r['_buffs'][0]['attributes'].values());aure.append({'path_id':int(pid),'path':path(c['gameobject_path_id']),'raw':r,'no_attributes_or_flags_or_damage':True,'real_consumer':'visual.module.v3 generic shared Aura+ownedtoggles source mode2/3; real child Buff per currently eligible target; typed AV effect attach/detach observations',
            'reference_flags':['_interval0 reconciles existing domain cadence','single-layer currentstage satisfies onlyDetectCurrentMapLayer0; no crosslayer renderer implemented','excludeReborningEntity0/removeBuffIncludeReborning0 targetwaiting retention semantics not independently established; fixed12 no targetrebirth in these probes','clearBuffsWhenDisappear0 hidden-source visual persistence remains untested reference; no HIDE added to selectedBossroute']})
    mechanics={'normal':['twoexact31PURE/70busy/135interval, live770→1155 and protection fields, nativeimmunities'],'Ignite':['exact35/full59,19/19,max2excludeDragonFire,atOnAttackrecapture,BB30.5/50/180/30'],'Explode':['exact31/full59,35/35,AlwaysNoTarget,marker1tick AdvDamage→clearparent→qualifiedx5AoE→reignite1tick'],'Reborn':['maxcount2/5s/+50%HPATK/first100%PRTSreference, rawrecharge.5 remainsunknown; extraPreset0 terminalHP0 finite28s'],'Wave':['trueDefaultTrack/falseRebornRelease/BGM exactBSONpath and finiteflags sourceV5/core4bf; futureRootjoint82 proof has separateidentity'],'Screen':['mode2/3 noordinary, native7rows/28prototypes/10volley, interval2/duration28/invul15; finalterminalretire authentic'],'SummonHint':['75init/50cycle,7loopphases/native10registeredactors/real25SP Flame source; hint AV effect+cancel as above']}
    structure=[]
    for pid,c in cs.items():
        name=c['native_class'];status='source retained, renderer/structural ancillary' if name in ('SkeletonAnimation','SingleSpineAnimator','SpineEffectEmitter','ShadowController','BoneFollower','FaceSwitcher','UberEffectEmitter') else 'included in exact gameplay source closure; see mechanism group/reference policy'
        if name in ('ThreePartChannelingAnimation','ScreenEffectEmitter','GlobalAuraAbility','BsnakeSummonHint'):status='detailed checklist above'
        structure.append({'path_id':int(pid),'class':name,'path':path(c['gameobject_path_id']),'status':status})
    out=BASE/'finalBoss.source_fields.checklist.v1.json';assert not out.exists();result={'schema':'ark-sim/bsnake-source-fields-checklist/v1','source_locks':{str(x):sha(x) for x in (source,boss,BASE/'visual.module.v3.json',Path(__file__))},'mechanism_groups':mechanics,'visual_aura':aure,'three_part_channeling_animation_not_audio':drivers,'spine_audio_event_timing':{k:v for k,v in p['frames'].items() if k.startswith('Reborn_')},'audio_status':'No ThreePartChannelingAudio source component exists in exact closure. OnPlayAudio Spine events are real0/29/73 etc source AV timing; sound signal assets/playback mapping not decoded here, no imaginaryaudio component or HP/gameplay mutation introduced.',
        'hint_cancel':hintcheck,'all_native_component_inventory':structure,'stage_admission_scope':'VisualAura author requires Root composition/independentmembership on actualnewBoss+stage; native animation-end callback ordering, AVrenderer, rechargeparameter mapping and expanded hidden/reborn-target policies remain explicit replaceable boundaries. Do not equate sourceinventory with everyfield actualclientconsumed or fullBoss approval.','renderer_rendered':False,'native_method_bodies_verified':False,'whole_stage_approved':False}
    out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()

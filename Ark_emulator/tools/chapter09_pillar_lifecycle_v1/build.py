"""Native source pillar state chain, with declared replaceable spatial policy."""
import json,hashlib,base64
from pathlib import Path
from tools.chapter09_pillar_v1 import build_payload as payload
ROOT=Path(__file__).resolve().parents[2]
PREFIX='ch9/pillar/'
START='buff/'+PREFIX+'startdead';READY='buff/'+PREFIX+'candead';EFFECT='buff/'+PREFIX+'ready_effect';IMMUNE='buff/'+PREFIX+'abnormalimmunes'
UNDEAD='buff/'+PREFIX+'undead';ONDEAD='buff/'+PREFIX+'ondead'
def ids(actor):return {b['definition'] for b in actor['components'].get('buffs',{}).get('instances',[])}
def gate(inputs,params,context):
    source=inputs['source'];target=inputs['target'];state=inputs['state'];effect=inputs['request']['effect']
    if source and 'dupilr' in source.get('tags',[]):return {'accepted':False,'actions':['mark_ready']}
    if not source or effect.get('environmental') or effect.get('node_is_env_damage') or state['stage'] in ['damaged','collapsing']:return {'accepted':False,'actions':[]}
    pos=source['components']['spatial']['position'];center=target['components']['spatial']['position']
    from ark_sim.domains.spatial import project_cell
    a=project_cell(pos);b=project_cell(center)
    return {'accepted':(a[0]-b[0],a[1]-b[1]) in params['hit_offsets'],'actions':[]}
def plan(inputs,params,context):
    stage=inputs['state']['stage'];target=inputs['target'];source=inputs['source']
    if stage=='normal' and READY not in ids(target):return {'action':'defer','stage':'damaged','actions':['begin','ready']}
    if stage in ['normal','ready'] and READY in ids(target) and source and inputs['request']['operation']=='damage':
        p=source['components']['spatial']['position'];q=target['components']['spatial']['position'];dr=p['row']-q['row'];dc=p['col']-q['col']
        # Native SwitchSourceDirection branches collapse AWAY from attacker.
        direction=('left' if dc>0 else 'right') if abs(dc)>=abs(dr) else ('up' if dr>0 else 'down')
        return {'action':'defer','stage':'collapsing','actions':['collapse_'+direction]}
    return {'action':'none','stage':stage,'actions':[]}
def providers():return {**payload.providers(),'reference.ch9.pillar_gate':{'callable':gate,'version':'native-x5-cell-projection-v1'},'reference.ch9.pillar_plan':{'callable':plan,'version':'source-relative-opposite-dominant-axis-v1'}}
def build():
    p=payload.build();closure_path=ROOT/'packages/campaign/chapter09_consumers/pillars/source.closure.v1.json';closure=json.loads(closure_path.read_bytes())
    assert len(closure['required_keys'])==8 and not closure['closure']['missing_templates']
    for row in closure['closure']['templates'].values():assert hashlib.sha256(base64.b64decode(row['document_base64'])).hexdigest()==row['document_sha256']
    range_path=ROOT/'ark_emulator/data_range_table.json';native_range=json.loads(range_path.read_bytes())['x-5'];offsets=[[x['row'],x['col']] for x in native_range['grids']]
    native=json.loads(payload.SOURCE.read_bytes());durations=[]
    def visit(value):
        if isinstance(value,dict):
            if value.get('key')=='dupilr_trait[startdead].duration':durations.append(value['value'])
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(native['stages']);assert durations and set(durations)=={2.0}
    assert native_range['id']=='x-5'
    p['rules'] += [{'id':'rule/'+PREFIX+'gate','kind':'rule','contract':'resource.depletion','parameters':{'hit_offsets':offsets},'implementation':{'type':'provider','provider':'reference.ch9.pillar_gate'}},{'id':'rule/'+PREFIX+'depletion','kind':'rule','contract':'resource.depletion','implementation':{'type':'provider','provider':'reference.ch9.pillar_plan'}}]
    shared={'mode':'refresh','identity':['definition','target'],'max_stacks':1}
    p['buffs'] += [{'id':START,'kind':'buff','stacking':shared,'selection_flags':{'abnormal_flags':[5,2,15]}},{'id':READY,'kind':'buff','stacking':shared},{'id':EFFECT,'kind':'buff','stacking':shared},{'id':IMMUNE,'kind':'buff','selection_flags':{'abnormal_flags':[8,21],'abnormal_immunes':[0,16,12,23,13],'abnormal_combo_immunes':[0]}}]
    native_buffs={b['buffKey']:b for row in native['prefabs']['trap_043_dupilr']['components'].values() if row['native_class']=='PassiveBuffAbility' for b in row['raw'].get('_buffs',[])}
    assert native_buffs['dupilr_trait[undead]']['attributes']['abnormalFlags']==[6]
    p['buffs'] += [{'id':UNDEAD,'kind':'buff','selection_flags':{'abnormal_flags':[6]},'metadata':{'native_inline':native_buffs['dupilr_trait[undead]'],'consumer':'exact-zero opt-in lifecycle holds HP0, never HP1'}},{'id':ONDEAD,'kind':'buff','metadata':{'native_inline':native_buffs['dupilr_trait[ondead]'],'consumer':'resource.depletion source-owned actual damage -> finite possessed collapse cast'}}]
    retained=[payload.TRAIT,START,READY,IMMUNE,EFFECT,UNDEAD,ONDEAD]
    clear={'op':'remove_buff','buff':payload.TRAIT,'remove_all':True,'parameters':{'retain_definitions':retained}}
    actions={'mark_ready':{'at_seconds':0,'effects':[{'op':'apply_buff','buff':READY}]},'begin':{'at_seconds':0,'effects':[{'op':'apply_buff','buff':START},clear,{'op':'apply_buff','buff':EFFECT}]},'ready':{'at_seconds':2,'next_stage':'ready','effects':[{'op':'remove_buff','buff':START},{'op':'apply_buff','buff':READY},clear]}}
    for direction in ['right','left','up','down']:actions['collapse_'+direction]={'at_seconds':0,'effects':[clear],'owned_ability':'ability/'+PREFIX+'collapse_'+direction}
    body=p['entities'][0]['components'];body['buffs']['initial'] += [IMMUNE,UNDEAD,ONDEAD];body['depletion']={'resource':'hp','rule':'rule/'+PREFIX+'depletion','damage_gate_rule':'rule/'+PREFIX+'gate','initial_stage':'normal','parameters':{},'stages':{'normal':{'active':True,'selectable':True},'damaged':{'active':False,'selectable':False},'ready':{'active':True,'selectable':True},'collapsing':{'active':True,'selectable':False}},'actions':actions}
    p['manifest']['id']='package/ch9/pillar/lifecycle_v1';p['manifest']['metadata'].update({'source_closure_sha256':hashlib.sha256(closure_path.read_bytes()).hexdigest(),'source_range':native_range,'range_source_sha256':hashlib.sha256(range_path.read_bytes()).hexdigest(),'reference_policy':{'source_range':'x-5 raw grids applied via project_cell; client Collider edge acceptance remains reference','direction':'dominant source-to-pillar axis; opposite direction; horizontal tie is explicitly replaceable','native_state':'HP exactly0; startdead2s -> candead only; later real in-range damage launches possessed collapse ability'},'whole_pillar_complete':False,'pending':['visual-only animator/effect rendering','client Collider and SwitchSourceDirection tie comparison','durable Buff distinction not represented by generic model']})
    return p

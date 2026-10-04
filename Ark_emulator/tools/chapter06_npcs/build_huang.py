"""Exact native no-skill Blaze NPC with normal3-target trait and source talents."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim.domains.selection import DEFAULT_STATE
SOURCE=ROOT/'packages/campaign/chapter06_predefines/source.reference.json';INPUTS=ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json'
TALENTS=ROOT/'packages/campaign/chapter06_npcs/huang_talents.v5.model.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    source=json.loads(SOURCE.read_bytes());data=json.loads(INPUTS.read_bytes());row=next(r for r in data['records'] if r['character_id']=='char_017_huang')
    stats=row['stats'];cfg=deepcopy(source['prefabs']['char_017_huang']['components']['8461021441099313565']['raw'])
    assert cfg['_limitedMaxTargetNumToBlockedCnt']==1 and stats['blockCnt']==3
    assert row['skill_index']==-1 and row['normal_attack_source']['raw']['_selectTargetSource']==1
    p=json.loads(TALENTS.read_bytes());p['manifest']['id']='package/ch6/npc/huang_complete_reference'
    p['manifest']['metadata'].update(source_locks={str(SOURCE.relative_to(ROOT)):sha(SOURCE),str(INPUTS.relative_to(ROOT)):sha(INPUTS),str(TALENTS.relative_to(ROOT)):sha(TALENTS)},
        native_no_selected_skill=True,native_config=row['native_instance'],selector_source=cfg,ordinary_attack_source=row['normal_attack_source'],
        pending_policies=['Actual max animation scale2 clamp calibration','BlockedOrAdvancedSelector native order vs generic ordering','Death/HP floor hook native callback ordering'])
    defaults=deepcopy(DEFAULT_STATE);defaults.update(side=0,motion=1,category=1,unit_type=1)
    uid='unit/ch6/npc/char_017_huang';aid='ability/ch6/npc/huang_normal';sid='selector/ch6/npc/huang';eligible='rule/ch6/npc/huang_eligible';windup='rule/ch6/npc/huang_windup'
    p['rules']+=[{'id':eligible,'kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}},
        {'id':windup,'kind':'calculation_rule','contract':'ability.windup','parameters':{'minimum_speed':.01},
            'implementation':{'type':'expression','expression':'inputs.timing_parameters.seconds/max(inputs.attributes.attack_speed_ratio,params.minimum_speed)'}}]
    p['entities']=[{'id':uid,'kind':'entity','tags':['player','ground','native_npc'],'metadata':{'native_character':'char_017_huang','native_instance':row['native_instance']},
        'components':{'attributes':{'base':{'max_hp':stats['maxHp'],'atk':stats['atk'],'def':stats['def'],'mres':stats['magicResistance'],
            'attack_interval':stats['baseAttackTime'],'attack_speed_ratio':1,'block_count':3,'one_minus_status_resistance':1}},
            'resources':{'hp':{'initial':stats['maxHp'],'capacity_attribute':'max_hp','role':'health'}},'spatial':{},'selection_state':defaults,
            'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[aid],
            'buffs':{'initial':['buff/ch6/npc/huang_once','buff/ch6/npc/huang_resistance_wait']}}}]
    ranges=ROOT/'ark_emulator/data_range_table.json';rangevalue=json.loads(ranges.read_bytes())[row['range_id']]
    p['selectors']=[{'id':sid,'kind':'selector','region':{'type':'grid_offsets','offsets':[[-c['row'],c['col']] for c in rangevalue['grids']]},
        'filters':[{'tag':'enemy'},{'state':'alive'}],'limit_attribute':'block_count','parameters':{'include_blocked':True},
        'eligibility':{'rule':eligible,'parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}}}]
    p['abilities']=[{'id':aid,'kind':'ability','activation':{'mode':'automatic_attack','settle_blocking':True,'parameters':{'auto_only':True}},
        'rules':{'ability.windup':windup},'selector':sid,'target_capture':'at_cast','timeline':[{'at_seconds':10/30,
            'effect':{'op':'damage','damage_type':'physical','scale':1,'damage_flags':{'source_attack_type':'NORMAL','ignore_for_sp':False}}}]}]
    path=ROOT/'packages/campaign/chapter06_npcs/huang.model.json';assert not path.exists();path.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(path),'hp':stats['maxHp'],'atk':stats['atk'],'block':3,'selected_skill':None}))


if __name__=='__main__':main()

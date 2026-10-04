"""Native E2 no-potential Blaze low-HP one-shot talent and delayed resistance."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter06_predefines/source.reference.json';INPUTS=ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json'
OUT=ROOT/'packages/campaign/chapter06_npcs/huang_talents.model.json'
PARENT='buff/ch6/npc/huang_once';LOCK='buff/ch6/npc/huang_lock';RESIST='buff/ch6/npc/huang_resistance'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    source=json.loads(SOURCE.read_bytes());inputs=json.loads(INPUTS.read_bytes());row=next(r for r in inputs['records'] if r['character_id']=='char_017_huang')
    bb={x['key']:x['value'] for x in row['selected_talents'][0]['candidate']['blackboard']}
    resistance={x['key']:x['value'] for x in row['selected_talents'][1]['candidate']['blackboard']}
    assert bb=={'hp_ratio':.25,'huang_t_1[heal].hp_ratio':.5,'huang_t_1[lock].min_hp_ratio':.5,'huang_t_1[lock].duration':6.0}
    assert resistance=={'one_minus_status_resistance':-.5,'interval':15.0}
    nodes=source['bson_templates']['templates'];assert 'ON_TAKE_DAMAGE' in nodes['huang_t_1[lock]']['parsed']['eventToActions']
    assert nodes['huang_t_1[heal]']['parsed']['eventToActions']['ON_BUFF_START'][0]['_healTarget']=='BUFF_OWNER'
    amount='min(inputs.effect.settlement.amount,max(0,inputs.target.components.resources.hp.current-'+str(bb['huang_t_1[lock].min_hp_ratio'])+'*inputs.target.components.attributes.base.max_hp))'
    guard="{'accepted':inputs.effect.settlement.accepted,'amount':min(inputs.effect.settlement.amount,max(0,inputs.target.components.resources.hp.current-1)),'allocations':[],'events':[]}"
    locked="{'accepted':inputs.effect.settlement.accepted,'amount':"+amount+",'allocations':[],'events':[]}"
    return {'schemaVersion':2,'manifest':{'id':'package/ch6/npc/huang_talents','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{str(SOURCE.relative_to(ROOT)):sha(SOURCE),str(INPUTS.relative_to(ROOT)):sha(INPUTS)},'builder_sha':sha(Path(__file__)),
        'policies':{'one_shot':'Source UNDEADABLE6 keeps HP>=1 until below25% event applies 50%maxHP heal, 6s lock and removes the real parent handle.',
            'ordering':'Full damage settlement before owner damage event; deferred reaction is explicit model policy, no native same-frame callback body claim.',
            'resistance':'Source15s first trigger installs -0.5 one_minus_status_resistance once, independent of no selected skill.',
            'scope':'Native E2L25 no-potential/no-skill Blaze passive effects only; ordinary attack authored separately.'},
        'complete_source_policies':False,'whole_stage_executed':False,'client_verified':False}},
        'rules':[{'id':'rule/ch6/npc/huang_undead','kind':'calculation_rule','contract':'damage.pipeline','implementation':{'type':'expression','expression':guard}},
            {'id':'rule/ch6/npc/huang_hp_lock','kind':'calculation_rule','contract':'damage.pipeline','implementation':{'type':'expression','expression':locked}}],
        'buffs':[{'id':PARENT,'kind':'buff','selection_flags':{'abnormal_flags':[6]},
            'damage_hooks':[{'phase':'after','rule':'rule/ch6/npc/huang_undead'}],
            'events':[{'event':'damage.accepted','condition':'inputs.payload.target == context.owner.id and context.owner.components.resources.hp.current < .25 * context.owner.components.attributes.base.max_hp',
                'effects':[{'op':'regenerate','parameters':{'max_hp_ratio':.5}}, {'op':'apply_buff','buff':LOCK}, {'op':'remove_buff','buff':PARENT}]}]},
            {'id':LOCK,'kind':'buff','duration_seconds':6,'damage_hooks':[{'phase':'after','rule':'rule/ch6/npc/huang_hp_lock'}]},
            {'id':RESIST,'kind':'buff','modifiers':[{'attribute':'one_minus_status_resistance','layer':'flat','value':-.5}]},
            {'id':'buff/ch6/npc/huang_resistance_wait','kind':'buff','interval_seconds':15,
             'effects':[{'op':'apply_buff','buff':RESIST},{'op':'remove_buff','buff':'buff/ch6/npc/huang_resistance_wait'}]}]}


def main():
    assert not OUT.exists();OUT.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(OUT)}))


if __name__=='__main__':main()

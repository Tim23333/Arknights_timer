"""Correct dynamic maxHP threshold and dynamic heal-free without kernel edits."""
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter06_npcs.build_huang_talents import PARENT,LOCK


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    folder=ROOT/'packages/campaign/chapter06_npcs';base=folder/'huang_talents.v5.model.json'
    p=json.loads(base.read_bytes());reaction='buff/ch6/npc/huang_reaction'
    app='rule/ch6/npc/huang_low_hp';eligible='rule/ch6/npc/huang_heal_eligible'
    selector='selector/ch6/npc/huang_heal_self'
    defaults=deepcopy(DEFAULT_STATE);defaults.update(side=0,motion=1,category=1,unit_type=1)
    cfg={'_targetSide':1,'_targetCategory':7,'_targetMotion':3,'_professionMask':0,'_unitTypeMask':0,
         '_ignoreTargetFree':1,'_onlyIgnoreSomeOfTargetFreeCase':0,'_excludeSomeAbnormalFlags':0,
         '_needProfessionMask':0,'_ignoreAllyTargetFree':1,'_ignoreHealFree':0,
         '_ignoreMotionMode':1,'_forceIgnoreCamouflage':1,'_checkUnitType':0}
    p['rules'] += [{'id':app,'kind':'calculation_rule','contract':'buff.application',
        'implementation':{'type':'provider','provider':'reference.c6.npc_low_hp'},
        'parameters':{'reaction':reaction,'threshold':.25}},
        {'id':eligible,'kind':'rule','contract':'targeting.eligibility',
         'implementation':{'type':'provider','provider':'reference.c6.npc_owner_heal'}}]
    # HealingViaMaxHpRatio ignores neither dynamic HEAL_FREE nor native heal-free.
    # Other targeting gates are irrelevant to a direct BUFF_OWNER heal.
    p['selectors']=[{'id':selector,'kind':'selector','region':{'type':'all'},
        'filters':[{'state':'alive'}],'limit':1,
        'eligibility':{'rule':eligible,'parameters':{'source_configuration':cfg,
            'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':defaults}}}]
    event=next(b for b in p['buffs'] if b['id']==PARENT)['events'][0]
    heal=deepcopy(event['effects'][0]);heal.pop('condition');heal['selector']=selector
    heal['parameters']={'healing':True}
    event['condition']='inputs.payload.target == context.owner.id'
    event['effects']=[{'op':'buff_application','application_rule':app,'allowed':[reaction]}]
    # A one-quantum reaction executes on-start effects. Its actual applied
    # event asks the parent to remove itself; no construction back-edge.
    p['buffs'].append({'id':reaction,'kind':'buff','effects':[heal,
        {'op':'apply_buff','buff':LOCK}]})
    parent=next(b for b in p['buffs'] if b['id']==PARENT)
    parent['events'].append({'event':'buff.applied',
        'condition':"inputs.payload.target == context.owner.id and inputs.payload.buff == '"+reaction+"'",
        'effects':[{'op':'remove_buff','buff':PARENT}]})
    p['manifest']['metadata'].update(parent_sha=sha(base),builder_sha=sha(Path(__file__)),
        reference_policy='Effective maxHP threshold; derived dynamic heal-free gate; source reaction ordering remains explicit policy')
    target=folder/'huang_talents.v7.model.json';assert not target.exists()
    target.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':sha(target)}))


if __name__=='__main__':main()

"""Keep source flags separate from the generic exit accounting kernel."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter06_plans/source.plan.json'


def build():
    raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()=='d310c3f98408b2686be3f065ab6212e552451b7505ec083a62418db564941608'
    native=json.loads(raw)['stages']['level_main_06-15']['native_document']
    action=native['waves'][0]['fragments'][0]['actions'][0]
    assert action['actionType']=='SPAWN' and action['key']=='enemy_1510_frstar2_s'
    flag=action['isUnharmfulAndAlwaysCountAsKilled'];assert type(flag) is bool and flag is True
    rule={'id':'rule/ch6/training_exit_credit','kind':'calculation_rule','contract':'lifecycle.exit',
        'implementation':{'type':'expression','expression':"{'base_life_loss': 0 if inputs.exit_parameters.unharmful else inputs.exit_parameters.loss, 'kills_delta': 1 if inputs.exit_parameters.always_count_as_killed else 0, 'leaks_delta': 0 if inputs.exit_parameters.always_count_as_killed else 1}"}}
    return {'schemaVersion':2,'manifest':{'id':'package/ch6/training_exit_credit','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{str(SOURCE.relative_to(ROOT)):hashlib.sha256(raw).hexdigest()},
        'native_flags':{'combined_action_flag':flag,'unharmful':flag,'always_count_as_killed':flag},
        'scope':'Source-declared options consumed by explicit exit-only reference policy, no enemy attack/boss/NPC/story implementation',
        'reference_policy':'Unharmful prevents base life loss on route exit; alwaysCountAsKilled gives scenario kill credit on exit. Real exited actor is not combat dead. Does not suppress outgoing combat damage.',
        'native_body_verified':False,'whole_stage_executed':False,'client_verified':False}},'rules':[rule],
        'actionLifecycleProfile':{'native_id':'level_main_06-15','wave':0,'fragment':0,'action':0,
            'native_action':action,'lifecycle':{'exit_rule':rule['id'],
                'exit_parameters':{'unharmful':flag,'always_count_as_killed':flag,'loss':1}}}}


def main():
    out=ROOT/'packages/campaign/chapter06_exit_accounting/reference_policy.json';assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True)
    p=build();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'sha':hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__=='__main__':main()

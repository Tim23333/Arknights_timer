"""Immutable author receipt, literal source BB guard and explicit integration scope."""
import json
from pathlib import Path
from tools.chapter08_bsnake_skills.build_v1 import BASE,ROOT,FIRE,sha,CORE
def main():
    source=BASE/'skills.module.v4.json';assert sha(source)=='9a11e1b3122b1a6f268489f3d1e9956d73c5d91e2eed9b0da3e7076a022d0a6a'
    p=json.loads(source.read_bytes());req=json.loads((BASE/'requirements.v2.json').read_bytes());fire=json.loads(FIRE.read_bytes())
    params=next(r for r in fire['rules'] if r['id']=='rule/ch8/dragon_fire/application')['parameters']
    for skill in req['source_stats']['skills']:
        if skill['prefabKey'] not in ('Ignite','DragonFireExplode'):continue
        bb={r['key']:r['value'] for r in skill['blackboard']}
        assert {k:bb['dragon_fire.'+k] for k in ('duration','baseDamage','addOnDamage','addOnDuration')}=={'duration':30.5,'baseDamage':50,'addOnDamage':180,'addOnDuration':30}
        assert (params['duration'],params['base'],params['addition'],params['increase_duration'])==(30.5,50,180,30)
        assert skill['spCost']==0 and skill['priority']==0
    reports=[BASE/'skills_author_v4/report.json',BASE/'skills_boundaries_v3/report.json',BASE/'skills_clocks_v1/report.json']
    counts=[4,7,2]
    for path,n in zip(reports,counts):
        r=json.loads(path.read_bytes());assert r['core']==CORE and r['module_sha256']==sha(source) and len(r['rows'])==n
        assert all(v['CP'] and v['head'] for v in r['rows'])
    files=[source,BASE/'skills.source.v1.json',BASE/'source.closure.v1.json',BASE/'requirements.v2.json',BASE/'range.source.v1.json',ROOT.parent/'unpack_work/campaign_tables/range_table.json',FIRE,ROOT.parent/'data/anon_textassets/buff_template_data.dat']
    files += list((ROOT/'tools/chapter08_bsnake_skills').glob('*.py'))
    for folder in ('skills_author_v4','skills_boundaries_v3','skills_clocks_v1'):
        files += [v for v in (BASE/folder).rglob('*') if v.is_file()]
    out=BASE/'skills.final.author.v1.json';assert not out.exists();data={'schema':'ark-sim/bsnake-skills-author/v1','status':'13_actual_source_policy_cases_passed','core':CORE,'module':str(source),'module_sha256':sha(source),'pins':{str(x):sha(x) for x in files},
        'source_explode_BSON':'07cb1d02604e0a5c73c6104ef488be43f365db5f315ec4c44d3fe8dffd8b67ef','source_reignite_BSON':'15c55b28798f5d9ae2c2fb95098bdffa295836494057c51d952d56e3bb5ae0c8',
        'source_consumed':['Exact modes0/1 skill PPtrs/Spine35 and31/full59','Ignite19/19 with max2 unburned HATE gate and atOnAttack recapture','Explode35/35 AlwaysTrigger even empty selection; max2 burned atCast','Actual short marker1tick: live center arts then remove parent, qualified x-5 neighbors excluding center, normal arts modifier/SP flags preserved','1tick reignite only live owner: D12 original30.5/50/180/30 dynamic timer, no parent hook skip','Source lifetime target cleanup single AoE when center damage fatal; allocated474 instead of unclamped616 request','ASPD2 windup18/full30 reference, source interval remains19/35'],
        'scope':'Content+pure-provider author, standalone native-stat Boss with controlled target definitions. All13 diskCP/head fullWorld/tasks/RNG/time/events. No kernel edit, no fullphase/normal/rebirth/screen/branch/stage/client claim.',
        'integration_required':['Strict compose external D12 and combat module singleowner; metadata owned_ability_bindings/arbitration entries must be consumed','Combined arbitration priority and skill busy group with ordinary normal behavior','Actual joint four-mode/rebirth/terminal permission and source-safe buff callbacks','SummonFlame genuine looping branch is Root-owned, outside these2skills'],
        'source_policies':p['manifest']['metadata']['reference_policies'],'old_evidence_retained':['skills.module.v1/v2/v3 draft artifacts','skills_author_v1 expression-root failure','skills_author_v2 initialtimer expires915 before35s fixture','skills_boundaries_v1 manual prepare rejected by existing busy cast fixture','skills_boundaries_v2 accepted-damage clamp expectation error'],'independent_peer_approved':False,'whole_stage_approved':False,'client_verified':False}
    out.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out),'pins':len(data['pins'])}))
if __name__=='__main__':main()

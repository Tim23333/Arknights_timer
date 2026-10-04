"""Independent literal clocks/source-mode assertions after actual CP/head proof."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'validation/campaign/chapter08_join_review_v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    path=BASE/'observations.json';p=json.loads(path.read_bytes());normal,first=p['rows'];assert all(r['CP'] and r['head'] and r['all_events'] for r in p['rows'])
    nstarts=[(e['time'],e['payload']['ability']) for e in normal['observations'] if e['type']=='ability.started']
    assert [t for t,a in nstarts if a.endswith('/normal/phase0')]==[0,135,270,405,540,675]
    assert [(t,a) for t,a in nstarts if '/ignite/' in a]==[(611,'ability/ch8/bsnake/ignite/phase0')]
    assert first['initial']=={'hp':0,'active':False,'mode':0};assert first['final']=={'hp':37500,'mode':1}
    events=first['observations'];starts=[(e['time'],e['payload']['ability']) for e in events if e['type']=='ability.started']
    assert not [(t,a) for t,a in starts if 151<=t<991 and ('/normal/' in a or '/ignite/' in a or '/explode/' in a)]
    volleys=[e['time'] for e in events if e['type']=='source.bsnake.screen.volley'];assert volleys==list(range(211,752,60)),volleys
    first_mode1=min(t for t,a in starts if a.endswith('/normal/phase1'))
    ignite=[(t,a) for t,a in starts if a.endswith('/ignite/phase1')]
    assert first_mode1>=991 and ignite and ignite[0][0]>=1561,(first_mode1,ignite)
    assert not [(t,a) for t,a in starts if t>=991 and ('/normal/phase0' in a or '/ignite/phase0' in a or '/explode/phase0' in a)]
    assert not [(t,a) for t,a in starts if a.endswith('/summon_flame')],starts
    protections=[e for e in events if e['type'] in ('buff.applied','buff.removed') and 'bsnake_t[protect]' in e['payload'].get('buff','')]
    assert any(e['time']==1 and e['type']=='buff.removed' and e['payload']['buff']=='buff/ch8/source/bsnake_t[protect]' for e in protections)
    assert any(e['time']==1 and e['type']=='buff.applied' and e['payload']['buff']=='buff/ch8/source/bsnake_t[protect]/reborn' for e in protections)
    result={'status':'partial_join_two_fresh_actual_cases_source_policy_passed','core':p['core'],'source_join_sha256':p['audit']['join_sha256'],'first_mode1_normal_start':first_mode1,'phase1_ignite_starts':ignite,'screen_10volley_times':volleys,
        'clock_interpretation':'Restart full initial19/35/75 from991 and wait normal70 busy; observed effect-order may delay legal start one tick. This is current explicit reference rule, not recovered native pause/reset body proof.',
        'source_and_geometry_scope':'Original6b281 partial3rows remained unchanged. Source37500 restoration/phase2 skill exclusion/phase1 clock guard and protective profile replacement actually checked; finalzero/tracknextwaveTrue/7row stage proof not claimed.',
        'pins':{str(x):sha(x) for x in [path,BASE/'normal/observations.json',BASE/'firstdown/observations.json',BASE/'source.audit.json',BASE/'screen.geometry.source_plan.json',ROOT/'tools/chapter08_join_review/review_v2.py',Path(__file__)]}}
    out=BASE/'source_gate.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out)}))
if __name__=='__main__':main()

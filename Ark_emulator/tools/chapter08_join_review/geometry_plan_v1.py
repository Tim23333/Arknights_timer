"""Source projection requirements only; does not edit frozen screen content."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    source=ROOT/'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json';plan=ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json';join=ROOT/'packages/campaign/chapter08_consumers/bsnake/partial_join.module.v1.json'
    s=json.loads(source.read_bytes());stage=json.loads(plan.read_bytes())['stages']['level_main_08-17']['native_document'];p=json.loads(join.read_bytes());screen=next(c for c in s['prefab']['components'].values() if c['native_class']=='BsnakeScreenAttack');raw=screen['raw'];pr=s['projectile_bsnake'];simple=next(c for c in pr['components'].values() if c['native_class']=='SimpleProjectile');motion=next(c for c in pr['components'].values() if c['native_class']=='FarthestPointMovement');hit=next(c for c in pr['components'].values() if c['native_class']=='HitBehaviour')
    rows=len(stage['mapData']['map']);cols=len(stage['mapData']['map'][0]);assert rows==9 and cols==15 and all(len(row)==cols for row in stage['mapData']['map']);border=raw['_borderToPeel'];assert type(border) is int and border==1
    projected=list(range(border,rows-border));assert projected==[1,2,3,4,5,6,7]
    assert motion['raw']['_speed']==2.5 and simple['raw']['_lifeTime']==60 and simple['raw']['_maxHitNum']==1
    current=[d for d in p['definitions'] if d['kind']=='projectile' and d['id'].startswith('projectile/ch8/bsnake/firecommon/')]
    actual=sorted({d['motion']['parameters']['row'] for d in current});assert actual==[1,2,3] and len(current)==12
    data={'schema':'ark-sim/jt8-3-screen-projection-plan/v1','status':'source_requirements_not_runtime_stage_pass','source_locks':{str(x):sha(x) for x in (source,plan,join,Path(__file__))},
        'native_map':{'rows':rows,'cols':cols,'border_peel':border,'required_rows':projected},'existing_controlled_rows':actual,
        'source_components':{'screen':screen,'simple_projectile':simple,'movement':motion,'hit':hit,'colliders':pr['geometry_sources']},
        'new_content_recipe':['New screen module version derives row set from supplied exact native map rows and source borderPeel1; rejects non-int/bool, nonrectangular map or nonpositive interior.',
            'Keep original three-row definitions/frozen bytes; derive missing r4/r5/r6/r7 prototypes from source-complete template, preserving speed2.5/lifetime60/max1/retain-source/hit category/default eligibility and collider. Four delay prototype IDs per row gives28.',
            'One real random.birth decision per each of7rows per actual volley; preserve declared .10000000149 source randomDelayToBorn and current discrete0/1/2/3frame reference policy. Never use one shared random sample for allrows.',
            'Actual ten firstscreen volleys must launch70rays total and sample70 RNG values; controlled3rows has30rays. This count applies firstscreen only, finalscreen separately.',
            'Retain pure trajectory map-bounds projection. Current reference launch col1 toward13 for15cols; sourceDirection/useStartDirection fields must stay visible as body/constructor feedback policy rather than claiming full native geometry.',
            'Fresh7row test places one qualified player perrow1..7 and no players border0/8, differentRES perrow; assert7 launches/7 qualified impacts once each, no border ray/late source attribute or target-free shortcuts, source actor never moved to launch location.',
            'Separate camo/air/targetfree/enemy/neutral intercept cases; actual CP with all7 pending rays and freshhead. Old3rowgreen receipts do not transfer.'],
        'expected_counts':{'firstscreen_volley_rows':7,'projectile_prototypes':28,'actual_volley_count_source':10,'total_firstscreen_rays':70},
        'pending_final_and_wave':['Native final screen graph not in current partial join','Source finish+track nextwaveTrue generic boundary still independent task','Mode clocks fullrestart vs elapsed/pause must be explicitly reference policy and independently measured'],
        'no_generic_kernel_change_required_for_row_count':True,'client_verified':False,'whole_stage_verified':False}
    out=ROOT/'validation/campaign/chapter08_join_review_v2/screen.geometry.source_plan.json';assert not out.exists();out.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()

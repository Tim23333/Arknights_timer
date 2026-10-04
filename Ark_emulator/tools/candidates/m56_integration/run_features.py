"""Run frozen branch assertions against the actually imported M44 composition."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m56_chapter03_integrated_candidate'
CORE='9fd0e2e11e19ad3573b9f85b49cff52ae6503cc031e44124d452c5972294f011'
OUT=ROOT/'validation/campaign/m56_integration'


def main():
    copied=ROOT/'tools/experiments/m56_integration';copied.mkdir(parents=True,exist_ok=True)
    mapping={'m41_hole/test_contact.py':'test_contact.py','m42_aura_remove/test_remove.py':'test_remove.py',
             'defdrn_status/test_model.py':'test_defdrn.py','m45_aura_reentry/test_reentry.py':'test_reentry.py','m46_area/test_generic.py':'test_generic.py','m46_area/test_boss.py':'test_boss.py','m49_visibility/test_toggle.py':'test_toggle.py','m49_visibility/test_sources.py':'test_sources.py','m51_payment/test_stock_copy.py':'test_stock.py','m51_payment/test_peer_copy.py':'test_payment_peer.py','m51_payment/test_atomic_record.py':'test_atomic_record.py','m53_qualified_area/test_area.py':'test_qualified_area.py','m55_obstacle/test_contact.py':'test_obstacle_contact.py'}
    guards=[Path(__file__),ROOT/'tools/candidates/m56_integration/prepare.py']
    for old,new in mapping.items():
        source=ROOT/'tools/experiments'/old;raw=source.read_bytes();text=raw.decode('utf8')
        for name in ('campaign_m41_hole_contact_candidate','campaign_m42_aura_remove_candidate','campaign_m37_projectile_refs_candidate','campaign_m45_aura_reentry_candidate','campaign_m46_area_members_candidate','campaign_m49_visibility_candidate','campaign_m51_deploy_payment_candidate','campaign_m50_deploy_stock_candidate','campaign_m53_qualified_area_candidate','campaign_m55_route_obstacle_candidate'):
            text=text.replace(name,'campaign_m56_chapter03_integrated_candidate')
        destination=copied/new;destination.write_bytes(text.encode('utf8'));guards.extend([source,destination])
        (OUT/('original_'+new)).write_bytes(raw)
    sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent!=RUNTIME/'ark_sim' or implementation_digest()!=CORE:raise ValueError('Wrong integrated feature runtime')
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};start=implementation_digest()
    import pytest
    selection=[str(copied), 'tests_v2/test_lossless_request_transform.py','tests_v2/test_chapter02_birth_contact_adapter.py',
        'tests_v2/test_chapter02_reference_tile_fields.py','tests_v2/test_chapter02_reference_story_control.py',
        'tests_v2/test_campaign_content_composition.py','tests_v2/test_auras.py','tests_v2/test_domain_rules.py',
        'tests_v2/test_engine.py','tests_v2/test_damage_hooks_random.py','tests_v2/test_buff_mode_lifecycle.py','-q','--tb=short']
    code=int(pytest.main(selection));after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};end=implementation_digest()
    report={'schema':'ark-sim/integrated-feature-tests/v1','passed':code==0 and before==after and start==end,
        'exit_code':code,'core_start':start,'core_end':end,'source_start':before,'source_end':after,'selection':selection,
        'module':ark_sim.__file__,'actual_client_verified':False}
    (OUT/'features.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()

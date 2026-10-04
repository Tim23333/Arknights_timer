"""Distinguish native amount hpRatio from unresolved hpRechargeRatio."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'packages/campaign/chapter08_consumers/bsnake'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    source=BASE/'source.closure.v1.json';p=json.loads(source.read_bytes());raw=p['RebornTalent']['raw'];bb=p['consumer_merged_BB12'];assert raw['_hpRechargeRatio']==.5 and raw['_maxRespawnCnt']==2
    assert bb['reborn.max_hp']['value']==bb['reborn.atk']['value']==.5 and bb['reborn.duration']['value']==5
    assert len(raw['_extraRebornDataPresets'])==1 and raw['_extraRebornDataPresets'][0]['hpRechargeRatio']==0 and raw['_extraRebornDataPresets'][0]['useMinHpRatio']==0
    dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';text=dump.read_text(encoding='utf8');snippets={}
    for name in ('public struct Unit.RebornData','public class RebornTalent : Talent','private class Enemy.States.RebornState','public struct RebornTalent.AdvancedRebornData'):
        start=text.index(name);start=text.rfind('// Namespace:',0,start);end=text.index('\n// Namespace:',text.index(name))+1;snippets[name]=text[start:end]
    assert 'public FP hpRatio; // 0x10' in snippets['public struct Unit.RebornData']
    assert 'public FP hpRechargeRatio; // 0x30' in snippets['public struct Unit.RebornData']
    assert 'ModifyHpRatio(FP hpRatio)' in snippets['public class RebornTalent : Talent']
    assert 'm_recoverStartHp' in snippets['private class Enemy.States.RebornState'] and 'm_tween' in snippets['private class Enemy.States.RebornState']
    out=BASE/'source.first_restore.review.v1.json';assert not out.exists()
    maximum=p['variant']['native_enemy']['resolved']['attributes']['maxHp']*(1+bb['reborn.max_hp']['value']);assert maximum==75000
    result={'schema':'ark-sim/bsnake-first-restore-source-review/v1','status':'native_hpRechargeRatio_amount_mapping_unproven_reference100percent_recommended',
        'source_locks':{str(x):sha(x) for x in (source,dump,Path(__file__),ROOT/'validation/campaign/chapter08_join_review_v2/source_gate.json')},
        'exact_raw_fields':{'hpRechargeRatio':raw['_hpRechargeRatio'],'rebornDuration':bb['reborn.duration'],'rebornMaxHpBuff':bb['reborn.max_hp'],'rebornAtkBuff':bb['reborn.atk'],'extra_presets':raw['_extraRebornDataPresets'],'raw_RebornTalent':raw},
        'native_schema':{'dump_path':str(dump),'dump_sha256':sha(dump),'excerpts':snippets,'distinction':'Unit.RebornData contains separate hpRatio and hpRechargeRatio. RebornTalent.ModifyHpRatio takes hpRatio, not a named hpRechargeRatio argument. Enemy.RebornState also has HP/tween fields. A schema declaration alone cannot assign final amount or charge timing semantics to raw.5.',
            'method_bodies_recovered':False,'hpRechargeRatio_as_time_fraction_proven':False,'hpRechargeRatio_as_final_HP_fraction_proven':False},
        'PRTS_current_evidence':{'url':'https://prts.wiki/w/%E2%80%9C%E4%B8%8D%E6%AD%BB%E7%9A%84%E9%BB%91%E8%9B%87%E2%80%9D','checked_date':'2026-10-04','retrieved_statement':'首次被击败时进行持续5s的重生(恢复100%生命值)','retrieval_scope':'Current page/search source directly checked through web; no downloaded complete HTML or revisionID is claimed.',
            'related_clock_statements':'Current enemy page general source note says entering form resets skill CDs, and CDs pause when not in corresponding mode. This supports explicit restart/CD review, not an exact recovered frame-order implementation.',
            'historical_revision_verified':False,'history_attempts':[{'url':'https://prts.wiki/index.php?title=%E2%80%9C%E4%B8%8D%E6%AD%BB%E7%9A%84%E9%BB%91%E8%9B%87%E2%80%9D&action=history','result':'web access unavailable'}, {'url':'https://prts.wiki/api.php?action=query&titles=%E2%80%9C%E4%B8%8D%E6%AD%BB%E7%9A%84%E9%BB%91%E8%9B%87%E2%80%9D&prop=revisions&rvprop=ids%7Ctimestamp%7Ccontent&rvslots=main&rvlimit=3&format=json','result':'web access unavailable / native curl TLS handshake failed'}],
            'version_limit':'Current reference describes100%; exact historical revision at local20260831 or fixed56 has not been proven. Do not invent revision IDs/old percentages.'},
        'small_source_math_assertions':{'baseHP':50000,'boost_multiplier':1.5,'effective_capacity':maximum,'old_literal_half_endpoint':maximum*raw['_hpRechargeRatio'],'current_reference_full_endpoint':maximum,'five_second_delay_ticks_at30Hz':150},
        'competing_interpretations':[{'policy':'raw.5 final amount multiplier','endpoint':37500,'evidence':'Old model implements this and actual CP/head proves internal consistency only; native amount mapping not established.'},
            {'policy':'recovery before maxHP synchronization','endpoint_options':[25000,37500],'evidence':'Different ordering/fraction preservation can yield these values; no recovered native method confirms it; none supplies full100% by itself.'},
            {'policy':'raw.5 recharge-animation or progress parameter, separate hpRatio full endpoint','endpoint':75000,'evidence':'Separate native hpRatio/rechargeRatio fields and tween schema are compatible, but specific timing/assignment meaning remains unknown.'},
            {'policy':'reference-first observed full capacity after5s','endpoint':75000,'evidence':'Explicit current PRTS100% and fixed base/boost; recommended new model default while parameter semantics remain replaceable.'}],
        'recommended_default':{'source_raw_hpRechargeRatio_preserved':.5,'source_parameter_semantics':'unresolved_native_recharge_parameter_not_final_amount_proof','after_first_wait_seconds':5,'restored_amount_rule':'effective capacity (75000), not capacity * raw_hpRechargeRatio','new_content_only':True,'generic_kernel_change_required':False,
            'required_actual_new_proofs':['Public firstdown preserves50000base and+50% native buff, inactive waiting,5s endpoint75000; source maxHP75000/ATK1155','New CP before/inside waiting and head on new module/core identity; do not migrate old37.5proof','Second source terminal restore0 and final screen remain separate finite source preset, not fake full revival']},
        'old_receipts_scope':'Old6b281/rawratio0.5/37500 source_gate14280 and sameinput CP/head remain valid literal-model evidence. They are not actual Boss recovery/source-complete admission. No old files, expectations, raw fields or runtime modified.',
        'actual_client_verified':False,'source_Boss_complete':False}
    out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out)}))
if __name__=='__main__':main()

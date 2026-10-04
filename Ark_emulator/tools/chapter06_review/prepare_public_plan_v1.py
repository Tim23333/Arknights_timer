"""Public fixed12 rotation candidate; source DP/slots/HP remain authoritative."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    package=ROOT/'validation/campaign/chapter06_join_draft_v2/06-14.json';p=json.loads(package.read_bytes());scene=p['scenarioDraft']
    defs={d['id']:d for d in p['definitions']};commands=[];rows=[]
    placements=[(0,'char_151_myrtle',6,5),(360,'char_222_bpipe',6,5),(660,'char_128_plosis',5,5),
        (960,'char_010_chen',6,6),(1260,'char_107_liskam',4,6),(1560,'char_202_demkni',6,7),
        (1860,'char_103_angel',5,6),(2160,'char_180_amgoat',3,6),(2460,'char_003_kalts',5,7),
        (2760,'char_358_lisa',3,7),(3060,'char_400_weedy',6,8),(3360,'char_179_cgbird',5,9)]
    commands += [{'at':300,'action':'skill','source':'c6_myrtle','ability':'ability/campaign_myrtle_s2'},
                 {'at':330,'action':'withdraw','source':'c6_myrtle'},
                 {'at':1860-10,'action':'skill','source':'c6_bpipe','ability':'ability/campaign_bpipe_s3'},
                 {'at':2700,'action':'withdraw','source':'c6_bpipe'},
                 {'at':3000,'action':'withdraw','source':'c6_chen'}]
    roster={r['definition'] if isinstance(r,dict) else r for r in scene['roster']}
    for tick,key,row,col in placements:
        unit='unit/'+key;alias='c6_'+key.split('_')[-1];assert unit in roster
        tile=scene['map']['tiles'][row*scene['map']['cols']+col];ground=defs[unit]['components']['deployable']['terrain']=='ground'
        assert tile['buildableType']&(1 if ground else 2)
        commands.append({'at':tick,'action':'deploy','entity':unit,'row':row,'col':col,'facing':'right','alias':alias})
        rows.append({'unit':unit,'alias':alias,'tick':tick,'position':{'row':row,'col':col},'source_tile':tile})
    commands += [
        {'at':2700,'action':'skill','source':'c6_kalts','ability':'ability/kalts_summon'},
        {'at':3000,'action':'skill','source':'c6_kalts','ability':'ability/kalts_host_s3'},
        {'at':3000,'action':'skill','source':'c6_amgoat','ability':'ability/campaign_amgoat_s3'},
        {'at':3300,'action':'skill','source':'c6_demkni','ability':'ability/demkni_s3'},
        {'at':3600,'action':'skill','source':'c6_lisa','ability':'ability/lisa_s3'},
        {'at':3600,'action':'skill','source':'c6_plosis','ability':'ability/plosis_s2_first_packet'},
        {'at':3660,'action':'skill','source':'c6_weedy','ability':'ability/campaign_weedy_deploy_cannon'},
        {'at':3780,'action':'skill','source':'c6_weedy','ability':'ability/campaign_weedy_s3'},
        {'at':4200,'action':'skill','source':'c6_cgbird','ability':'ability/cgbird_s3'},
        {'at':4230,'action':'skill','source':'c6_cgbird','ability':'ability/support_night_bird'}]
    commands.sort(key=lambda c:c['at'])
    out=ROOT/'scenarios/campaign/chapter06/level_main_06-14/public_plan_v1';out.mkdir(parents=True,exist_ok=False)
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf8')
    report={'package_sha':sha(package),'commands_sha':sha(out/'commands.json'),'fixed12_distinct_deploy_attempts':12,'source_terrain_validated':rows,
        'scope':'Public candidate rotation only; DP/SP/cooldown/HP/owned-blocking and actual admission require runtime. No pregrant/forcedsuccess or fullstage acceptance.',
        'manual_auto_only_skill_calls':False,'pending_mechanism_witnesses':['Rebirth second phase','IceShield random tile/kill boundary','Source-trap ownedbranch','Every fixed12 actual deployment before terminal']}
    (out/'plan.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'commands':len(commands),'sha':sha(out/'commands.json')}))


if __name__=='__main__':main()

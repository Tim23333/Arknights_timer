"""Fixed twelve native-map public input plan; costs and admission stay runtime-owned."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    package=ROOT/'packages/campaign/chapter07_stage_models/level_main_07-15.native_draft.v1.json'
    p=json.loads(package.read_bytes());s=p['scenarioDraft'];mp=s['map'];rows=[]
    plan=[('myrtle','151_myrtle',0,6,3,'up'),('bpipe','222_bpipe',870,6,3,'up'),
          ('plosis','128_plosis',1350,5,2,'right'),('chen','010_chen',1830,6,4,'up'),
          ('liskam','107_liskam',2310,4,2,'right'),('demkni','202_demkni',2790,5,3,'up'),
          ('angel','103_angel',3270,5,4,'up'),('amgoat','180_amgoat',3750,3,2,'right'),
          ('kalts','003_kalts',4230,5,5,'up'),('lisa','358_lisa',4710,2,2,'down'),
          ('weedy','400_weedy',5490,4,5,'left'),('cgbird','179_cgbird',5970,5,9,'left')]
    definitions={d['id']:d for d in p['definitions']}
    for alias,suffix,tick,row,col,facing in plan:
        uid='unit/char_'+suffix;assert uid in s['roster']
        terrain=definitions[uid]['components']['deployable'].get('terrain','ground')
        mask=2 if terrain=='high' else 1 if terrain=='ground' else 3
        assert mp['tiles'][row*mp['cols']+col]['buildableType'] & mask
        rows.append({'at':tick,'action':'deploy','entity':uid,'row':row,'col':col,
                     'facing':facing,'alias':'c7_'+alias})
    for alias,tick in [('myrtle',810),('bpipe',4650),('chen',5130),('liskam',5610)]:
        rows.append({'at':tick,'action':'withdraw','source':'c7_'+alias})
    for alias,tick,ability in [('myrtle',300,'campaign_myrtle_s2'),('bpipe',2400,'campaign_bpipe_s3'),
        ('kalts',4500,'kalts_summon'),('kalts',4800,'kalts_host_s3'),('amgoat',4800,'campaign_amgoat_s3'),
        ('demkni',5100,'demkni_s3'),('lisa',5400,'lisa_s3'),('plosis',5400,'plosis_s2_first_packet'),
        ('weedy',6090,'campaign_weedy_deploy_cannon'),('weedy',6150,'campaign_weedy_s3'),
        ('cgbird',6540,'campaign_night_summon_cage'),('cgbird',6570,'campaign_night_s3')]:
        command={'at':tick,'action':'skill','source':'c7_'+alias,'ability':'ability/'+ability}
        if ability=='kalts_summon':command['payload']={'position':{'row':4,'col':4},'facing':'up'}
        if ability=='campaign_weedy_deploy_cannon':command['payload']={'position':{'row':4,'col':4},'facing':'left'}
        if ability=='campaign_night_summon_cage':command['payload']={'position':{'row':6,'col':10},'facing':'left'}
        rows.append(command)
    rows.sort(key=lambda row:row['at'])
    out=ROOT/'scenarios/campaign/chapter07/level_main_07-15/public_plan_v1/commands.json'
    out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists()
    out.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8',newline='')
    meta={'source_package_sha':hashlib.sha256(package.read_bytes()).hexdigest(),
          'commands_sha':hashlib.sha256(out.read_bytes()).hexdigest(),'planned_distinct_fixed12':12,
          'commands':len(rows),'native_slots':9,'native_DP':10,
          'source_map_deployment_masks_checked':True,'legal_accepted_count':None,
          'scope':'Publicattempts only. Real DP/slots/death/control/skills/stock validated by actual command outcomes. Nativebirthtiming untouched, no perfect victory requirement.'}
    (out.parent/'plan.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    print(json.dumps(meta))


if __name__=='__main__':main()

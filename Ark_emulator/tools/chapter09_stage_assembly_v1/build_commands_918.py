"""Fixed twelve public attempts on native cells, including two real device cards."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    package=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v1.life99999.json';p=json.loads(package.read_bytes());scene=p['scenarioDraft'];defs={x['id']:x for x in p['definitions']};mp=scene['map'];commands=[]
    placements=[('myrtle','151_myrtle',0,5,3,'up'),('bpipe','222_bpipe',600,5,3,'up'),
        ('plosis','128_plosis',1050,5,4,'up'),('chen','010_chen',1530,4,3,'right'),
        ('liskam','107_liskam',2010,3,4,'down'),('demkni','202_demkni',2490,4,5,'left'),
        ('angel','103_angel',2970,6,2,'right'),('amgoat','180_amgoat',3450,5,6,'up'),
        ('kalts','003_kalts',3930,3,5,'down'),('lisa','358_lisa',4410,1,6,'down'),
        ('weedy','400_weedy',4890,6,5,'left'),('cgbird','179_cgbird',5370,6,6,'up')]
    for alias,suffix,at,row,col,face in placements:
        entity='unit/char_'+suffix;assert entity in scene['roster'];terrain=defs[entity]['components']['deployable']['terrain'];mask=2 if terrain=='high' else 1;assert mp['tiles'][row*mp['cols']+col]['buildableType']&mask
        commands.append({'at':at,'action':'deploy','entity':entity,'row':row,'col':col,'facing':face,'alias':'c9_'+alias})
    for alias,at in [('myrtle',540),('bpipe',4350),('chen',4770),('liskam',5250)]:commands.append({'at':at,'action':'withdraw','source':'c9_'+alias})
    skills=[('myrtle',300,'campaign_myrtle_s2'),('bpipe',2100,'campaign_bpipe_s3'),('kalts',4200,'kalts_summon'),
        ('kalts',4500,'kalts_host_s3'),('amgoat',4500,'campaign_amgoat_s3'),('demkni',4650,'demkni_s3'),
        ('lisa',4920,'lisa_s3'),('plosis',5100,'plosis_s2_first_packet'),('weedy',5400,'campaign_weedy_deploy_cannon'),
        ('weedy',5460,'campaign_weedy_s3'),('cgbird',5940,'cgbird_s3'),('cgbird',5970,'support_night_bird')]
    for alias,at,name in skills:
        command={'at':at,'action':'skill','source':'c9_'+alias,'ability':'ability/'+name};assert command['ability'] in defs
        if name=='kalts_summon':command['payload']={'position':{'row':3,'col':2},'facing':'right'}
        if name=='campaign_weedy_deploy_cannon':command['payload']={'position':{'row':6,'col':4},'facing':'up'}
        if name=='support_night_bird':command['payload']={'position':{'row':3,'col':7},'facing':'left'}
        commands.append(command)
    device='unit/ch9/demolition/body';assert scene['cards']==[device]
    for at,row,col,face,name in [(120,2,3,'right','device1'),(1800,4,5,'left','device2')]:
        assert mp['tiles'][row*mp['cols']+col]['buildableType'];commands.append({'at':at,'action':'deploy','entity':device,'row':row,'col':col,'facing':face,'alias':'c9_'+name})
    # Finite participation plan releases surviving blockers after the encounter
    # window. Rejected already-dead withdrawals remain real command outcomes.
    for i,(alias,_,_,_,_,_) in enumerate(placements):commands.append({'at':12000+i,'action':'withdraw','source':'c9_'+alias})
    commands.sort(key=lambda x:x['at']);out=ROOT/'scenarios/campaign/chapter09/level_main_09-16/public_plan_v1_finite/commands.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();out.write_text(json.dumps(commands,indent=2)+'\n',encoding='utf8')
    meta={'source_package_sha':hashlib.sha256(package.read_bytes()).hexdigest(),'commands_sha':hashlib.sha256(out.read_bytes()).hexdigest(),'planned_distinct12':12,'commands':len(commands),'card_requests':2,'finite_withdraw_at':12000,'native_slots':8,'native_initialDP':12,'native_map_masks_checked':True,'actual_accepted_count':None,'scope':'Real public attempts, outcome acceptance/DP/slots/source status/skillSP at runtime; no perfect victory requirement; native waves unchanged'};(out.parent/'plan.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8');print(json.dumps(meta))


if __name__=='__main__':main()

"""M78-common exact-hunk lease fix composition into frozen M91, new M94 only."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.candidates.m79_rebirth_environment.prepare import core,sha
from tools.candidates.m90_disk_immunity.prepare import compose
U=ROOT.parent/'unpack_work'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--m93-core',required=True);ap.add_argument('--m93-freeze',type=Path,required=True);ap.add_argument('--freeze-sha',required=True);args=ap.parse_args()
 common=U/'campaign_m78_owned_attachment_candidate';base=U/'campaign_m91_complete_c4_candidate';incoming=U/'campaign_m93_world_cast_leases_candidate';out=U/'campaign_m94_complete_c4_candidate'
 assert sha(args.m93_freeze)==args.freeze_sha
 assert core(common)=='27d8ba218d90e6880a4f8704418871a517e5a6f30f034a79db8b04ca46a0cf74'
 assert core(base)=='e370d26ed84e5ac95feea9af51ac038f57ab7b7c22d943dd2116a99b50006feb'
 assert core(incoming)==args.m93_core
 # The independently frozen source is a three-file mechanism fix, not another
 # unreviewed capabilities merge. Retain the complete reviewed M91 catalog.
 changed=[p.relative_to(incoming/'ark_sim').as_posix() for p in sorted((incoming/'ark_sim').rglob('*.py')) if sha(p)!=sha(common/'ark_sim'/p.relative_to(incoming/'ark_sim'))]
 assert changed==['domains/abilities.py','domains/attachments.py','domains/effects.py'],changed
 compose(common,base,incoming,out,'m94_complete_c4')
 protected=['kernel/session.py','kernel/events.py','rules/contracts.json','domains/lifecycle.py','domains/rebirth.py','domains/no_source_damage.py','domains/death_projectiles.py','domains/deployment.py','domains/deploy_connectivity.py','domains/applicability.py','domains/periodic_fields.py']
 for name in protected:assert (base/'ark_sim'/name).read_bytes()==(out/'ark_sim'/name).read_bytes(),name
 p=ROOT/'validation/campaign/m94_complete_c4/composition_receipt.json'
 p.write_text(json.dumps({'core':core(out),'m93_core':args.m93_core,'m93_freeze_sha':args.freeze_sha,'m93_freeze':str(args.m93_freeze.resolve()),'changed':changed,'exact_preserved':{n:sha(out/'ark_sim'/n) for n in protected},'whole_stage_executed':False,'formal_approved':False},indent=2)+'\n',encoding='utf8',newline='')
 print(json.dumps({'core':core(out),'receipt_sha256':sha(p)}))
if __name__=='__main__':main()

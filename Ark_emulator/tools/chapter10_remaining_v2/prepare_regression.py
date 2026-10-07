"""Copy frozen author assertions; change only candidate/report identities."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
for old,new,report in [('test_author.py','test_bloodline_joint.py','author.bloodline.joint.v1.json'),('test_domain46.py','test_domain46_joint.py','domain46.joint.v1.json')]:
    source=(ROOT/'tools/chapter10_bloodline_v1'/old).read_text(encoding='utf8')
    source=source.replace('campaign_c10_bloodline_v1_candidate','campaign_c10_joint_v1_candidate')
    source=source.replace("ROOT/'validation/campaign/chapter10_bloodline_v1'","ROOT/'validation/campaign/chapter10_remaining_v2'")
    source=source.replace('validation/campaign/chapter10_bloodline_v1/domain46.resume.v2.json','validation/campaign/chapter10_remaining_v2/'+report)
    source=source.replace('author.final.resume.v8.json',report)
    dst=OUT/new;assert not dst.exists();dst.write_text(source,encoding='utf8')
(ROOT/'validation/campaign/chapter10_remaining_v2').mkdir(parents=True,exist_ok=True)

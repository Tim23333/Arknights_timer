"""Metadata-only count correction; preserve every actual-tested v4 command."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];FOLDER=ROOT/'packages/campaign/chapter0_stage_models'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    rows=[]
    for stage in ('level_main_00-10','level_main_00-11'):
        parent=FOLDER/(stage+'.public.plan.v4.json');doc=json.loads(parent.read_bytes());count=sum(c['action']=='skill' and c['ability'] not in ('ability/kalts_summon','ability/campaign_weedy_deploy_cannon','ability/support_night_bird') for c in doc['commands']);assert count==50
        doc.update({'schema':'ark-sim/chapter0-public-finite-plan/v5','manual_selected_skill_attempts':count,'metadata_count_correction_only':True,'parent_plan_v4_sha256':sha(parent)})
        path=FOLDER/(stage+'.public.plan.v5.json');encoded=json.dumps(doc,ensure_ascii=False,indent=2)+'\n'
        if path.exists():assert path.read_text(encoding='utf8')==encoded
        else:path.write_text(encoded,encoding='utf8')
        rows.append({'stage':stage,'sha256':sha(path),'selected_skills':50,'summons':3,'commands_changed':False})
    out=ROOT/'validation/campaign/chapter0_stage_assembly_v1/public.plan.v5.receipt.json';out.write_text(json.dumps({'records':rows,'tool_sha256':sha(Path(__file__)),'whole_stage':False},indent=2)+'\n',encoding='utf8');print(json.dumps(rows))
if __name__=='__main__':main()

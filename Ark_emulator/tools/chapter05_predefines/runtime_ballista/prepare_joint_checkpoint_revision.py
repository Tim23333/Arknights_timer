"""Fresh preserved checkpoint location only; no source/behavior expectation edits."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
 here=Path(__file__).parent;test=here/'test_source_chain_v3.py';dest=here/'test_source_chain_v4.py';runner=here/'verify_joint_v3.py';next_runner=here/'verify_joint_v4.py'
 if dest.exists() or next_runner.exists():raise ValueError('Preserve joint identities')
 text=test.read_text(encoding='utf8');old='validation/campaign/chapter05_complete_v1/source_chain_v3.pending_branch.checkpoint.json';new='validation/campaign/chapter05_ballista_joint_v3_v2/source_chain.author_v2.pending_branch.checkpoint.json';assert text.count(old)==1;text=text.replace(old,new,1);dest.write_text(text,encoding='utf8',newline='');code=runner.read_text(encoding='utf8');code=code.replace("'validation/campaign/chapter05_ballista_joint_v3'","'validation/campaign/chapter05_ballista_joint_v3_v2'",1).replace('test_source_chain_v3.py','test_source_chain_v4.py').replace("endswith('test_source_chain_v3')","endswith('test_source_chain_v4')");next_runner.write_text(code,encoding='utf8',newline='');print({'checkpoint_new':new,'other_source_or_behavior_changed':False})
if __name__=='__main__':main()
